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

class NominalTrajectory {
 public:
  NominalTrajectory(const TaughtPoint &safe, const TaughtPoint &edge,
                    double x_error_m, double speed_scale) {
    PlanPoint p_safe{poseFromSix(safe.pose), safe.elbow};

    std::array<double, 6> back_six{};
    for (std::size_t i = 0; i < 3; ++i) {
      back_six[i] = kBackP6MmDeg[i] * 0.001;
      back_six[3 + i] = edge.pose[3 + i];
    }
    back_six[2] = edge.pose[2] + kPreInsertLiftM;
    back_six[0] += x_error_m;
    PlanPoint p_back{poseFromSix(back_six), edge.elbow};

    auto edge_six = edge.pose;
    edge_six[0] += x_error_m;
    PlanPoint p_edge{poseFromSix(edge_six), edge.elbow};

    std::array<double, 6> press_six{};
    for (std::size_t i = 0; i < 3; ++i) {
      press_six[i] = kFinalP8MmDeg[i] * 0.001;
      press_six[3 + i] = kFinalP8MmDeg[3 + i] * kDeg;
    }
    press_six[0] += x_error_m;
    PlanPoint p_press{poseFromSix(press_six), kFinalP8Elbow};

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

class AssemblyXAdmittanceNode final : public rclcpp::Node {
 public:
  AssemblyXAdmittanceNode()
      : Node("ar_assembly_x_admittance_node") {
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
    x_error_m_ = declare_parameter<double>("x_error_m", 0.0001);
    speed_scale_ = declare_parameter<double>("speed_scale", 0.5);
    force_to_motion_sign_ =
        declare_parameter<double>("force_to_motion_sign", 1.0);
    duration_shadow_s_ = declare_parameter<double>("shadow_duration_s", 20.0);
    wrench_timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.05);

    mass_ = declare_parameter<double>("x_virtual_mass", 5.0);
    damping_ = declare_parameter<double>("x_damping", 150.0);
    stiffness_ = declare_parameter<double>("x_stiffness", 5000.0);
    deadband_n_ = declare_parameter<double>("x_deadband_n", 0.5);
    contact_n_ = declare_parameter<double>("x_contact_n", 1.0);
    max_offset_m_ = declare_parameter<double>("x_max_offset_m", 0.0003);
    max_velocity_m_s_ =
        declare_parameter<double>("x_max_velocity_m_s", 0.0005);
    max_acceleration_m_s2_ =
        declare_parameter<double>("x_max_acceleration_m_s2", 0.02);
    soft_force_n_ = declare_parameter<double>("soft_force_n", 27.0);
    hard_force_n_ = declare_parameter<double>("hard_force_n", 30.0);
    hard_torque_nm_ =
        declare_parameter<double>("hard_torque_nm", 1.25);

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
        "Mode=%s; trajectory error=workobject X %+.3f mm; only X admittance "
        "is enabled; hard limits %.1f N / %.2f Nm.",
        active_ ? "ACTIVE" : "SHADOW", x_error_m_ * 1000.0,
        hard_force_n_, hard_torque_nm_);
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
    NominalTrajectory trajectory(points.at("P_SAFE"),
                                 points.at("P_EDGE_IN"), x_error_m_,
                                 speed_scale_);
    printPlan(trajectory);
    return active_ ? runActive(points, trajectory)
                   : runShadow(points, trajectory);
  }

 private:
  void validate() const {
    if (points_file_.empty() || std::abs(x_error_m_) > 0.0005 ||
        speed_scale_ <= 0.0 || speed_scale_ > 1.0 ||
        std::abs(std::abs(force_to_motion_sign_) - 1.0) > 1e-9 ||
        mass_ <= 0.0 || damping_ <= 0.0 || stiffness_ <= 0.0 ||
        deadband_n_ < 0.0 || contact_n_ <= deadband_n_ ||
        max_offset_m_ <= 0.0 || max_offset_m_ > 0.0005 ||
        max_velocity_m_s_ <= 0.0 || max_velocity_m_s_ > 0.001 ||
        max_acceleration_m_s2_ <= 0.0 || max_acceleration_m_s2_ > 0.05 ||
        soft_force_n_ <= 0.0 || hard_force_n_ <= soft_force_n_ ||
        hard_torque_nm_ <= 0.0) {
      throw std::invalid_argument("invalid or unsafe X-admittance parameters");
    }
  }

