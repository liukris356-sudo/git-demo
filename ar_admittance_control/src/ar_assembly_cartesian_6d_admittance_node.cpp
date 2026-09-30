#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <Eigen/Geometry>
#include <rclcpp/rclcpp.hpp>

#include "ar_admittance_control/admittance_common.hpp"

namespace {

using ar_admittance_control::Clock;
using ar_admittance_control::Vector6d;
constexpr double kPi = ar_admittance_control::kPi;
constexpr double kDeg = kPi / 180.0;

constexpr std::array<double, 6> kBackP6MmDeg{
    224.7736, -337.1420, 2.0454, 175.2683, -1.1645, -154.7335};
constexpr std::array<double, 6> kFinalP8MmDeg{
    228.7783, -343.0617, -5.8556, -174.7136, 0.7086, -153.7597};
constexpr double kFinalP8Elbow = 1.2180 * kDeg;
constexpr double kPreInsertLiftM = 0.0005;

struct TaughtPoint {
  std::array<double, 6> pose{};
  double elbow{};
  std::array<double, 7> joints{};
};

struct PlanPoint {
  Eigen::Isometry3d pose{Eigen::Isometry3d::Identity()};
  double elbow{};
};

struct Segment {
  PlanPoint start;
  PlanPoint finish;
  double duration_s{};
  double start_s{};
};

std::vector<std::string> splitCsv(const std::string &line) {
  std::vector<std::string> result;
  std::stringstream stream(line);
  std::string cell;
  while (std::getline(stream, cell, ',')) result.push_back(cell);
  return result;
}

double cellNumber(const std::vector<std::string> &cells, std::size_t index) {
  if (index >= cells.size()) throw std::runtime_error("short CSV row");
  std::size_t used = 0;
  const double value = std::stod(cells[index], &used);
  if (used != cells[index].size() || !std::isfinite(value)) {
    throw std::runtime_error("invalid CSV number: " + cells[index]);
  }
  return value;
}

std::map<std::string, TaughtPoint> loadPoints(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open points CSV: " + path);
  std::map<std::string, TaughtPoint> points;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') continue;
    const auto cells = splitCsv(line);
    if (cells.empty() || cells[0] == "name") continue;
    if (cells.size() < 21) throw std::runtime_error("CSV row has fewer than 21 fields");
    TaughtPoint point;
    for (std::size_t i = 0; i < 6; ++i) point.pose[i] = cellNumber(cells, 1 + i);
    point.elbow = cellNumber(cells, 13);
    for (std::size_t i = 0; i < 7; ++i) point.joints[i] = cellNumber(cells, 14 + i);
    points[cells[0]] = point;
  }
  if (!points.count("P_SAFE") || !points.count("P_EDGE_IN")) {
    throw std::runtime_error("CSV must contain P_SAFE and P_EDGE_IN");
  }
  return points;
}

Eigen::Isometry3d poseFromSix(const std::array<double, 6> &pose) {
  Eigen::Isometry3d result = Eigen::Isometry3d::Identity();
  result.translation() = Eigen::Vector3d(pose[0], pose[1], pose[2]);
  result.linear() =
      (Eigen::AngleAxisd(pose[5], Eigen::Vector3d::UnitZ()) *
       Eigen::AngleAxisd(pose[4], Eigen::Vector3d::UnitY()) *
       Eigen::AngleAxisd(pose[3], Eigen::Vector3d::UnitX()))
          .toRotationMatrix();
  return result;
}

std::array<double, 6> sixFromPose(const Eigen::Isometry3d &pose) {
  const Eigen::Vector3d zyx = pose.linear().eulerAngles(2, 1, 0);
  return {pose.translation().x(), pose.translation().y(),
          pose.translation().z(), zyx[2], zyx[1], zyx[0]};
}

double rotationDistance(const Eigen::Isometry3d &a,
                        const Eigen::Isometry3d &b) {
  Eigen::AngleAxisd angle(a.linear().transpose() * b.linear());
  return std::abs(angle.angle());
}

double smoothStep(double value) {
  const double u = std::clamp(value, 0.0, 1.0);
  return u * u * u * (10.0 + u * (-15.0 + 6.0 * u));
}

double smoothStepDerivative(double value) {
  const double u = std::clamp(value, 0.0, 1.0);
  return 30.0 * u * u * (u - 1.0) * (u - 1.0);
}

double interpolateProfile(const std::vector<double> &progress,
                          const std::vector<double> &values,
                          double query) {
  const double clamped = std::clamp(query, 0.0, 1.0);
  const auto upper = std::upper_bound(progress.begin(), progress.end(), clamped);
  if (upper == progress.begin()) return values.front();
  if (upper == progress.end()) return values.back();
  const std::size_t high = static_cast<std::size_t>(upper - progress.begin());
  const std::size_t low = high - 1;
  const double span = progress[high] - progress[low];
  const double ratio = span > 0.0 ? (clamped - progress[low]) / span : 0.0;
  return values[low] + ratio * (values[high] - values[low]);
}

const char *phaseName(double progress) {
  if (progress < 0.06) return "APPROACH";
  if (progress < 0.30) return "LIP_CONTACT";
  if (progress < 0.34) return "RELEASE";
  if (progress < 0.55) return "INSERT";
  if (progress < 0.85) return "FLATTEN";
  return "SEAT";
}

const char *axisName(int axis) {
  static constexpr std::array<const char *, 6> names{
      "X", "Y", "Z", "Rx", "Ry", "Rz"};
  return axis >= 0 && axis < static_cast<int>(names.size())
             ? names[static_cast<std::size_t>(axis)]
             : "unknown";
}

class NominalTrajectory {
 public:
  NominalTrajectory(const TaughtPoint &safe, const TaughtPoint &edge,
                    const Vector6d &trajectory_error, double speed_scale) {
    PlanPoint p_safe{poseFromSix(safe.pose), safe.elbow};

    std::array<double, 6> back_six{};
    for (std::size_t i = 0; i < 3; ++i) {
      back_six[i] = kBackP6MmDeg[i] * 0.001;
      back_six[3 + i] = edge.pose[3 + i];
    }
    back_six[2] = edge.pose[2] + kPreInsertLiftM;
    PlanPoint p_back{poseFromSix(back_six), edge.elbow};

    auto edge_six = edge.pose;
    PlanPoint p_edge{poseFromSix(edge_six), edge.elbow};

    std::array<double, 6> press_six{};
    for (std::size_t i = 0; i < 3; ++i) {
      press_six[i] = kFinalP8MmDeg[i] * 0.001;
      press_six[3 + i] = kFinalP8MmDeg[3 + i] * kDeg;
    }
    PlanPoint p_press{poseFromSix(press_six), kFinalP8Elbow};

    for (PlanPoint *point : {&p_back, &p_edge, &p_press}) {
      point->pose.translation() += trajectory_error.head<3>();
      point->pose.linear() =
          ar_admittance_control::rotationVectorToMatrix(
              trajectory_error.tail<3>()) *
          point->pose.linear();
    }

    add(p_safe, p_back, 1.0 * speed_scale, 1.0 * speed_scale);
    add(p_back, p_edge, 0.8 * speed_scale, 0.8 * speed_scale);
    add(p_edge, p_press, 0.3 * speed_scale, 0.5 * speed_scale);
    points_ = {p_safe, p_back, p_edge, p_press};
  }

  PlanPoint sample(double elapsed_s) const {
    if (elapsed_s <= 0.0) return segments_.front().start;
    for (const auto &segment : segments_) {
      if (elapsed_s <= segment.start_s + segment.duration_s) {
        const double u = smoothStep(
            (elapsed_s - segment.start_s) / segment.duration_s);
        PlanPoint result;
        result.pose.translation() =
            segment.start.pose.translation() +
            u * (segment.finish.pose.translation() -
                 segment.start.pose.translation());
        const Eigen::Quaterniond q0(segment.start.pose.linear());
        const Eigen::Quaterniond q1(segment.finish.pose.linear());
        result.pose.linear() = q0.slerp(u, q1).normalized().toRotationMatrix();
        result.elbow = segment.start.elbow +
                       u * (segment.finish.elbow - segment.start.elbow);
        return result;
      }
    }
    return segments_.back().finish;
  }

  double duration() const {
    const auto &last = segments_.back();
    return last.start_s + last.duration_s;
  }

  const std::vector<PlanPoint> &points() const { return points_; }

