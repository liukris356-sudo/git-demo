#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include "Eigen/Geometry"
#include "ar_admittance_control/admittance_common.hpp"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rokae/robot.h"

namespace {

constexpr double kDeg = ar_admittance_control::kPi / 180.0;
using Clock = std::chrono::steady_clock;
using Vector6d = ar_admittance_control::Vector6d;

struct PointRecord {
  std::string name;
  std::array<double, 6> tcp_in_reference{};
  std::array<double, 6> flange_in_base{};
  std::array<double, 6> joints{};
};

struct PointFile {
  std::string robot;
  std::string controller;
  std::string sdk;
  std::string tool;
  std::string workobject;
  std::vector<PointRecord> points;
  std::map<std::string, std::pair<double, double>> segment_speeds;
};

struct PlanPoint {
  Eigen::Isometry3d pose{Eigen::Isometry3d::Identity()};
};

struct Segment {
  PlanPoint start;
  PlanPoint finish;
  double duration_s{};
  double start_s{};
};

std::string trim(std::string text) {
  while (!text.empty() &&
         (text.back() == '\r' || text.back() == '\n' || text.back() == ' ')) {
    text.pop_back();
  }
  const auto first = text.find_first_not_of(" \t");
  return first == std::string::npos ? std::string{} : text.substr(first);
}

std::vector<std::string> splitCsv(const std::string &line) {
  std::vector<std::string> fields;
  std::stringstream input(line);
  std::string field;
  while (std::getline(input, field, ',')) fields.push_back(trim(field));
  return fields;
}

double parseCell(const std::vector<std::string> &cells,
                 std::size_t index, const std::string &line) {
  if (index >= cells.size()) {
    throw std::runtime_error("short CSV row: " + line);
  }
  std::size_t used = 0;
  const double value = std::stod(cells[index], &used);
  if (used != cells[index].size() || !std::isfinite(value)) {
    throw std::runtime_error("invalid numeric CSV cell: " + cells[index]);
  }
  return value;
}

PointFile loadPointFile(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open point file: " + path);

  PointFile file;
  std::string line;
  while (std::getline(input, line)) {
    const auto trimmed = trim(line);
    if (trimmed.empty()) continue;
    if (trimmed[0] == '#') {
      const auto comment_fields = splitCsv(trimmed.substr(1));
      if (comment_fields.size() >= 2) {
        if (comment_fields[0] == "robot") file.robot = comment_fields[1];
        if (comment_fields[0] == "controller") file.controller = comment_fields[1];
        if (comment_fields[0] == "sdk") file.sdk = comment_fields[1];
        if (comment_fields[0] == "tool") file.tool = comment_fields[1];
        if (comment_fields[0] == "workobject") file.workobject = comment_fields[1];
        if (comment_fields[0] == "segment_speed" && comment_fields.size() >= 4) {
          const double v = std::stod(comment_fields[2]);
          const double w = std::stod(comment_fields[3]);
          file.segment_speeds[comment_fields[1]] = {v, w};
        }
      }
      continue;
    }

    const auto cells = splitCsv(trimmed);
    if (cells.empty() || cells[0] == "name") continue;
    if (cells.size() < 19) {
      throw std::runtime_error("point row has fewer than 19 fields: " + trimmed);
    }

    PointRecord record;
    record.name = cells[0];
    for (std::size_t i = 0; i < 6; ++i) {
      record.tcp_in_reference[i] = parseCell(cells, 1 + i, trimmed);
    }
    for (std::size_t i = 0; i < 6; ++i) {
      record.flange_in_base[i] = parseCell(cells, 7 + i, trimmed);
    }
    for (std::size_t i = 0; i < 6; ++i) {
      record.joints[i] = parseCell(cells, 13 + i, trimmed);
    }
    file.points.push_back(record);
  }

  if (file.points.size() < 2) {
    throw std::runtime_error("point file must contain at least 2 points: " + path);
  }
  return file;
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
  return 30.0 * u * u * (1.0 + u * (-2.0 + u));
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
  if (progress < 0.50) return "APPROACH";
  if (progress < 0.70) return "LIP_CONTACT";
  if (progress < 0.84) return "CLEARANCE";
  return "SEAT";
}

class NominalTrajectory {
 public:
  NominalTrajectory(const PointFile &file,
                    const Vector6d &trajectory_error,
                    double speed_scale) {
    if (file.points.size() < 2) {
      throw std::runtime_error("trajectory needs at least 2 points");
    }

    std::vector<PlanPoint> base_points;
    base_points.reserve(file.points.size());
    for (const auto &pt : file.points) {
      base_points.push_back({poseFromSix(pt.tcp_in_reference)});
    }

    // Apply error perturbation to non-start points if requested
    for (std::size_t i = 1; i < base_points.size(); ++i) {
      base_points[i].pose.translation() += trajectory_error.head<3>();
      base_points[i].pose.linear() =
          ar_admittance_control::rotationVectorToMatrix(
              trajectory_error.tail<3>()) *
          base_points[i].pose.linear();
    }

    for (std::size_t i = 1; i < base_points.size(); ++i) {
      double linear_mm_s = 0.5;
      double rot_deg_s = 0.5;
      const auto it = file.segment_speeds.find(file.points[i].name);
      if (it != file.segment_speeds.end()) {
        linear_mm_s = it->second.first;
        rot_deg_s = it->second.second;
      }
      add(base_points[i - 1], base_points[i],
          linear_mm_s * speed_scale, rot_deg_s * speed_scale);
    }
    points_ = base_points;
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
        return result;
      }
    }
    return segments_.back().finish;
  }

  double duration() const {
    if (segments_.empty()) return 0.0;
    const auto &last = segments_.back();
    return last.start_s + last.duration_s;
  }

  const std::vector<PlanPoint> &points() const { return points_; }
  const std::vector<Segment> &segments() const { return segments_; }

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
  result.hasElbow = false;
  return result;
}