  void printPlan(const NominalTrajectory &trajectory) const {
    static const std::array<const char *, 4> labels{
        "P_SAFE(no error)", "P_BACK_LOW(+X error)",
        "P_EDGE_IN(+X error)", "P8(+X error)"};
    RCLCPP_INFO(get_logger(), "Nominal duration %.1f s", trajectory.duration());
    for (std::size_t i = 0; i < trajectory.points().size(); ++i) {
      const auto pose = sixFromPose(trajectory.points()[i].pose);
      RCLCPP_INFO(get_logger(), "%s xyz=[%.3f %.3f %.3f] mm",
                  labels[i], pose[0] * 1000.0, pose[1] * 1000.0,
                  pose[2] * 1000.0);
    }
  }

  void selectTool(rokae::ArRobot &robot) const {
    std::error_code ec;
    robot.setToolset(tool_, workobject_, ec);
    ar_admittance_control::requireOk(ec, "select tool/workobject");
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
                 const NominalTrajectory &trajectory) const {
    std::vector<double> start(safe.joints.begin(), safe.joints.end());
    std::vector<rokae::CartesianPosition> path;
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
    RCLCPP_INFO(get_logger(), "Controller checkPath: PASS");
  }

  int runShadow(const std::map<std::string, TaughtPoint> &points,
                const NominalTrajectory &trajectory) {
    (void)trajectory;
    rokae::ArRobot robot;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      selectTool(robot);
      checkPath(robot, points.at("P_SAFE"), trajectory);
      RCLCPP_WARN(get_logger(),
                  "SHADOW: no power or motion. Push gently along workobject X "
                  "and verify Fx sign before ACTIVE.");
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
        const Eigen::Vector3d force_ref =
            t_ref_tool.linear() * tool.head<3>();
        if (Clock::now() >= next_log) {
          RCLCPP_INFO(get_logger(),
                      "F_workobject=[%+.2f %+.2f %+.2f] N; selected Fx=%+.2f "
                      "N; motion_sign=%+.0f",
                      force_ref.x(), force_ref.y(), force_ref.z(),
                      force_ref.x(), force_to_motion_sign_);
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
      case 2: return "30 N / torque hard limit";
      case 3: return "27 N soft force held for 30 ms";
      case 4: return "robot state read failure";
      case 5: return "TCP tracking envelope";
      case 6: return "X correction saturated while lateral force remained";
      default: return "unknown";
    }
  }