 private:
  void add(const PlanPoint &start, const PlanPoint &finish,
           double linear_mm_s, double rotation_deg_s) {
    if (linear_mm_s <= 0.0 || rotation_deg_s <= 0.0) {
      throw std::invalid_argument("trajectory speed must be positive");
    }
    const double translation_s =
        (finish.pose.translation() - start.pose.translation()).norm() *
        1000.0 / linear_mm_s;
    const double rotation_s = rotationDistance(start.pose, finish.pose) /
                              kDeg / rotation_deg_s;
    Segment segment{start, finish, std::max({translation_s, rotation_s, 0.5}),
                    segments_.empty()
                        ? 0.0
                        : segments_.back().start_s +
                              segments_.back().duration_s};
    segments_.push_back(segment);
  }

  std::vector<Segment> segments_;
  std::vector<PlanPoint> points_;
};

rokae::CartesianPosition controllerPoint(const PlanPoint &point) {
  const auto pose = sixFromPose(point.pose);
  rokae::CartesianPosition result;
  for (std::size_t i = 0; i < 3; ++i) {
    result.trans[i] = pose[i];
    result.rpy[i] = pose[3 + i];
  }
  result.elbow = point.elbow;
  result.hasElbow = true;
  return result;
}

class AssemblyCartesian6DAdmittanceNode final : public rclcpp::Node {
 public:
  AssemblyCartesian6DAdmittanceNode()
      : Node("ar_assembly_cartesian_6d_admittance_node") {
    active_ = declare_parameter<bool>("active_control", false);
    sensor_mounted_ =
        declare_parameter<bool>("sensor_mounted_to_robot", true);
    robot_ip_ = declare_parameter<std::string>("robot_ip", "192.168.2.160");
    local_ip_ = declare_parameter<std::string>("local_ip", "192.168.2.100");
    tool_ = declare_parameter<std::string>("tool", "g_tool_1");
    workobject_ = declare_parameter<std::string>("workobject", "g_wobj_0");
    points_file_ = declare_parameter<std::string>("points_file", "");
    wrench_topic_ = declare_parameter<std::string>(
        "wrench_topic", "/m3815/wrench_raw");
    trajectory_error_ = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "trajectory_error", {0.0002, 0.0, 0.0, 0.0, 0.0, 0.0}),
        "trajectory_error");
    preload_error_at_safe_ =
        declare_parameter<bool>("preload_error_at_safe", false);
    preload_error_duration_s_ =
        declare_parameter<double>("preload_error_duration_s", 14.0);
    speed_scale_ = declare_parameter<double>("speed_scale", 0.5);
    duration_shadow_s_ = declare_parameter<double>("shadow_duration_s", 20.0);
    wrench_timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.05);
    soft_limit_margin_deg_ =
        declare_parameter<double>("soft_limit_margin_deg", 3.0);

    admittance_.mass = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "virtual_mass", {5.0, 5.0, 5.0, 0.05, 0.05, 0.05}),
        "virtual_mass");
    admittance_.damping = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "damping", {150.0, 150.0, 180.0, 1.0, 1.0, 1.0}),
        "damping");
    admittance_.stiffness = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "stiffness", {5000.0, 5000.0, 6000.0, 5.0, 5.0, 5.0}),
        "stiffness");
    admittance_.deadband = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "deadband", {0.5, 0.5, 0.5, 0.03, 0.03, 0.03}),
        "deadband");
    max_offset_ = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "max_offset",
            {0.0005, 0.0005, 0.0005, 0.0174533, 0.0174533, 0.0087266}),
        "max_offset");
    min_offset_ = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "min_offset",
            {-0.0005, -0.0005, -0.0005,
             -0.0174533, -0.0174533, -0.0087266}),
        "min_offset");
    // The shared solver uses a symmetric internal clamp. Give it the larger
    // absolute side, then apply the true asymmetric bounds in this node.
    admittance_.max_position =
        max_offset_.cwiseMax(min_offset_.cwiseAbs());
    admittance_.max_velocity = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "max_velocity",
            {0.0005, 0.0005, 0.0003, 0.00872665, 0.00872665, 0.00436332}),
        "max_velocity");
    admittance_.max_acceleration = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "max_acceleration", {0.02, 0.02, 0.01, 0.20, 0.20, 0.10}),
        "max_acceleration");
    admittance_.filter_cutoff_hz =
        declare_parameter<double>("filter_cutoff_hz", 10.0);
    wrench_to_motion_sign_ = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "wrench_to_motion_sign", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}),
        "wrench_to_motion_sign");

    phase_approach_axes_ = phaseMask("phase_approach_axes",
                                    {0, 0, 0, 0, 0, 0});
    phase_lip_axes_ = phaseMask("phase_lip_axes", {1, 1, 1, 1, 1, 1});
    phase_release_axes_ = phaseMask("phase_release_axes", {1, 1, 1, 1, 1, 1});
    phase_insert_axes_ = phaseMask("phase_insert_axes", {1, 1, 1, 1, 1, 1});
    phase_flatten_axes_ = phaseMask("phase_flatten_axes", {1, 1, 1, 1, 1, 1});
    phase_seat_axes_ = phaseMask("phase_seat_axes", {1, 1, 1, 1, 1, 1});

    profile_progress_ = declare_parameter<std::vector<double>>(
        "normal_profile_progress",
        {0.0, 0.06, 0.15, 0.25, 0.30, 0.34, 0.40,
         0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 1.0});

    normal_force_upper_n_ = declare_parameter<std::vector<double>>(
        "normal_force_upper_n",
        {1.8, 2.1, 2.7, 2.5, 2.5, 1.7, 1.1,
         1.1, 7.8, 6.9, 10.8, 16.5, 26.0, 35.0});

    const std::array<std::string, 6> center_names{
        "normal_fx_center_n",
        "normal_fy_center_n",
        "normal_fz_center_n",
        "normal_mx_center_nm",
        "normal_my_center_nm",
        "normal_mz_center_nm"};

    const std::array<std::string, 6> width_names{
        "normal_fx_half_width_n",
        "normal_fy_half_width_n",
        "normal_fz_half_width_n",
        "normal_mx_half_width_nm",
        "normal_my_half_width_nm",
        "normal_mz_half_width_nm"};

    const std::array<double, 6> default_width{
        0.6, 0.7, 2.0, 0.15, 0.15, 0.10};

    for (std::size_t axis = 0; axis < 6; ++axis) {
      normal_center_profile_[axis] =
          declare_parameter<std::vector<double>>(
              center_names[axis],
              std::vector<double>(profile_progress_.size(), 0.0));

      normal_half_width_profile_[axis] =
          declare_parameter<std::vector<double>>(
              width_names[axis],
              std::vector<double>(
                  profile_progress_.size(), default_width[axis]));
    }

    excess_hold_s_ = declare_parameter<double>("excess_hold_s", 0.10);
    trajectory_governor_enabled_ =
        declare_parameter<bool>("trajectory_governor_enabled", true);
    trajectory_rate_ramp_per_s_ =
        declare_parameter<double>("trajectory_rate_ramp_per_s", 4.0);
    governor_trigger_hold_s_ =
        declare_parameter<double>("governor_trigger_hold_s", 0.10);
    governor_force_trigger_n_ =
        declare_parameter<double>("governor_force_trigger_n", 2.0);
    governor_force_clear_n_ =
        declare_parameter<double>("governor_force_clear_n", 1.0);
    governor_torque_trigger_nm_ =
        declare_parameter<double>("governor_torque_trigger_nm", 0.10);
    governor_torque_clear_nm_ =
        declare_parameter<double>("governor_torque_clear_nm", 0.05);
    recovery_clear_hold_s_ =
        declare_parameter<double>("recovery_clear_hold_s", 0.20);
    recovery_timeout_s_ =
        declare_parameter<double>("recovery_timeout_s", 8.0);
    recovery_resume_offset_ = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "recovery_resume_offset",
            {0.00025, 0.00010, 0.00015,
             0.00174533, 0.00261799, 0.00087266}),
        "recovery_resume_offset");
    uncorrectable_hold_s_ =
        declare_parameter<double>("uncorrectable_hold_s", 0.50);
    uncorrectable_margin_n_ =
        declare_parameter<double>("uncorrectable_margin_n", 2.0);
    saturation_hold_s_ =
        declare_parameter<double>("saturation_hold_s", 0.50);
    admittance_enable_progress_ =
        declare_parameter<double>("admittance_enable_progress", 0.34);
    error_injection_end_progress_ =
        declare_parameter<double>("error_injection_end_progress", 0.15);
    centering_contact_force_n_ =
        declare_parameter<double>("centering_contact_force_n", 1.0);
    centering_contact_hold_s_ =
        declare_parameter<double>("centering_contact_hold_s", 0.05);
    seat_enable_progress_ =
        declare_parameter<double>("seat_enable_progress", 0.85);
    seat_target_force_n_ =
        declare_parameter<double>("seat_target_force_n", 25.0);
    seat_force_axis_ = declare_parameter<int>("seat_force_axis", 2);
    seat_force_sign_ = declare_parameter<double>("seat_force_sign", 1.0);
    seat_hold_s_ = declare_parameter<double>("seat_hold_s", 0.05);
    require_seat_force_ =
        declare_parameter<bool>("require_seat_force", true);
    hard_force_n_ = declare_parameter<double>("hard_force_n", 35.0);
    hard_torque_nm_ = declare_parameter<double>("hard_torque_nm", 1.50);

    const auto sensor_xyz = declare_parameter<std::vector<double>>(
        "tool_to_sensor_translation_m", {0.0, 0.0, 0.0});
    const auto sensor_rpy = declare_parameter<std::vector<double>>(
        "tool_to_sensor_rpy_rad", {0.0, 0.0, 0.0});
    transform_.controlled_p_sensor =
        ar_admittance_control::vector3(sensor_xyz,
                                       "tool_to_sensor_translation_m");
    transform_.controlled_R_sensor =
        ar_admittance_control::rpyToRotation(sensor_rpy);
    transform_.sign = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "wrench_sign", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}),
        "wrench_sign");
    transform_.enabled = Vector6d::Ones();

    validate();
    receiver_ = std::make_unique<ar_admittance_control::WrenchReceiver>(
        *this, wrench_topic_, wrench_timeout_s_);
    RCLCPP_WARN(
        get_logger(),
        "Mode=%s; phase-aware 6D Cartesian admittance; trajectory error "
        "xyz=[%+.3f %+.3f %+.3f] mm, rot=[%+.3f %+.3f %+.3f] deg; "
        "hard limits %.1f N / %.2f Nm.",
        active_ ? "ACTIVE" : "SHADOW", trajectory_error_[0] * 1000.0,
        trajectory_error_[1] * 1000.0, trajectory_error_[2] * 1000.0,
        trajectory_error_[3] / kDeg, trajectory_error_[4] / kDeg,
        trajectory_error_[5] / kDeg, hard_force_n_, hard_torque_nm_);
  }

  int run() {
    if (!receiver_->waitForData(5.0)) {
      RCLCPP_ERROR(get_logger(), "No fresh wrench data within 5 seconds");
      return 2;
    }
    std::string tare_reason;
    RCLCPP_INFO(get_logger(), "Hands off: collecting 2 s tare...");
    if (!receiver_->tare(2.0, 3.0, 0.3, tare_reason)) {
      RCLCPP_ERROR(get_logger(), "Tare failed: %s", tare_reason.c_str());
      return 3;
    }

    const auto points = loadPoints(points_file_);
    const NominalTrajectory centered_trajectory(
        points.at("P_SAFE"), points.at("P_EDGE_IN"), Vector6d::Zero(),
        speed_scale_);
    const NominalTrajectory perturbed_trajectory(
        points.at("P_SAFE"), points.at("P_EDGE_IN"), trajectory_error_,
        speed_scale_);
    printPlan(centered_trajectory);
    return active_ ? runActive(points, centered_trajectory,
                               perturbed_trajectory)
                   : runShadow(points, centered_trajectory,
                               perturbed_trajectory);
  }

 private:
  Vector6d phaseMask(const std::string &name,
                     const std::vector<double> &defaults) {
    const Vector6d mask = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(name, defaults), name.c_str());
    if (!mask.allFinite() || (mask.array() < 0.0).any() ||
        (mask.array() > 1.0).any()) {
      throw std::invalid_argument(name + " values must be 0 or 1");
    }
    return (mask.array() > 0.5).cast<double>();
  }

  Vector6d enabledAxes(double progress) const {
    if (progress < 0.06) return phase_approach_axes_;
    if (progress < 0.30) return phase_lip_axes_;
    if (progress < 0.34) return phase_release_axes_;
    if (progress < 0.55) return phase_insert_axes_;
    if (progress < 0.85) return phase_flatten_axes_;
    return phase_seat_axes_;
  }

  void validate() const {
    const auto profile_size = profile_progress_.size();
    bool profile_valid =
        profile_size >= 2 &&
        normal_force_upper_n_.size() == profile_size &&
        std::abs(profile_progress_.front()) < 1e-9 &&
        std::abs(profile_progress_.back() - 1.0) < 1e-9;

    for (std::size_t i = 0; profile_valid && i < profile_size; ++i) {
      profile_valid =
          std::isfinite(profile_progress_[i]) &&
          std::isfinite(normal_force_upper_n_[i]) &&
          normal_force_upper_n_[i] > 0.0 &&
          (i == 0 || profile_progress_[i] > profile_progress_[i - 1]);

      for (std::size_t axis = 0; profile_valid && axis < 6; ++axis) {
        profile_valid =
            normal_center_profile_[axis].size() == profile_size &&
            normal_half_width_profile_[axis].size() == profile_size &&
            std::isfinite(normal_center_profile_[axis][i]) &&
            std::isfinite(normal_half_width_profile_[axis][i]) &&
            normal_half_width_profile_[axis][i] > 0.0;
      }
    }

    admittance_.validate();
    const bool signs_valid = wrench_to_motion_sign_.allFinite() &&
        ((wrench_to_motion_sign_.array().abs() - 1.0).abs() < 1e-9).all();
    const bool offset_ranges_valid =
        min_offset_.allFinite() && max_offset_.allFinite() &&
        (min_offset_.array() < 0.0).all() &&
        (max_offset_.array() > 0.0).all() &&
        (min_offset_.array() < max_offset_.array()).all();
    bool preload_velocity_valid = std::isfinite(preload_error_duration_s_) &&
                                  preload_error_duration_s_ > 0.0;
    if (preload_velocity_valid && preload_error_at_safe_) {
      // The quintic smooth-step derivative peaks at 1.875.
      const Vector6d preload_peak_velocity =
          1.875 * trajectory_error_.cwiseAbs() / preload_error_duration_s_;
      preload_velocity_valid =
          (preload_peak_velocity.array() <=
           admittance_.max_velocity.array() + 1e-12)
              .all();
    }
    const bool governor_valid =
        std::isfinite(trajectory_rate_ramp_per_s_) &&
        trajectory_rate_ramp_per_s_ > 0.0 &&
        std::isfinite(governor_trigger_hold_s_) &&
        governor_trigger_hold_s_ > 0.0 &&
        std::isfinite(governor_force_trigger_n_) &&
        governor_force_trigger_n_ > 0.0 &&
        std::isfinite(governor_force_clear_n_) &&
        governor_force_clear_n_ > 0.0 &&
        governor_force_clear_n_ < governor_force_trigger_n_ &&
        std::isfinite(governor_torque_trigger_nm_) &&
        governor_torque_trigger_nm_ > 0.0 &&
        std::isfinite(governor_torque_clear_nm_) &&
        governor_torque_clear_nm_ > 0.0 &&
        governor_torque_clear_nm_ < governor_torque_trigger_nm_ &&
        std::isfinite(recovery_clear_hold_s_) &&
        recovery_clear_hold_s_ > 0.0 &&
        std::isfinite(recovery_timeout_s_) && recovery_timeout_s_ > 0.0 &&
        recovery_resume_offset_.allFinite() &&
        (recovery_resume_offset_.array() > 0.0).all() &&
        (recovery_resume_offset_.array() <=
         admittance_.max_position.array())
            .all();

    if (points_file_.empty() ||
        trajectory_error_.head<3>().cwiseAbs().maxCoeff() > 0.0035 ||
        trajectory_error_.tail<3>().cwiseAbs().maxCoeff() > 1.0 * kDeg ||
        speed_scale_ <= 0.0 || speed_scale_ > 1.0 || !signs_valid ||
        !offset_ranges_valid || !preload_velocity_valid || !governor_valid ||
        soft_limit_margin_deg_ < 1.0 || soft_limit_margin_deg_ > 10.0 ||
        max_offset_.head<3>().maxCoeff() > 0.0045 ||
        max_offset_.tail<3>().maxCoeff() > 2.5 * kDeg ||
        min_offset_.head<3>().cwiseAbs().maxCoeff() > 0.0045 ||
        min_offset_.tail<3>().cwiseAbs().maxCoeff() > 2.5 * kDeg ||
        hard_force_n_ <= 0.0 || hard_torque_nm_ <= 0.0 ||
        !profile_valid || excess_hold_s_ < 0.0 ||
        uncorrectable_hold_s_ <= 0.0 || uncorrectable_margin_n_ < 0.0 ||
        saturation_hold_s_ <= 0.0 || admittance_enable_progress_ < 0.0 ||
        admittance_enable_progress_ >= 1.0 ||
        error_injection_end_progress_ <= 0.0 ||
        error_injection_end_progress_ >= seat_enable_progress_ ||
        centering_contact_force_n_ <= 0.0 ||
        centering_contact_force_n_ >= hard_force_n_ ||
        centering_contact_hold_s_ <= 0.0 || seat_enable_progress_ <= 0.0 ||
        seat_enable_progress_ >= 1.0 ||
        seat_enable_progress_ <= admittance_enable_progress_ ||
        seat_target_force_n_ <= 0.0 ||
        seat_target_force_n_ >= hard_force_n_ || seat_force_axis_ < 0 ||
        seat_force_axis_ > 2 ||
        std::abs(std::abs(seat_force_sign_) - 1.0) > 1e-9 ||
        seat_hold_s_ <= 0.0 ||
        (trajectory_error_.array() < min_offset_.array()).any() ||
        (trajectory_error_.array() > max_offset_.array()).any()) {
      throw std::invalid_argument("invalid or unsafe 6D-admittance parameters");
    }
  }

  void printPlan(const NominalTrajectory &trajectory) const {
    static const std::array<const char *, 4> labels{
        "P_SAFE(center)", "P_BACK_LOW(center)",
        "P_EDGE_IN(center)", "P8(center)"};
    RCLCPP_INFO(get_logger(), "Nominal duration %.1f s", trajectory.duration());
    for (std::size_t i = 0; i < trajectory.points().size(); ++i) {
      const auto pose = sixFromPose(trajectory.points()[i].pose);
      RCLCPP_INFO(get_logger(), "%s xyz=[%.3f %.3f %.3f] mm",
                  labels[i], pose[0] * 1000.0, pose[1] * 1000.0,
                  pose[2] * 1000.0);
    }
    RCLCPP_WARN(
        get_logger(),
        "The taught path is the center attractor. The configured perturbation "
        "is injected smoothly and released on contact or at %.1f%% progress. "
        "The YAML phase masks decide which wrench axes may move. Seat "
        "target=%.1f N on workobject axis %d with sign %+.0f; hard "
        "force=%.1f N.",
        error_injection_end_progress_ * 100.0, seat_target_force_n_,
        seat_force_axis_, seat_force_sign_, hard_force_n_);
  }

  void selectTool(rokae::ArRobot &robot) const {
    std::error_code ec;
    robot.setToolset(tool_, workobject_, ec);
    ar_admittance_control::requireOk(ec, "select tool/workobject");
  }

  void waitForPowerReady(rokae::ArRobot &robot, bool require_idle,
                         const char *stage) const {
    const auto deadline = Clock::now() + std::chrono::seconds(5);
    int consecutive_on_samples = 0;
    while (Clock::now() < deadline) {
      std::error_code ec;
      const auto power = robot.powerState(ec);
      const std::string power_action =
          std::string("read power state at ") + stage;
      ar_admittance_control::requireOk(ec, power_action.c_str());
      if (power == rokae::PowerState::estop) {
        throw std::runtime_error("emergency stop is active at " +
                                 std::string(stage));
      }
      if (power == rokae::PowerState::gstop) {
        throw std::runtime_error("safety gate/stop is active at " +
                                 std::string(stage));
      }
      if (power == rokae::PowerState::on) {
        ++consecutive_on_samples;
        if (consecutive_on_samples >= 3) {
          if (require_idle) {
            const auto state = robot.operationState(ec);
            const std::string state_action =
                std::string("read operation state at ") + stage;
            ar_admittance_control::requireOk(ec, state_action.c_str());
            if (state != rokae::OperationState::idle) {
              throw std::runtime_error(
                  "robot is powered but not idle before real-time control");
            }
          }
          RCLCPP_INFO(get_logger(), "Motor power verified ON at %s", stage);
          return;
        }
      } else {
        consecutive_on_samples = 0;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    throw std::runtime_error("motor power did not become ready at " +
                             std::string(stage));
  }

  void requireAtSafe(rokae::ArRobot &robot,
                     const TaughtPoint &safe) const {
    std::error_code ec;
    const auto pose = robot.cartPosture(rokae::CoordinateType::endInRef, ec);
    ar_admittance_control::requireOk(ec, "read TCP in workobject");
    const auto joints = robot.jointPos(ec);
    ar_admittance_control::requireOk(ec, "read current joints");
    const Eigen::Vector3d delta(pose.trans[0] - safe.pose[0],
                                pose.trans[1] - safe.pose[1],
                                pose.trans[2] - safe.pose[2]);
    double joint_error = 0.0;
    for (std::size_t i = 0; i < 7; ++i) {
      joint_error = std::max(joint_error,
                             std::abs(joints[i] - safe.joints[i]));
    }
    RCLCPP_INFO(get_logger(), "Current versus P_SAFE: %.3f mm, max joint %.3f deg",
                delta.norm() * 1000.0, joint_error / kDeg);
    if (delta.norm() > 0.001 || joint_error > 1.0 * kDeg) {
      throw std::runtime_error(
          "robot is not at P_SAFE; run guarded GO_SAFE first");
    }
  }

  void checkPath(rokae::ArRobot &robot, const TaughtPoint &safe,
                 const NominalTrajectory &trajectory,
                 const char *description,
                 bool include_preload_pose = false) const {
    std::vector<double> start(safe.joints.begin(), safe.joints.end());
    std::vector<rokae::CartesianPosition> path;
    if (include_preload_pose) {
      PlanPoint preload = trajectory.points().front();
      preload.pose.translation() += trajectory_error_.head<3>();
      preload.pose.linear() =
          ar_admittance_control::rotationVectorToMatrix(
              trajectory_error_.tail<3>()) *
          preload.pose.linear();
      path.push_back(controllerPoint(preload));
    }
    for (std::size_t i = 1; i < trajectory.points().size(); ++i) {
      path.push_back(controllerPoint(trajectory.points()[i]));
    }
    std::vector<double> target;
    std::error_code ec;
    const int failed = robot.checkPath(start, path, target, ec);
    if (ec || target.size() < 7) {
      throw std::runtime_error("controller checkPath failed at " +
                               std::to_string(failed) + ": " + ec.message());
    }
    RCLCPP_INFO(get_logger(), "Controller checkPath (%s): PASS", description);
  }

  int runShadow(const std::map<std::string, TaughtPoint> &points,
                const NominalTrajectory &centered_trajectory,
                const NominalTrajectory &perturbed_trajectory) {
    rokae::ArRobot robot;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      selectTool(robot);
      checkPath(robot, points.at("P_SAFE"), centered_trajectory, "centered");
      checkPath(robot, points.at("P_SAFE"), perturbed_trajectory,
                "maximum configured perturbation");
      RCLCPP_WARN(get_logger(),
                  "SHADOW: no power or motion. Excite one direction at a "
                  "time and verify all workobject Fx/Fy/Fz/Mx/My/Mz signs.");
      const auto started = Clock::now();
      auto next_log = started;
      while (rclcpp::ok() &&
             !ar_admittance_control::stop_requested.load() &&
             std::chrono::duration<double>(Clock::now() - started).count() <
                 duration_shadow_s_) {
        if (!receiver_->fresh()) throw std::runtime_error("wrench data stale");
        std::error_code ec;
        const auto ref_pose = robot.cartPosture(
            rokae::CoordinateType::endInRef, ec);
        ar_admittance_control::requireOk(ec, "read TCP for SHADOW transform");
        const Eigen::Isometry3d t_ref_tool = poseFromSix(
            {ref_pose.trans[0], ref_pose.trans[1], ref_pose.trans[2],
             ref_pose.rpy[0], ref_pose.rpy[1], ref_pose.rpy[2]});
        const Vector6d tool = transform_.apply(receiver_->corrected());
        Vector6d wrench_ref;
        wrench_ref.head<3>() = t_ref_tool.linear() * tool.head<3>();
        wrench_ref.tail<3>() = t_ref_tool.linear() * tool.tail<3>();
        if (Clock::now() >= next_log) {
          RCLCPP_INFO(get_logger(),
                      "W_workobject=[%+.2f %+.2f %+.2f N | "
                      "%+.3f %+.3f %+.3f Nm]",
                      wrench_ref[0], wrench_ref[1], wrench_ref[2],
                      wrench_ref[3], wrench_ref[4], wrench_ref[5]);
          next_log = Clock::now() + std::chrono::milliseconds(200);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
      }
      robot.stopReceiveRobotState();
      return 0;
    } catch (const std::exception &error) {
      RCLCPP_ERROR(get_logger(), "SHADOW error: %s", error.what());
      robot.stopReceiveRobotState();
      return 4;
    }
  }

  static const char *faultText(int code) {
    switch (code) {
      case 1: return "wrench stale/non-finite";
      case 2: return "force / torque hard limit";
      case 4: return "robot state read failure";
      case 5: return "TCP tracking envelope";
      case 6: return "6D correction saturated while excess wrench remained";
      case 7: return "force exceeded phase envelope on disabled axes";
      case 8: return "trajectory ended without reaching seating force";
      case 9: return "unexpected contact while preloading test error at P_SAFE";
      case 10: return "controller did not accept the RT TCP command";
      case 11: return "abnormal-contact recovery timed out";
      default: return "unknown";
    }
  }

  int runActive(const std::map<std::string, TaughtPoint> &points,
                const NominalTrajectory &trajectory,
                const NominalTrajectory &perturbed_trajectory) {
    if (!sensor_mounted_) {
      RCLCPP_ERROR(get_logger(), "Set sensor_mounted_to_robot=true only after rigid mounting");
      return 5;
    }
    rokae::ArRobot robot;
    std::shared_ptr<rokae::RtMotionControlCobot<7>> controller;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      selectTool(robot);
      requireAtSafe(robot, points.at("P_SAFE"));
      checkPath(robot, points.at("P_SAFE"), trajectory, "centered");
      checkPath(robot, points.at("P_SAFE"), perturbed_trajectory,
                "maximum configured perturbation",
                preload_error_at_safe_);

      const std::string arm_token = "ARM_PHASE_6D_ADMIT";
      std::cout
          << "ACTIVE PHASE-AWARE 6D CARTESIAN ADMITTANCE.\n"
          << "The taught trajectory is the center attractor; the configured "
             "perturbation is released after contact or progress fallback.\n"
          << "Injected translation offset [mm]: " << std::showpos
          << trajectory_error_[0] * 1000.0 << ' '
          << trajectory_error_[1] * 1000.0 << ' '
          << trajectory_error_[2] * 1000.0 << std::noshowpos << "\n"
          << (preload_error_at_safe_
                  ? "Test preload: establish the full offset at P_SAFE before "
                    "trajectory motion; unexpected preload contact aborts.\n"
                  : "Test preload: disabled; error ramps with trajectory "
                    "progress.\n")
          << "The YAML phase masks, not the sensor alone, decide which axes "
             "may move.\n"
          << "Verify all six SHADOW signs, clear workspace, hold E-stop.\n"
          << "Type " << arm_token << " exactly: " << std::flush;
      std::string confirmation;
      std::getline(std::cin, confirmation);
      if (confirmation != arm_token) {
        RCLCPP_WARN(get_logger(), "Cancelled; robot was not powered on");
        return 0;
      }
      std::string quiet_reason;
      if (!receiver_->verifyCorrectedQuiet(1.0, 3.0, 0.3, quiet_reason)) {
        throw std::runtime_error("pre-arm quiet check: " + quiet_reason);
      }

      std::array<double[2], 7> soft_limits{};
      ar_admittance_control::checkSoftLimits(
          robot, soft_limits, soft_limit_margin_deg_ * kDeg);
      ar_admittance_control::powerInNonRealtime(robot);
      waitForPowerReady(robot, true, "NrtCommand");
      ar_admittance_control::switchToRealtime(robot);
      waitForPowerReady(robot, false, "RtCommand");
      controller = robot.getRtMotionController().lock();
      if (!controller) throw std::runtime_error("RT controller handle expired");

      robot.startReceiveRobotState(
          std::chrono::milliseconds(1),
          {rokae::RtSupportedFields::tcpPose_m,
           rokae::RtSupportedFields::tcpPose_c,
           rokae::RtSupportedFields::elbow_m,
           rokae::RtSupportedFields::jointPos_m});
      std::array<double, 16> base_safe_array{};
      std::array<double, 7> start_joints{};
      double start_elbow = 0.0;
      if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m,
                             base_safe_array) != 0 ||
          robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                             start_joints) != 0 ||
          robot.getStateData(rokae::RtSupportedFields::elbow_m,
                             start_elbow) != 0) {
        throw std::runtime_error("read initial RT state failed");
      }
      const Eigen::Isometry3d base_safe =
          ar_admittance_control::rowMajorToEigen(base_safe_array);
      const Eigen::Isometry3d ref_safe = trajectory.points().front().pose;
      const Eigen::Isometry3d base_ref = base_safe * ref_safe.inverse();

      std::atomic<int> fault{0};
      std::atomic<double> max_force{0.0};
      std::atomic<double> max_torque{0.0};
      std::atomic<double> last_progress{0.0};
      std::atomic<double> last_seat_force{0.0};
      std::atomic<bool> seat_reached{false};
      std::atomic<int> saturated_axis{-1};
      std::array<double, 16> last_desired_array = base_safe_array;
      std::array<double, 16> last_measured_array = base_safe_array;
      std::array<double, 16> last_controller_command_array = base_safe_array;
      bool have_controller_command = false;
      Vector6d last_wrench_ref = Vector6d::Zero();
      Vector6d last_excess = Vector6d::Zero();
      admittance_.position.setZero();
      admittance_.velocity.setZero();
      admittance_.filtered_input.setZero();
      int saturated_cycles = 0;
      int excess_cycles = 0;
      int uncorrectable_cycles = 0;
      int seat_cycles = 0;
      int centering_contact_cycles = 0;
      int preload_contact_cycles = 0;
      int controller_command_miss_cycles = 0;
      int governor_trigger_cycles = 0;
      int recovery_clear_cycles = 0;
      int recovery_count = 0;
      bool recovery_active = false;
      double recovery_elapsed_s = 0.0;
      double recovery_total_s = 0.0;
      double trajectory_elapsed_s = 0.0;
      double trajectory_rate = 1.0;
      bool centering_started =
          trajectory_error_.cwiseAbs().maxCoeff() < 1e-12;
      int centering_trigger = centering_started ? 3 : 0;
      double centering_start_progress = centering_started ? 0.0 : -1.0;
      double minimum_x_correction = 0.0;
      double maximum_x_correction = 0.0;
      double minimum_actual_preload_x = 0.0;
      double maximum_actual_preload_x = 0.0;
      double minimum_rx_correction = 0.0;
      double maximum_rx_correction = 0.0;
      double minimum_actual_preload_rx = 0.0;
      double maximum_actual_preload_rx = 0.0;
      double minimum_ry_correction = 0.0;
      double maximum_ry_correction = 0.0;
      double minimum_actual_preload_ry = 0.0;
      double maximum_actual_preload_ry = 0.0;
      auto started = Clock::now();
      bool first_control_cycle = true;

      const int excess_hold_cycles =
          std::max(1, static_cast<int>(std::ceil(excess_hold_s_ / 0.001)));
      const int uncorrectable_hold_cycles = std::max(
          1, static_cast<int>(std::ceil(uncorrectable_hold_s_ / 0.001)));
      const int saturation_hold_cycles = std::max(
          1, static_cast<int>(std::ceil(saturation_hold_s_ / 0.001)));
      const int seat_hold_cycles =
          std::max(1, static_cast<int>(std::ceil(seat_hold_s_ / 0.001)));
      const int centering_contact_hold_cycles = std::max(
          1, static_cast<int>(std::ceil(centering_contact_hold_s_ / 0.001)));
      const int recovery_clear_hold_cycles = std::max(
          1, static_cast<int>(std::ceil(recovery_clear_hold_s_ / 0.001)));
      const int governor_trigger_hold_cycles = std::max(
          1, static_cast<int>(std::ceil(governor_trigger_hold_s_ / 0.001)));

      std::function<rokae::CartesianPosition()> callback = [&]() {
        rokae::CartesianPosition command{};
        command.pos = base_safe_array;
        command.elbow = start_elbow;
        command.hasElbow = true;

        const Vector6d corrected = receiver_->corrected();
        const Vector6d raw = receiver_->raw();
        if (!receiver_->fresh() || !corrected.allFinite() || !raw.allFinite() ||
            ar_admittance_control::norm3(raw, 0) > 1000.0 ||
            ar_admittance_control::norm3(raw, 3) > 100.0) {
          fault.store(1);
          command.setFinished();
          return command;
        }
        const double force_norm = ar_admittance_control::norm3(corrected, 0);
        const double torque_norm = ar_admittance_control::norm3(corrected, 3);
        max_force.store(std::max(max_force.load(), force_norm));
        max_torque.store(std::max(max_torque.load(), torque_norm));
        if (force_norm >= hard_force_n_ || torque_norm >= hard_torque_nm_) {
          fault.store(2);
          command.setFinished();
          return command;
        }
        std::array<double, 16> measured_array{};
        std::array<double, 16> controller_command_array{};
        std::array<double, 7> measured_joints{};
        double measured_elbow = 0.0;
        if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m,
                               measured_array) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                               measured_joints) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::elbow_m,
                               measured_elbow) != 0) {
          fault.store(4);
          command.setFinished();
          return command;
        }
        if (robot.getStateData(rokae::RtSupportedFields::tcpPose_c,
                               controller_command_array) == 0) {
          last_controller_command_array = controller_command_array;
          have_controller_command = true;
        }

        const Eigen::Isometry3d measured =
            ar_admittance_control::rowMajorToEigen(measured_array);
        last_measured_array = measured_array;
        const Eigen::Isometry3d ref_measured = base_ref.inverse() * measured;
        if (first_control_cycle) {
          started = Clock::now();
          first_control_cycle = false;
        }
        const double total_elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        const bool preloading =
            preload_error_at_safe_ &&
            total_elapsed < preload_error_duration_s_;
        const double trajectory_elapsed = trajectory_elapsed_s;
        const double progress =
            std::clamp(trajectory_elapsed / trajectory.duration(), 0.0, 1.0);
        last_progress.store(progress);

        if (preloading) {
          const double actual_preload_x =
              ref_measured.translation().x() - ref_safe.translation().x();
          const Eigen::AngleAxisd actual_preload_rotation(
              ref_measured.linear() * ref_safe.linear().transpose());
          const double actual_preload_ry =
              std::abs(actual_preload_rotation.angle()) > 1e-12
                  ? actual_preload_rotation.angle() *
                        actual_preload_rotation.axis().y()
                  : 0.0;
          const double actual_preload_rx =
              std::abs(actual_preload_rotation.angle()) > 1e-12
                  ? actual_preload_rotation.angle() *
                        actual_preload_rotation.axis().x()
                  : 0.0;
          minimum_actual_preload_x =
              std::min(minimum_actual_preload_x, actual_preload_x);
          maximum_actual_preload_x =
              std::max(maximum_actual_preload_x, actual_preload_x);
          minimum_actual_preload_rx =
              std::min(minimum_actual_preload_rx, actual_preload_rx);
          maximum_actual_preload_rx =
              std::max(maximum_actual_preload_rx, actual_preload_rx);
          minimum_actual_preload_ry =
              std::min(minimum_actual_preload_ry, actual_preload_ry);
          maximum_actual_preload_ry =
              std::max(maximum_actual_preload_ry, actual_preload_ry);
          preload_contact_cycles =
              force_norm >= centering_contact_force_n_
                  ? preload_contact_cycles + 1
                  : 0;
          if (preload_contact_cycles >= centering_contact_hold_cycles) {
            fault.store(9);
            command.setFinished();
            return command;
          }
        } else {
          preload_contact_cycles = 0;
        }
        const Vector6d tool_wrench = transform_.apply(corrected);
        Vector6d wrench_ref;
        wrench_ref.head<3>() = ref_measured.linear() * tool_wrench.head<3>();
        wrench_ref.tail<3>() = ref_measured.linear() * tool_wrench.tail<3>();
        if (ar_admittance_control::norm3(wrench_ref, 0) >= hard_force_n_ ||
            ar_admittance_control::norm3(wrench_ref, 3) >= hard_torque_nm_) {
          fault.store(2);
          command.setFinished();
          return command;
        }
        last_wrench_ref = wrench_ref;
        const double seat_force =
            seat_force_sign_ * wrench_ref[seat_force_axis_];
        last_seat_force.store(seat_force);

        if (progress >= seat_enable_progress_ &&
            seat_force >= seat_target_force_n_) {
          ++seat_cycles;
        } else {
          seat_cycles = 0;
        }
        if (seat_cycles >= seat_hold_cycles) {
          seat_reached.store(true);
          command.setFinished();
          return command;
        }

        Vector6d center = Vector6d::Zero();
        Vector6d half_width = Vector6d::Zero();
        for (Eigen::Index axis = 0; axis < 6; ++axis) {
          center[axis] = interpolateProfile(
              profile_progress_,
              normal_center_profile_[static_cast<std::size_t>(axis)],
              progress);
          half_width[axis] = interpolateProfile(
              profile_progress_,
              normal_half_width_profile_[static_cast<std::size_t>(axis)],
              progress);
        }

        Vector6d excess = Vector6d::Zero();
        for (Eigen::Index i = 0; i < 6; ++i) {
          // The learned profile is an allowed contact envelope, not a desired
          // force trajectory. Including zero prevents missing contact from
          // creating a fictitious wrench that drives the robot through air.
          const double low = std::min(center[i] - half_width[i], 0.0);
          const double high = std::max(center[i] + half_width[i], 0.0);
          excess[i] = wrench_ref[i] < low
                          ? wrench_ref[i] - low
                          : (wrench_ref[i] > high
                                 ? wrench_ref[i] - high
                                 : 0.0);
        }
        last_excess = excess;

        const bool in_correction_window =
            progress >= admittance_enable_progress_ && progress < 1.0;
        const Vector6d axes = enabledAxes(progress);
        bool enabled_excess = false;
        bool disabled_excess = false;
        bool governor_severe_excess = false;
        bool governor_clear_excess = true;
        for (Eigen::Index i = 0; i < 6; ++i) {
          const bool outside = std::abs(excess[i]) > admittance_.deadband[i];
          enabled_excess = enabled_excess || (outside && axes[i] > 0.5);
          disabled_excess = disabled_excess || (outside && axes[i] <= 0.5);
          if (axes[i] > 0.5) {
            const double magnitude = std::abs(excess[i]);
            const double trigger =
                i < 3 ? governor_force_trigger_n_
                      : governor_torque_trigger_nm_;
            const double clear =
                i < 3 ? governor_force_clear_n_
                      : governor_torque_clear_nm_;
            governor_severe_excess =
                governor_severe_excess || magnitude > trigger;
            governor_clear_excess =
                governor_clear_excess && magnitude <= clear;
          }
        }
        excess_cycles = in_correction_window && enabled_excess
                            ? excess_cycles + 1
                            : 0;
        const bool update_admittance =
            excess_cycles >= excess_hold_cycles;

        governor_trigger_cycles =
            trajectory_governor_enabled_ && !preloading &&
                    in_correction_window && governor_severe_excess
                ? governor_trigger_cycles + 1
                : 0;
        if (governor_trigger_cycles >= governor_trigger_hold_cycles &&
            !recovery_active) {
          recovery_active = true;
          recovery_elapsed_s = 0.0;
          recovery_clear_cycles = 0;
          governor_trigger_cycles = 0;
          ++recovery_count;
        }

        if (!preloading && !centering_started) {
          centering_contact_cycles =
              force_norm >= centering_contact_force_n_
                  ? centering_contact_cycles + 1
                  : 0;
          const bool contact_triggered =
              centering_contact_cycles >= centering_contact_hold_cycles;
          const bool progress_triggered =
              progress >= error_injection_end_progress_;
          if (contact_triggered || progress_triggered) {
            centering_started = true;
            centering_trigger = contact_triggered ? 1 : 2;
            centering_start_progress = progress;
          }
        }

        const double force_upper = interpolateProfile(
            profile_progress_, normal_force_upper_n_, progress);
        const bool force_far_outside =
            force_norm > force_upper + uncorrectable_margin_n_;
        uncorrectable_cycles =
            in_correction_window && force_far_outside && disabled_excess &&
                    !enabled_excess
                ? uncorrectable_cycles + 1
                : 0;
        if (uncorrectable_cycles >= uncorrectable_hold_cycles) {
          fault.store(7);
          command.setFinished();
          return command;
        }

        if (preloading) {
          const double preload_phase =
              total_elapsed / preload_error_duration_s_;
          const double preload_gain = smoothStep(preload_phase);
          admittance_.position = preload_gain * trajectory_error_;
          admittance_.velocity =
              (smoothStepDerivative(preload_phase) /
               preload_error_duration_s_) *
              trajectory_error_;
          admittance_.filtered_input.setZero();
          admittance_.enabled.setZero();
        } else if (!centering_started) {
          // Reproduce the configured test perturbation without moving the
          // center attractor itself. Preserve the scheduled velocity so an
          // early contact transition does not create a velocity discontinuity.
          if (preload_error_at_safe_) {
            admittance_.position = trajectory_error_;
            admittance_.velocity.setZero();
          } else {
            const double injection_phase =
                progress / error_injection_end_progress_;
            const double injection_duration =
                error_injection_end_progress_ * trajectory.duration();
            const double injection_gain = smoothStep(injection_phase);
            admittance_.position = injection_gain * trajectory_error_;
            admittance_.velocity =
                (smoothStepDerivative(injection_phase) /
                 injection_duration) *
                trajectory_error_;
          }
          admittance_.filtered_input.setZero();
          admittance_.enabled.setZero();
        } else {
          admittance_.enabled = Vector6d::Zero();
          if (in_correction_window) admittance_.enabled = axes;
          Vector6d input = Vector6d::Zero();
          if (update_admittance) {
            input = wrench_to_motion_sign_.cwiseProduct(excess);
          }
          // position is the complete offset from the taught center. With a
          // zero input, the existing K*position term attracts it back to zero.
          admittance_.step(input, ar_admittance_control::kControlDt);
        }

        // The common solver is given the larger absolute bound. Apply the
        // true asymmetric bounds here.
        for (Eigen::Index i = 0; i < 6; ++i) {
          if (admittance_.position[i] >= max_offset_[i]) {
            admittance_.position[i] = max_offset_[i];
            admittance_.velocity[i] = std::min(admittance_.velocity[i], 0.0);
          } else if (admittance_.position[i] <= min_offset_[i]) {
            admittance_.position[i] = min_offset_[i];
            admittance_.velocity[i] = std::max(admittance_.velocity[i], 0.0);
          }
        }
        minimum_x_correction =
            std::min(minimum_x_correction, admittance_.position[0]);
        maximum_x_correction =
            std::max(maximum_x_correction, admittance_.position[0]);
        minimum_rx_correction =
            std::min(minimum_rx_correction, admittance_.position[3]);
        maximum_rx_correction =
            std::max(maximum_rx_correction, admittance_.position[3]);
        minimum_ry_correction =
            std::min(minimum_ry_correction, admittance_.position[4]);
        maximum_ry_correction =
            std::max(maximum_ry_correction, admittance_.position[4]);

        if (recovery_active) {
          recovery_elapsed_s += ar_admittance_control::kControlDt;
          recovery_total_s += ar_admittance_control::kControlDt;
          const bool correction_near_center =
              (admittance_.position.cwiseAbs().array() <=
               recovery_resume_offset_.array())
                  .all();
          recovery_clear_cycles =
              governor_clear_excess && correction_near_center
                  ? recovery_clear_cycles + 1
                  : 0;
          if (recovery_clear_cycles >= recovery_clear_hold_cycles) {
            recovery_active = false;
            recovery_elapsed_s = 0.0;
            recovery_clear_cycles = 0;
          } else if (recovery_elapsed_s >= recovery_timeout_s_) {
            fault.store(11);
            command.setFinished();
            return command;
          }
        }

        bool saturated_with_excess = false;
        int cycle_saturated_axis = -1;
        for (Eigen::Index i = 0; i < 6; ++i) {
          const double drive = wrench_to_motion_sign_[i] * excess[i];
          const bool pushing_upper =
              admittance_.position[i] >=
                  0.999 * max_offset_[i] &&
              drive > admittance_.deadband[i];
          const bool pushing_lower =
              admittance_.position[i] <= 0.999 * min_offset_[i] &&
              drive < -admittance_.deadband[i];
          if (axes[i] > 0.5 && (pushing_upper || pushing_lower)) {
            saturated_with_excess = true;
            if (cycle_saturated_axis < 0) {
              cycle_saturated_axis = static_cast<int>(i);
            }
          }
        }
        if (saturated_with_excess) {
          if (saturated_axis.load() == cycle_saturated_axis) {
            ++saturated_cycles;
          } else {
            saturated_axis.store(cycle_saturated_axis);
            saturated_cycles = 1;
          }
        } else {
          saturated_axis.store(-1);
          saturated_cycles = 0;
        }
        if (saturated_cycles >= saturation_hold_cycles) {
          fault.store(6);
          command.setFinished();
          return command;
        }

        const double trajectory_rate_target = recovery_active ? 0.0 : 1.0;
        const double trajectory_rate_step =
            trajectory_rate_ramp_per_s_ * ar_admittance_control::kControlDt;
        trajectory_rate += std::clamp(
            trajectory_rate_target - trajectory_rate,
            -trajectory_rate_step, trajectory_rate_step);

        PlanPoint nominal = trajectory.sample(trajectory_elapsed);
        nominal.pose.translation() += admittance_.position.head<3>();
        nominal.pose.linear() =
            ar_admittance_control::rotationVectorToMatrix(
                admittance_.position.tail<3>()) *
            nominal.pose.linear();
        const Eigen::Isometry3d desired = base_ref * nominal.pose;
        last_desired_array = ar_admittance_control::eigenToRowMajor(desired);
        const double tracking =
            (desired.translation() - measured.translation()).norm();
        const Eigen::AngleAxisd rotation_error(
            measured.linear().transpose() * desired.linear());
        if (have_controller_command) {
          const Eigen::Isometry3d controller_command =
              ar_admittance_control::rowMajorToEigen(
                  last_controller_command_array);
          const double command_mismatch =
              (desired.translation() - controller_command.translation()).norm();
          const double command_rotation_mismatch =
              rotationDistance(desired, controller_command);
          controller_command_miss_cycles =
              total_elapsed > 0.25 &&
                      (command_mismatch > 0.00075 ||
                       command_rotation_mismatch > 0.25 * kDeg)
                  ? controller_command_miss_cycles + 1
                  : 0;
          if (controller_command_miss_cycles >= 50) {
            fault.store(10);
            command.setFinished();
            return command;
          }
        }
        const double tracking_limit = preloading ? 0.00075 : 0.005;
        const double rotation_tracking_limit =
            preloading ? 0.25 * kDeg : 3.0 * kDeg;
        if (tracking > tracking_limit ||
            std::abs(rotation_error.angle()) > rotation_tracking_limit) {
          fault.store(5);
          command.setFinished();
          return command;
        }
        command.pos = last_desired_array;
        command.elbow = nominal.elbow;
        command.hasElbow = true;
        if (!preloading) {
          trajectory_elapsed_s +=
              trajectory_rate * ar_admittance_control::kControlDt;
        }
        if (ar_admittance_control::stop_requested.load() ||
            trajectory_elapsed_s >= trajectory.duration() + 0.5) {
          if (require_seat_force_ &&
              !seat_reached.load() &&
              !ar_admittance_control::stop_requested.load()) {
            fault.store(8);
          }
          command.setFinished();
        }
        return command;
      };

      RCLCPP_WARN(
          get_logger(),
          "ARMED: phase-aware 6D correction, xyz offset bounds "
          "X[%+.3f,%+.3f] Y[%+.3f,%+.3f] Z[%+.3f,%+.3f] mm; "
          "rotation bounds Rx[%+.3f,%+.3f] Ry[%+.3f,%+.3f] "
          "Rz[%+.3f,%+.3f] deg; preload %.1f s + trajectory %.1f s.",
          min_offset_[0] * 1000.0,
          max_offset_[0] * 1000.0,
          min_offset_[1] * 1000.0,
          max_offset_[1] * 1000.0,
          min_offset_[2] * 1000.0,
          max_offset_[2] * 1000.0,
          min_offset_[3] / kDeg,
          max_offset_[3] / kDeg,
          min_offset_[4] / kDeg,
          max_offset_[4] / kDeg,
          min_offset_[5] / kDeg,
          max_offset_[5] / kDeg,
          preload_error_at_safe_ ? preload_error_duration_s_ : 0.0,
          trajectory.duration());
      RCLCPP_INFO(
          get_logger(),
          "Trajectory governor=%s: ramp %.2f/s, recovery clear hold %.2f s, "
          "timeout %.1f s; force trigger/clear %.2f/%.2f N, torque "
          "trigger/clear %.3f/%.3f Nm.",
          trajectory_governor_enabled_ ? "ENABLED" : "DISABLED",
          trajectory_rate_ramp_per_s_, recovery_clear_hold_s_,
          recovery_timeout_s_, governor_force_trigger_n_,
          governor_force_clear_n_, governor_torque_trigger_nm_,
          governor_torque_clear_nm_);
      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::cartesianPosition);
      controller->startLoop(true);
      if (fault.load() != 0) {
        if (fault.load() == 6) {
          const int axis = saturated_axis.load();
          RCLCPP_ERROR(
              get_logger(),
              "WATCHDOG STOP: %s; axis=%s, correction=%+.6f, "
              "limit=%.6f, excess=%+.3f",
              faultText(fault.load()), axisName(axis),
              axis >= 0 ? admittance_.position[axis] : 0.0,
              axis >= 0
                  ? (admittance_.position[axis] >= 0.0
                         ? max_offset_[axis]
                         : min_offset_[axis])
                  : 0.0,
              axis >= 0 ? last_excess[axis] : 0.0);
        } else if (fault.load() == 5 || fault.load() == 10) {
          RCLCPP_ERROR(
              get_logger(),
              "WATCHDOG STOP: %s; desired xyz=[%.3f %.3f %.3f] mm, "
              "controller xyz=[%.3f %.3f %.3f] mm (%s), "
              "measured xyz=[%.3f %.3f %.3f] mm",
              faultText(fault.load()),
              last_desired_array[3] * 1000.0,
              last_desired_array[7] * 1000.0,
              last_desired_array[11] * 1000.0,
              last_controller_command_array[3] * 1000.0,
              last_controller_command_array[7] * 1000.0,
              last_controller_command_array[11] * 1000.0,
              have_controller_command ? "valid" : "unavailable",
              last_measured_array[3] * 1000.0,
              last_measured_array[7] * 1000.0,
              last_measured_array[11] * 1000.0);
        } else {
          RCLCPP_ERROR(get_logger(), "WATCHDOG STOP: %s",
                       faultText(fault.load()));
        }
      }
      RCLCPP_INFO(
          get_logger(),
          "Result: phase=%s (%.1f%%), correction="
          "[%+.3f %+.3f %+.3f mm | %+.3f %+.3f %+.3f deg], "
          "W_ref=[%+.2f %+.2f %+.2f N | %+.3f %+.3f %+.3f Nm], "
          "W_excess=[%+.2f %+.2f %+.2f | %+.3f %+.3f %+.3f], "
          "centering=%s, seat force=%+.2f N, seat=%s, max force=%.2f N, "
          "max torque=%.3f Nm",
          phaseName(last_progress.load()), last_progress.load() * 100.0,
          admittance_.position[0] * 1000.0,
          admittance_.position[1] * 1000.0,
          admittance_.position[2] * 1000.0,
          admittance_.position[3] / kDeg,
          admittance_.position[4] / kDeg,
          admittance_.position[5] / kDeg,
          last_wrench_ref[0], last_wrench_ref[1], last_wrench_ref[2],
          last_wrench_ref[3], last_wrench_ref[4], last_wrench_ref[5],
          last_excess[0], last_excess[1], last_excess[2],
          last_excess[3], last_excess[4], last_excess[5],
          centering_started ? "STARTED" : "NOT_STARTED",
          last_seat_force.load(), seat_reached.load() ? "REACHED" : "NO",
          max_force.load(), max_torque.load());
      const char *centering_trigger_text =
          centering_trigger == 1
              ? "CONTACT"
              : (centering_trigger == 2
                     ? "PROGRESS_FALLBACK"
                     : (centering_trigger == 3 ? "NO_TEST_ERROR" : "NONE"));
      RCLCPP_INFO(
          get_logger(),
          "Return-to-center evidence: X correction range=[%+.3f,%+.3f] mm, "
          "actual preload X range=[%+.3f,%+.3f] mm, final=%+.3f mm; "
          "Rx correction range=[%+.3f,%+.3f] deg, actual preload Rx "
          "range=[%+.3f,%+.3f] deg, final=%+.3f deg; "
          "Ry correction range=[%+.3f,%+.3f] deg, actual preload Ry "
          "range=[%+.3f,%+.3f] deg, final=%+.3f deg; trigger=%s at %.1f%% "
          "progress.",
          minimum_x_correction * 1000.0,
          maximum_x_correction * 1000.0,
          minimum_actual_preload_x * 1000.0,
          maximum_actual_preload_x * 1000.0,
          admittance_.position[0] * 1000.0,
          minimum_rx_correction / kDeg,
          maximum_rx_correction / kDeg,
          minimum_actual_preload_rx / kDeg,
          maximum_actual_preload_rx / kDeg,
          admittance_.position[3] / kDeg,
          minimum_ry_correction / kDeg,
          maximum_ry_correction / kDeg,
          minimum_actual_preload_ry / kDeg,
          maximum_actual_preload_ry / kDeg,
          admittance_.position[4] / kDeg,
          centering_trigger_text,
          centering_start_progress >= 0.0
              ? centering_start_progress * 100.0
              : -1.0);
      RCLCPP_INFO(
          get_logger(),
          "Trajectory governor: enabled=%s, recoveries=%d, total hold=%.3f s, "
          "final rate=%.3f, state=%s.",
          trajectory_governor_enabled_ ? "true" : "false",
          recovery_count, recovery_total_s, trajectory_rate,
          recovery_active ? "RECOVERY" : "RUN");
      ar_admittance_control::safeShutdown(robot, controller);
      return fault.load() == 0 ? 0 : 6;
    } catch (const std::exception &error) {
      RCLCPP_ERROR(get_logger(), "ACTIVE error: %s", error.what());
      ar_admittance_control::safeShutdown(robot, controller);
      return 7;
    }
  }

  bool active_{false};
  bool sensor_mounted_{true};
  std::string robot_ip_;
  std::string local_ip_;
  std::string tool_;
  std::string workobject_;
  std::string points_file_;
  std::string wrench_topic_;
  Vector6d trajectory_error_{Vector6d::Zero()};
  bool preload_error_at_safe_{false};
  double preload_error_duration_s_{14.0};
  double speed_scale_{0.5};
  double duration_shadow_s_{20.0};
  double wrench_timeout_s_{0.05};
  double soft_limit_margin_deg_{3.0};
  ar_admittance_control::Admittance6D admittance_;
  Vector6d min_offset_{Vector6d::Zero()};
  Vector6d max_offset_{Vector6d::Zero()};
  Vector6d wrench_to_motion_sign_{Vector6d::Ones()};
  Vector6d phase_approach_axes_{Vector6d::Zero()};
  Vector6d phase_lip_axes_{Vector6d::Zero()};
  Vector6d phase_release_axes_{Vector6d::Zero()};
  Vector6d phase_insert_axes_{Vector6d::Zero()};
  Vector6d phase_flatten_axes_{Vector6d::Zero()};
  Vector6d phase_seat_axes_{Vector6d::Zero()};
  double hard_force_n_{30.0};
  double hard_torque_nm_{1.25};

  std::vector<double> profile_progress_;
  std::vector<double> normal_force_upper_n_;

  std::array<std::vector<double>, 6> normal_center_profile_;
  std::array<std::vector<double>, 6> normal_half_width_profile_;
  double excess_hold_s_{0.10};
  bool trajectory_governor_enabled_{true};
  double trajectory_rate_ramp_per_s_{4.0};
  double governor_trigger_hold_s_{0.10};
  double governor_force_trigger_n_{2.0};
  double governor_force_clear_n_{1.0};
  double governor_torque_trigger_nm_{0.10};
  double governor_torque_clear_nm_{0.05};
  double recovery_clear_hold_s_{0.20};
  double recovery_timeout_s_{8.0};
  Vector6d recovery_resume_offset_{Vector6d::Zero()};
  double uncorrectable_hold_s_{0.50};
  double uncorrectable_margin_n_{2.0};
  double saturation_hold_s_{0.50};
  double admittance_enable_progress_{0.34};
  double error_injection_end_progress_{0.15};
  double centering_contact_force_n_{1.0};
  double centering_contact_hold_s_{0.05};
  double seat_enable_progress_{0.85};
  double seat_target_force_n_{25.0};
  int seat_force_axis_{2};
  double seat_force_sign_{1.0};
  double seat_hold_s_{0.05};
  bool require_seat_force_{true};
  ar_admittance_control::WrenchTransform transform_;
  std::unique_ptr<ar_admittance_control::WrenchReceiver> receiver_;
};

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, ar_admittance_control::requestStop);
  std::signal(SIGTERM, ar_admittance_control::requestStop);
  rclcpp::init(argc, argv);
  try {
    const auto node =
        std::make_shared<AssemblyCartesian6DAdmittanceNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    std::thread spin_thread([&executor]() { executor.spin(); });
    int result = 1;
    try {
      result = node->run();
    } catch (const std::exception &error) {
      RCLCPP_ERROR(node->get_logger(), "Run error: %s", error.what());
      result = 1;
    }
    if (rclcpp::ok()) rclcpp::shutdown();
    spin_thread.join();
    return result;
  } catch (const std::exception &error) {
    std::cerr << "Fatal: " << error.what() << '\n';
    if (rclcpp::ok()) rclcpp::shutdown();
    return 1;
  }
}