class XB7AssemblyCartesian6DAdmittanceNode final : public rclcpp::Node {
 public:
  XB7AssemblyCartesian6DAdmittanceNode()
      : Node("xb7_assembly_cartesian_6d_admittance_node") {
    active_control_ = declare_parameter<bool>("active_control", false);
    sensor_mounted_ = declare_parameter<bool>("sensor_mounted_to_robot", false);
    robot_ip_ = declare_parameter<std::string>("robot_ip", "192.168.2.160");
    local_ip_ = declare_parameter<std::string>("local_ip", "192.168.2.100");
    tool_ = declare_parameter<std::string>("tool", "g_tool_1");
    workobject_ = declare_parameter<std::string>("workobject", "g_wobj_0");
    wrench_topic_ = declare_parameter<std::string>("wrench_topic", "/ta67l/wrench_raw");
    points_file_ = declare_parameter<std::string>(
        "points_file",
        "/home/liu/projects/git-demo-admittance/xb7_records/xb7_assembly_new_full_20260929.csv");

    trajectory_error_ = Vector6d(declare_parameter<std::vector<double>>(
        "trajectory_error", {0.0, 0.0, 0.0, 0.0, 0.0, 0.0}).data());
    preload_error_at_safe_ =
        declare_parameter<bool>("preload_error_at_safe", false);
    preload_error_duration_s_ =
        declare_parameter<double>("preload_error_duration_s", 10.0);
    speed_scale_ = declare_parameter<double>("speed_scale", 1.0);
    duration_shadow_s_ = declare_parameter<double>("shadow_duration_s", 60.0);
    wrench_timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.20);
    soft_limit_margin_deg_ =
        declare_parameter<double>("soft_limit_margin_deg", 3.0);

    admittance_.mass = Vector6d(declare_parameter<std::vector<double>>(
        "virtual_mass", {5.0, 5.0, 5.0, 0.05, 0.05, 0.05}).data());
    admittance_.damping = Vector6d(declare_parameter<std::vector<double>>(
        "damping", {150.0, 150.0, 140.0, 2.0, 2.0, 1.5}).data());
    admittance_.stiffness = Vector6d(declare_parameter<std::vector<double>>(
        "stiffness", {800.0, 5000.0, 3000.0, 15.0, 15.0, 10.0}).data());
    admittance_.deadband = Vector6d(declare_parameter<std::vector<double>>(
        "deadband", {0.5, 0.5, 0.5, 0.03, 0.03, 0.03}).data());
    admittance_.filter_cutoff_hz = declare_parameter<double>("filter_cutoff_hz", 10.0);

    min_offset_ = Vector6d(declare_parameter<std::vector<double>>(
        "min_offset",
        {-0.0035, -0.0015, -0.0015, -0.01745329, -0.01745329, -0.00174533}).data());
    max_offset_ = Vector6d(declare_parameter<std::vector<double>>(
        "max_offset",
        {0.0035, 0.0015, 0.0015, 0.01745329, 0.01745329, 0.00174533}).data());
    admittance_.max_position = max_offset_;
    admittance_.max_velocity = Vector6d(declare_parameter<std::vector<double>>(
        "max_velocity",
        {0.0005, 0.0005, 0.0005, 0.00349066, 0.00349066, 0.00174533}).data());
    admittance_.max_acceleration =
        Vector6d(declare_parameter<std::vector<double>>(
            "max_acceleration",
            {0.005, 0.005, 0.005, 0.05, 0.05, 0.03}).data());