  int runActive(const std::map<std::string, TaughtPoint> &points,
                const NominalTrajectory &trajectory) {
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
      checkPath(robot, points.at("P_SAFE"), trajectory);

      std::cout
          << "ACTIVE X-ADMITTANCE: +0.1 mm workobject-X trajectory error.\n"
          << "Only X correction is enabled; maximum correction is 0.3 mm.\n"
          << "Verify SHADOW sign, clear workspace, hold E-stop.\n"
          << "Type ARM_X_ERROR_ADMIT exactly: " << std::flush;
      std::string confirmation;
      std::getline(std::cin, confirmation);
      if (confirmation != "ARM_X_ERROR_ADMIT") {
        RCLCPP_WARN(get_logger(), "Cancelled; robot was not powered on");
        return 0;
      }
      std::string quiet_reason;
      if (!receiver_->verifyCorrectedQuiet(1.0, 3.0, 0.3, quiet_reason)) {
        throw std::runtime_error("pre-arm quiet check: " + quiet_reason);
      }

      std::array<double[2], 7> soft_limits{};
      ar_admittance_control::checkSoftLimits(robot, soft_limits, 10.0 * kDeg);
      ar_admittance_control::powerInNonRealtime(robot);
      ar_admittance_control::switchToRealtime(robot);
      controller = robot.getRtMotionController().lock();
      if (!controller) throw std::runtime_error("RT controller handle expired");

      robot.startReceiveRobotState(
          std::chrono::milliseconds(1),
          {rokae::RtSupportedFields::tcpPose_m,
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
      std::atomic<double> last_fx_ref{0.0};
      double correction = 0.0;
      double velocity = 0.0;
      double filtered_fx = 0.0;
      int soft_cycles = 0;
      int saturated_cycles = 0;
      bool contact = false;
      const auto started = Clock::now();

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
        soft_cycles = force_norm >= soft_force_n_ ? soft_cycles + 1 : 0;
        if (soft_cycles >= 30) {
          fault.store(3);
          command.setFinished();
          return command;
        }

        std::array<double, 16> measured_array{};
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

        const Eigen::Isometry3d measured =
            ar_admittance_control::rowMajorToEigen(measured_array);
        const Eigen::Isometry3d ref_measured = base_ref.inverse() * measured;
        const Vector6d tool_wrench = transform_.apply(corrected);
        const Eigen::Vector3d force_ref =
            ref_measured.linear() * tool_wrench.head<3>();
        const double fx = force_ref.x();
        last_fx_ref.store(fx);
        contact = contact || std::abs(fx) >= contact_n_;

        if (contact) {
          const double alpha = 1.0 - std::exp(-2.0 * kPi * 10.0 * 0.001);
          filtered_fx += alpha * (fx - filtered_fx);
          const double input =
              force_to_motion_sign_ *
              ar_admittance_control::applyDeadband(filtered_fx, deadband_n_);
          double acceleration =
              (input - damping_ * velocity - stiffness_ * correction) /
              mass_;
          acceleration = std::clamp(acceleration, -max_acceleration_m_s2_,
                                    max_acceleration_m_s2_);
          velocity = std::clamp(velocity + acceleration * 0.001,
                                -max_velocity_m_s_, max_velocity_m_s_);
          correction = std::clamp(correction + velocity * 0.001,
                                  -max_offset_m_, max_offset_m_);
          if (std::abs(correction) >= 0.999 * max_offset_m_ &&
              std::abs(fx) > 2.0) {
            ++saturated_cycles;
          } else {
            saturated_cycles = 0;
          }
          if (saturated_cycles >= 500) {
            fault.store(6);
            command.setFinished();
            return command;
          }
        }

        const double elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        PlanPoint nominal = trajectory.sample(elapsed);
        nominal.pose.translation().x() += correction;
        const Eigen::Isometry3d desired = base_ref * nominal.pose;
        const double tracking =
            (desired.translation() - measured.translation()).norm();
        const Eigen::AngleAxisd rotation_error(
            measured.linear().transpose() * desired.linear());
        if (tracking > 0.005 || std::abs(rotation_error.angle()) > 3.0 * kDeg) {
          fault.store(5);
          command.setFinished();
          return command;
        }
        command.pos = ar_admittance_control::eigenToRowMajor(desired);
        command.elbow = nominal.elbow;
        command.hasElbow = true;
        if (ar_admittance_control::stop_requested.load() ||
            elapsed >= trajectory.duration() + 0.5) {
          command.setFinished();
        }
        return command;
      };

      RCLCPP_WARN(get_logger(),
                  "ARMED: +%.3f mm X error, X correction max %.3f mm, "
                  "duration %.1f s.",
                  x_error_m_ * 1000.0, max_offset_m_ * 1000.0,
                  trajectory.duration());
      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::cartesianPosition);
      controller->startLoop(true);
      if (fault.load() != 0) {
        RCLCPP_ERROR(get_logger(), "WATCHDOG STOP: %s", faultText(fault.load()));
      }
      RCLCPP_INFO(get_logger(),
                  "Result: correction X=%+.3f mm, Fx_ref=%+.2f N, "
                  "max force=%.2f N, max torque=%.3f Nm",
                  correction * 1000.0, last_fx_ref.load(), max_force.load(),
                  max_torque.load());
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
  double x_error_m_{0.0001};
  double speed_scale_{0.5};
  double force_to_motion_sign_{1.0};
  double duration_shadow_s_{20.0};
  double wrench_timeout_s_{0.05};
  double mass_{5.0};
  double damping_{150.0};
  double stiffness_{5000.0};
  double deadband_n_{0.5};
  double contact_n_{1.0};
  double max_offset_m_{0.0003};
  double max_velocity_m_s_{0.0005};
  double max_acceleration_m_s2_{0.02};
  double soft_force_n_{27.0};
  double hard_force_n_{30.0};
  double hard_torque_nm_{1.25};
  ar_admittance_control::WrenchTransform transform_;
  std::unique_ptr<ar_admittance_control::WrenchReceiver> receiver_;
};

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, ar_admittance_control::requestStop);
  std::signal(SIGTERM, ar_admittance_control::requestStop);
  rclcpp::init(argc, argv);
  try {
    const auto node = std::make_shared<AssemblyXAdmittanceNode>();
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