    wrench_to_motion_sign_ = Vector6d(declare_parameter<std::vector<double>>(
        "wrench_to_motion_sign", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}).data());

    phase_masks_["APPROACH"] = Vector6d(declare_parameter<std::vector<double>>(
        "phase_approach_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}).data());
    phase_masks_["LIP_CONTACT"] = Vector6d(declare_parameter<std::vector<double>>(
        "phase_lip_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}).data());
    phase_masks_["CLEARANCE"] = Vector6d(declare_parameter<std::vector<double>>(
        "phase_release_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}).data());
    phase_masks_["SEAT"] = Vector6d(declare_parameter<std::vector<double>>(
        "phase_seat_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}).data());

    profile_progress_ = declare_parameter<std::vector<double>>(
        "normal_profile_progress",
        {0.0, 0.06, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.72, 0.78, 0.84, 0.90, 0.95, 1.0});
    normal_force_upper_n_ = declare_parameter<std::vector<double>>(
        "normal_force_upper_n",
        {4.3, 4.3, 4.3, 4.3, 4.3, 4.4, 19.0, 10.0, 11.5, 15.7, 23.9, 25.9, 37.1, 41.5});

    static const std::array<const char *, 6> center_param_names{
        "normal_fx_center_n",  "normal_fy_center_n",
        "normal_fz_center_n",  "normal_mx_center_nm",
        "normal_my_center_nm", "normal_mz_center_nm"};
    static const std::array<const char *, 6> half_width_param_names{
        "normal_fx_half_width_n",  "normal_fy_half_width_n",
        "normal_fz_half_width_n",  "normal_mx_half_width_nm",
        "normal_my_half_width_nm", "normal_mz_half_width_nm"};

    static const std::array<std::vector<double>, 6> default_centers{
        std::vector<double>{0.5094, 0.5416, 0.5586, 0.6635, 0.6861, 0.7726, 3.8568, 1.7643, 3.2393, 3.8533, 8.2532, 10.4796, 10.1748, 12.3071},
        std::vector<double>{-1.0696, -1.0689, -1.0715, -1.0393, -1.0521, -1.0407, -8.6806, -4.9426, -6.27, -10.1719, -9.8376, -13.124, -18.3733, -21.7434},
        std::vector<double>{-0.1731, -0.1671, -0.163, -0.1369, -0.1349, -0.1377, -6.9115, -2.0009, 0.6024, -1.5279, -10.6227, -12.187, -17.9226, -26.3645},
        std::vector<double>{-0.0353, -0.0352, -0.0354, -0.035, -0.0354, -0.0353, -0.006, 0.0131, 0.15, 0.2234, 0.294, 0.2576, 0.1153, -0.0685},
        std::vector<double>{-0.0013, -0.0012, -0.0011, -0.0016, -0.0012, -0.0018, 0.0994, 0.0338, 0.0884, 0.0832, 0.2377, 0.2606, 0.2304, 0.2747},
        std::vector<double>{-0.013, -0.0126, -0.0133, -0.0132, -0.0132, -0.0133, -0.111, -0.0402, -0.0333, -0.0065, 0.2557, 0.0994, -0.1449, -0.2538}};

    static const std::array<std::vector<double>, 6> default_half_widths{
        std::vector<double>{1.055, 1.068, 1.0718, 1.0535, 1.0526, 1.071, 2.5129, 1.6381, 1.8264, 1.8522, 4.8123, 6.3652, 5.0931, 5.3942},
        std::vector<double>{1.256, 1.2553, 1.2703, 1.2707, 1.2672, 1.2535, 4.878, 1.9976, 2.4193, 3.1182, 1.7406, 4.4158, 3.8041, 1.7468},
        std::vector<double>{1.5372, 1.5463, 1.5505, 1.554, 1.5515, 1.5447, 3.2904, 3.6801, 2.0572, 3.0743, 5.4666, 3.566, 6.5815, 3.3944},
        std::vector<double>{0.0512, 0.0514, 0.0514, 0.0513, 0.0515, 0.0513, 0.1049, 0.1008, 0.0953, 0.0949, 0.1145, 0.094, 0.1515, 0.1017},
        std::vector<double>{0.0509, 0.0512, 0.0514, 0.0511, 0.0511, 0.0514, 0.1, 0.0728, 0.0793, 0.0892, 0.1526, 0.2323, 0.1723, 0.1986},
        std::vector<double>{0.0514, 0.0516, 0.0516, 0.0518, 0.0516, 0.0514, 0.0964, 0.0796, 0.0661, 0.0832, 0.2064, 0.193, 0.2131, 0.1551}};

    for (std::size_t axis = 0; axis < 6; ++axis) {
      normal_center_profile_[axis] = declare_parameter<std::vector<double>>(
          center_param_names[axis], default_centers[axis]);
      normal_half_width_profile_[axis] = declare_parameter<std::vector<double>>(
          half_width_param_names[axis], default_half_widths[axis]);
    }

    excess_hold_s_ = declare_parameter<double>("excess_hold_s", 0.10);
    trajectory_governor_enabled_ =
        declare_parameter<bool>("trajectory_governor_enabled", true);
    trajectory_rate_ramp_per_s_ =
        declare_parameter<double>("trajectory_rate_ramp_per_s", 4.0);
    governor_trigger_hold_s_ =
        declare_parameter<double>("governor_trigger_hold_s", 0.10);
    governor_force_trigger_n_ =
        declare_parameter<double>("governor_force_trigger_n", 3.0);
    governor_force_clear_n_ =
        declare_parameter<double>("governor_force_clear_n", 1.5);
    governor_torque_trigger_nm_ =
        declare_parameter<double>("governor_torque_trigger_nm", 0.15);
    governor_torque_clear_nm_ =
        declare_parameter<double>("governor_torque_clear_nm", 0.08);
    recovery_clear_hold_s_ =
        declare_parameter<double>("recovery_clear_hold_s", 0.20);
    recovery_timeout_s_ = declare_parameter<double>("recovery_timeout_s", 8.0);
    recovery_resume_offset_ = Vector6d(declare_parameter<std::vector<double>>(
        "recovery_resume_offset",
        {0.00025, 0.00010, 0.00015, 0.00174533, 0.00261799, 0.00087266}).data());

    uncorrectable_hold_s_ = declare_parameter<double>("uncorrectable_hold_s", 0.50);
    uncorrectable_margin_n_ = declare_parameter<double>("uncorrectable_margin_n", 3.0);
    saturation_hold_s_ = declare_parameter<double>("saturation_hold_s", 0.80);
    admittance_enable_progress_ =
        declare_parameter<double>("admittance_enable_progress", 0.0);

    error_injection_end_progress_ =
        declare_parameter<double>("error_injection_end_progress", 0.15);
    centering_contact_force_n_ =
        declare_parameter<double>("centering_contact_force_n", 1.5);
    centering_contact_hold_s_ =
        declare_parameter<double>("centering_contact_hold_s", 0.05);

    seat_enable_progress_ = declare_parameter<double>("seat_enable_progress", 0.85);
    seat_target_force_n_ = declare_parameter<double>("seat_target_force_n", 25.0);
    seat_force_axis_ = declare_parameter<int>("seat_force_axis", 2);
    seat_force_sign_ = declare_parameter<double>("seat_force_sign", -1.0);
    seat_hold_s_ = declare_parameter<double>("seat_hold_s", 0.05);
    require_seat_force_ = declare_parameter<bool>("require_seat_force", false);

    hard_force_n_ = declare_parameter<double>("hard_force_n", 45.0);
    hard_torque_nm_ = declare_parameter<double>("hard_torque_nm", 1.50);

    transform_.controlled_p_sensor = ar_admittance_control::vector3(
        declare_parameter<std::vector<double>>(
            "tool_to_sensor_translation_m", {0.0, 0.0, 0.0}),
        "tool_to_sensor_translation_m");
    transform_.controlled_R_sensor = ar_admittance_control::rpyToRotation(
        declare_parameter<std::vector<double>>(
            "tool_to_sensor_rpy_rad", {0.0, 0.0, 0.0}));
    transform_.sign = Vector6d::Ones();
    transform_.enabled = Vector6d::Ones();

    receiver_ = std::make_shared<ar_admittance_control::WrenchReceiver>(
        *this, wrench_topic_, wrench_timeout_s_);

    validateParameters();
  }

  int run() {
    PointFile point_file;
    try {
      point_file = loadPointFile(points_file_);
    } catch (const std::exception &exc) {
      RCLCPP_ERROR(get_logger(), "Failed to load points: %s", exc.what());
      return 2;
    }

    NominalTrajectory centered_trajectory(point_file, Vector6d::Zero(), speed_scale_);
    NominalTrajectory perturbed_trajectory(point_file, trajectory_error_, speed_scale_);
    printPlan(centered_trajectory);

    RCLCPP_INFO(get_logger(), "Waiting for force topic %s...", wrench_topic_.c_str());
    if (!receiver_->waitForData(5.0)) {
      RCLCPP_ERROR(get_logger(), "Timeout waiting for wrench topic: %s", wrench_topic_.c_str());
      return 3;
    }

    std::string tare_reason;
    RCLCPP_INFO(get_logger(), "Collecting 3 s tare (keep end-effector still)...");
    if (!receiver_->tare(3.0, 3.0, 0.3, tare_reason, 25)) {
      RCLCPP_ERROR(get_logger(), "Tare failed: %s", tare_reason.c_str());
      return 4;
    }
    const Vector6d bias = receiver_->bias();
    RCLCPP_INFO(get_logger(),
                "Tare complete: bias F=[%+.2f %+.2f %+.2f N], M=[%+.3f %+.3f %+.3f Nm]",
                bias[0], bias[1], bias[2], bias[3], bias[4], bias[5]);

    if (active_control_) {
      return runActive(point_file, centered_trajectory, perturbed_trajectory);
    }
    return runShadow(point_file, centered_trajectory, perturbed_trajectory);
  }

 private:
  void validateParameters() {
    const std::size_t profile_size = profile_progress_.size();
    if (profile_size < 2 || normal_force_upper_n_.size() != profile_size) {
      throw std::invalid_argument("normal envelope progress/upper size mismatch");
    }
    for (std::size_t i = 1; i < profile_size; ++i) {
      if (profile_progress_[i] <= profile_progress_[i - 1]) {
        throw std::invalid_argument("normal_profile_progress must be strictly increasing");
      }
    }
    for (std::size_t axis = 0; axis < 6; ++axis) {
      if (normal_center_profile_[axis].size() != profile_size ||
          normal_half_width_profile_[axis].size() != profile_size) {
        throw std::invalid_argument("normal center/half-width size mismatch");
      }
    }
  }

  void printPlan(const NominalTrajectory &trajectory) const {
    RCLCPP_INFO(get_logger(), "Trajectory has %zu points, duration %.1f s",
                trajectory.points().size(), trajectory.duration());
    for (std::size_t i = 0; i < trajectory.points().size(); ++i) {
      const auto pose = sixFromPose(trajectory.points()[i].pose);
      RCLCPP_INFO(get_logger(), "  Point %zu xyz=[%.3f, %.3f, %.3f] mm",
                  i, pose[0] * 1000.0, pose[1] * 1000.0, pose[2] * 1000.0);
    }
  }

  void selectTool(rokae::StandardRobot &robot) const {
    std::error_code ec;
    robot.setToolset(tool_, workobject_, ec);
    ar_admittance_control::requireOk(ec, "select tool/workobject");
  }

  void checkPath(rokae::StandardRobot &robot,
                 const PointRecord &start_point,
                 const NominalTrajectory &trajectory,
                 const char *description) const {
    std::vector<double> start_joints(start_point.joints.begin(), start_point.joints.end());
    std::vector<rokae::CartesianPosition> path;
    for (const auto &pt : trajectory.points()) {
      path.push_back(controllerPoint(pt));
    }
    std::vector<double> target_joints;
    std::error_code ec;
    const int failed = robot.checkPath(start_joints, path, target_joints, ec);
    if (ec || target_joints.size() < 6) {
      throw std::runtime_error("checkPath failed at point " +
                               std::to_string(failed) + ": " + ec.message());
    }
    RCLCPP_INFO(get_logger(), "Controller checkPath (%s): PASS", description);
  }

  int runShadow(const PointFile &point_file,
                const NominalTrajectory &trajectory,
                const NominalTrajectory &perturbed_trajectory) {
    (void)perturbed_trajectory;
    RCLCPP_WARN(get_logger(), "==========================================================");
    RCLCPP_WARN(get_logger(), "SHADOW MODE: Robot will NOT power on and will NOT move.");
    RCLCPP_WARN(get_logger(), "Simulating nominal trajectory progress while listening to");
    RCLCPP_WARN(get_logger(), "real TA67L force sensor and computing admittance response.");
    RCLCPP_WARN(get_logger(), "Push sensor by hand to test direction and envelope logic.");
    RCLCPP_WARN(get_logger(), "==========================================================");

    rokae::StandardRobot robot;
    bool robot_connected = false;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      selectTool(robot);
      checkPath(robot, point_file.points.front(), trajectory, "nominal centered");
      if (trajectory_error_.cwiseAbs().maxCoeff() > 1e-6) {
        checkPath(robot, point_file.points.front(), perturbed_trajectory, "perturbed test path");
      }
      robot_connected = true;
      RCLCPP_INFO(get_logger(), "Connected to XB7 controller at %s", robot_ip_.c_str());
    } catch (const std::exception &e) {
      RCLCPP_WARN(get_logger(), "Robot connection skipped in SHADOW: %s", e.what());
    }

    if (trajectory_error_.cwiseAbs().maxCoeff() > 1e-6) {
      RCLCPP_INFO(get_logger(),
                  "Perturbation error enabled: X=%+.3f mm, Y=%+.3f mm, Z=%+.3f mm",
                  trajectory_error_[0] * 1000.0,
                  trajectory_error_[1] * 1000.0,
                  trajectory_error_[2] * 1000.0);
    } else {
      RCLCPP_INFO(get_logger(), "Running with 0 perturbation error (nominal path).");
    }

    const auto start_time = Clock::now();
    auto next_log = start_time;
    double sim_time_s = 0.0;
    ar_admittance_control::Admittance6D admittance_sim = admittance_;

    bool centering_started = (trajectory_error_.cwiseAbs().maxCoeff() < 1e-12);
    int centering_contact_cycles = 0;
    const int centering_contact_hold_cycles =
        std::max(1, static_cast<int>(std::round(centering_contact_hold_s_ / 0.01)));

    while (rclcpp::ok() && !ar_admittance_control::stop_requested.load()) {
      const auto now = Clock::now();
      const double elapsed_s = std::chrono::duration<double>(now - start_time).count();
      if (elapsed_s >= duration_shadow_s_) break;

      sim_time_s = std::min(elapsed_s, trajectory.duration());
      const double progress = trajectory.duration() > 0.0 ? sim_time_s / trajectory.duration() : 1.0;

      const Vector6d wrench_raw = receiver_->corrected();
      const double f_total = wrench_raw.head<3>().norm();

      // Envelope evaluation
      Vector6d excess_wrench = Vector6d::Zero();
      for (std::size_t axis = 0; axis < 6; ++axis) {
        const double center = interpolateProfile(
            profile_progress_, normal_center_profile_[axis], progress);
        const double half_w = interpolateProfile(
            profile_progress_, normal_half_width_profile_[axis], progress);
        const double low = std::min(center - half_w, 0.0);
        const double high = std::max(center + half_w, 0.0);
        const double val = wrench_raw[axis];
        if (val > high) excess_wrench[axis] = val - high;
        else if (val < low) excess_wrench[axis] = val - low;
      }

      if (!centering_started) {
        if (f_total >= centering_contact_force_n_) {
          ++centering_contact_cycles;
          if (centering_contact_cycles >= centering_contact_hold_cycles) {
            centering_started = true;
            RCLCPP_INFO(get_logger(),
                        "Centering triggered by contact force (|F|=%.2fN >= %.2fN) at progress %.2f",
                        f_total, centering_contact_force_n_, progress);
          }
        } else {
          centering_contact_cycles = 0;
        }
        if (progress >= error_injection_end_progress_) {
          centering_started = true;
          RCLCPP_INFO(get_logger(),
                      "Centering triggered by progress threshold (%.2f) at progress %.2f",
                      error_injection_end_progress_, progress);
        }
      }

      constexpr double dt = 0.01;
      if (!centering_started) {
        const double phase = progress / error_injection_end_progress_;
        const double duration = error_injection_end_progress_ * trajectory.duration();
        const double gain = smoothStep(phase);
        admittance_sim.position = gain * trajectory_error_;
        admittance_sim.velocity =
            (smoothStepDerivative(phase) / duration) * trajectory_error_;
        admittance_sim.filtered_input.setZero();
      } else {
        const Vector6d force_applied = wrench_to_motion_sign_.cwiseProduct(excess_wrench);
        admittance_sim.step(force_applied, dt);
      }

      if (now >= next_log) {
        next_log = now + std::chrono::milliseconds(200);
        RCLCPP_INFO(get_logger(),
                    "[%s] p=%.2f (t=%.1fs) | F=[%+.2f, %+.2f, %+.2f]N (|F|=%.2fN) | "
                    "ExcessF=[%+.2f, %+.2f, %+.2f]N | OffsetXYZ=[%+.3f, %+.3f, %+.3f]mm",
                    phaseName(progress), progress, sim_time_s,
                    wrench_raw[0], wrench_raw[1], wrench_raw[2], f_total,
                    excess_wrench[0], excess_wrench[1], excess_wrench[2],
                    admittance_sim.position[0] * 1000.0,
                    admittance_sim.position[1] * 1000.0,
                    admittance_sim.position[2] * 1000.0);
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (robot_connected) {
      std::error_code ec;
      robot.disconnectFromRobot(ec);
    }
    RCLCPP_INFO(get_logger(), "SHADOW test finished cleanly.");
    return 0;
  }

  int runActive(const PointFile &point_file,
                const NominalTrajectory &trajectory,
                const NominalTrajectory &perturbed_trajectory) {
    if (!sensor_mounted_) {
      RCLCPP_ERROR(get_logger(), "Set sensor_mounted_to_robot=true before active motion");
      return 5;
    }

    rokae::StandardRobot robot;
    std::shared_ptr<rokae::RtMotionControlIndustrial<6>> controller;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      selectTool(robot);
      checkPath(robot, point_file.points.front(), trajectory, "nominal centered");
      if (trajectory_error_.cwiseAbs().maxCoeff() > 1e-6) {
        checkPath(robot, point_file.points.front(), perturbed_trajectory, "perturbed test path");
      }

      const std::string arm_token = "ARM_XB7_ACTIVE";
      std::cout << "\n======================================================\n"
                << "CAUTION: ACTIVE XB7 6D CARTESIAN ADMITTANCE CONTROL!\n"
                << "Robot will power on and execute trajectory with live force feedback.\n";
      if (trajectory_error_.cwiseAbs().maxCoeff() > 1e-6) {
        std::cout << "Injected perturbation error [mm / deg]: "
                  << "X=" << trajectory_error_[0] * 1000.0 << " mm, "
                  << "Y=" << trajectory_error_[1] * 1000.0 << " mm, "
                  << "Z=" << trajectory_error_[2] * 1000.0 << " mm\n";
      } else {
        std::cout << "No perturbation error injected (nominal centered path).\n";
      }
      std::cout << "Hold E-STOP reachable at all times.\n"
                << "Type '" << arm_token << "' to proceed: " << std::flush;
      std::string input;
      std::getline(std::cin, input);
      if (input != arm_token) {
        RCLCPP_WARN(get_logger(), "Aborted; robot not armed.");
        return 0;
      }

      std::array<double[2], 6> soft_limits{};
      ar_admittance_control::checkSoftLimits(
          robot, soft_limits, soft_limit_margin_deg_ * kDeg);
      ar_admittance_control::powerInNonRealtime(robot);
      ar_admittance_control::switchToRealtime(robot);

      controller = robot.getRtMotionController().lock();
      if (!controller) throw std::runtime_error("failed to get RT controller handle");

      robot.startReceiveRobotState(
          std::chrono::milliseconds(1),
          {rokae::RtSupportedFields::tcpPose_m,
           rokae::RtSupportedFields::tcpPose_c,
           rokae::RtSupportedFields::jointPos_m});

      std::array<double, 16> base_safe_array{};
      std::array<double, 6> start_joints{};
      if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m, base_safe_array) != 0 ||
          robot.getStateData(rokae::RtSupportedFields::jointPos_m, start_joints) != 0) {
        throw std::runtime_error("read initial RT state failed");
      }

      const Eigen::Isometry3d base_safe =
          ar_admittance_control::rowMajorToEigen(base_safe_array);
      const Eigen::Isometry3d ref_safe = trajectory.points().front().pose;
      const Eigen::Isometry3d base_ref = base_safe * ref_safe.inverse();

      ar_admittance_control::Admittance6D admittance_active = admittance_;
      double trajectory_elapsed_s = 0.0;
      std::atomic<int> fault{0};
      Clock::time_point started = Clock::now();
      bool first_cycle = true;

      bool centering_started = (trajectory_error_.cwiseAbs().maxCoeff() < 1e-12);
      int centering_contact_cycles = 0;
      const int centering_contact_hold_cycles =
          std::max(1, static_cast<int>(std::round(centering_contact_hold_s_ / ar_admittance_control::kControlDt)));

      std::function<rokae::CartesianPosition()> callback = [&]() {
        rokae::CartesianPosition command{};
        command.pos = base_safe_array;
        command.hasElbow = false;

        const Vector6d wrench = receiver_->corrected();
        if (!receiver_->fresh() || !wrench.allFinite()) {
          fault.store(1);
          command.setFinished();
          return command;
        }

        const double force_norm = wrench.head<3>().norm();
        const double torque_norm = wrench.tail<3>().norm();
        if (force_norm >= hard_force_n_ || torque_norm >= hard_torque_nm_) {
          fault.store(2);
          command.setFinished();
          return command;
        }

        if (first_cycle) {
          started = Clock::now();
          first_cycle = false;
        }

        const double progress = std::clamp(
            trajectory.duration() > 0.0 ? trajectory_elapsed_s / trajectory.duration() : 1.0,
            0.0, 1.0);

        // Check envelope
        Vector6d excess_wrench = Vector6d::Zero();
        for (std::size_t axis = 0; axis < 6; ++axis) {
          const double center = interpolateProfile(
              profile_progress_, normal_center_profile_[axis], progress);
          const double half_w = interpolateProfile(
              profile_progress_, normal_half_width_profile_[axis], progress);
          const double low = std::min(center - half_w, 0.0);
          const double high = std::max(center + half_w, 0.0);
          const double val = wrench[axis];
          if (val > high) excess_wrench[axis] = val - high;
          else if (val < low) excess_wrench[axis] = val - low;
        }

        // Apply masks
        const auto it_mask = phase_masks_.find(phaseName(progress));
        const Vector6d mask = it_mask != phase_masks_.end() ? it_mask->second : Vector6d::Ones();
        excess_wrench = excess_wrench.cwiseProduct(mask);

        if (!centering_started) {
          if (force_norm >= centering_contact_force_n_) {
            ++centering_contact_cycles;
            if (centering_contact_cycles >= centering_contact_hold_cycles) {
              centering_started = true;
            }
          } else {
            centering_contact_cycles = 0;
          }
          if (progress >= error_injection_end_progress_) {
            centering_started = true;
          }
        }

        // Governor: slow down trajectory if excess force is high
        double traj_rate = 1.0;
        if (trajectory_governor_enabled_ && excess_wrench.head<3>().norm() > governor_force_trigger_n_) {
          traj_rate = 0.2;
        }
        trajectory_elapsed_s += ar_admittance_control::kControlDt * traj_rate;

        // Admittance step or error injection
        if (!centering_started) {
          const double phase = progress / error_injection_end_progress_;
          const double duration = error_injection_end_progress_ * trajectory.duration();
          const double gain = smoothStep(phase);
          admittance_active.position = gain * trajectory_error_;
          admittance_active.velocity =
              (smoothStepDerivative(phase) / duration) * trajectory_error_;
          admittance_active.filtered_input.setZero();
        } else {
          const Vector6d force_applied = wrench_to_motion_sign_.cwiseProduct(excess_wrench);
          admittance_active.step(force_applied, ar_admittance_control::kControlDt);
        }

        // Compute final target pose
        const PlanPoint plan_pt = trajectory.sample(trajectory_elapsed_s);
        Eigen::Isometry3d target_in_ref = plan_pt.pose;
        target_in_ref.translation() += admittance_active.position.head<3>();
        target_in_ref.linear() =
            ar_admittance_control::rotationVectorToMatrix(admittance_active.position.tail<3>()) *
            target_in_ref.linear();

        const Eigen::Isometry3d target_in_base = base_ref * target_in_ref;
        command.pos = ar_admittance_control::eigenToRowMajor(target_in_base);

        if (trajectory_elapsed_s >= trajectory.duration() + 2.0) {
          command.setFinished();
        }
        return command;
      };

      RCLCPP_INFO(get_logger(), "Starting real-time control loop...");
      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::cartesianPosition);
      controller->startLoop(true);

      if (fault.load() != 0) {
        RCLCPP_ERROR(get_logger(), "Real-time loop terminated with fault code %d", fault.load());
      } else {
        RCLCPP_INFO(get_logger(), "Real-time assembly completed successfully!");
      }

      ar_admittance_control::safeShutdown(robot, controller);
    } catch (const std::exception &exc) {
      RCLCPP_ERROR(get_logger(), "Active control error: %s", exc.what());
      ar_admittance_control::safeShutdown(robot, controller);
      return 1;
    }
    return 0;
  }

  bool active_control_{false};
  bool sensor_mounted_{false};
  std::string robot_ip_;
  std::string local_ip_;
  std::string tool_;
  std::string workobject_;
  std::string wrench_topic_;
  std::string points_file_;
  Vector6d trajectory_error_{Vector6d::Zero()};
  bool preload_error_at_safe_{false};
  double preload_error_duration_s_{10.0};
  double speed_scale_{1.0};
  double duration_shadow_s_{60.0};
  double wrench_timeout_s_{0.20};
  double soft_limit_margin_deg_{3.0};

  ar_admittance_control::Admittance6D admittance_;
  Vector6d min_offset_{Vector6d::Zero()};
  Vector6d max_offset_{Vector6d::Zero()};
  Vector6d wrench_to_motion_sign_{Vector6d::Ones()};
  std::map<std::string, Vector6d> phase_masks_;

  std::vector<double> profile_progress_;
  std::vector<double> normal_force_upper_n_;
  std::array<std::vector<double>, 6> normal_center_profile_;
  std::array<std::vector<double>, 6> normal_half_width_profile_;

  double excess_hold_s_{0.10};
  bool trajectory_governor_enabled_{true};
  double trajectory_rate_ramp_per_s_{4.0};
  double governor_trigger_hold_s_{0.10};
  double governor_force_trigger_n_{3.0};
  double governor_force_clear_n_{1.5};
  double governor_torque_trigger_nm_{0.15};
  double governor_torque_clear_nm_{0.08};
  double recovery_clear_hold_s_{0.20};
  double recovery_timeout_s_{8.0};
  Vector6d recovery_resume_offset_{Vector6d::Zero()};

  double uncorrectable_hold_s_{0.50};
  double uncorrectable_margin_n_{3.0};
  double saturation_hold_s_{0.80};
  double admittance_enable_progress_{0.0};

  double error_injection_end_progress_{0.15};
  double centering_contact_force_n_{1.5};
  double centering_contact_hold_s_{0.05};

  double seat_enable_progress_{0.85};
  double seat_target_force_n_{25.0};
  int seat_force_axis_{2};
  double seat_force_sign_{-1.0};
  double seat_hold_s_{0.05};
  bool require_seat_force_{false};

  double hard_force_n_{45.0};
  double hard_torque_nm_{1.50};

  ar_admittance_control::WrenchTransform transform_;
  std::shared_ptr<ar_admittance_control::WrenchReceiver> receiver_;
};

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, ar_admittance_control::requestStop);
  std::signal(SIGTERM, ar_admittance_control::requestStop);
  rclcpp::init(argc, argv);
  auto node = std::make_shared<XB7AssemblyCartesian6DAdmittanceNode>();
  std::thread spin_thread([node]() {
    rclcpp::spin(node);
  });

  const int result = node->run();
  rclcpp::shutdown();
  if (spin_thread.joinable()) spin_thread.join();
  return result;
}
