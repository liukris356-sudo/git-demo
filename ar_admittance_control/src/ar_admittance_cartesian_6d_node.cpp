#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "ar_admittance_control/admittance_common.hpp"

namespace {

using ar_admittance_control::Admittance6D;
using ar_admittance_control::Clock;
using ar_admittance_control::Vector6d;
using ar_admittance_control::WrenchReceiver;
using ar_admittance_control::WrenchSafety;
using ar_admittance_control::WrenchTransform;
constexpr double kDeg = ar_admittance_control::kPi / 180.0;

class CartesianAdmittance6DNode final : public rclcpp::Node {
 public:
  CartesianAdmittance6DNode() : Node("ar_admittance_cartesian_6d_node") {
    active_control_ = declare_parameter<bool>("active_control", false);
    sensor_mounted_ =
        declare_parameter<bool>("sensor_mounted_to_robot", false);
    robot_ip_ = declare_parameter<std::string>("robot_ip", "192.168.2.160");
    local_ip_ = declare_parameter<std::string>("local_ip", "192.168.2.100");
    wrench_topic_ =
        declare_parameter<std::string>("wrench_topic", "/m3815/wrench_raw");
    duration_s_ = declare_parameter<double>("duration_s", 15.0);
    wrench_timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.05);
    tare_duration_s_ = declare_parameter<double>("tare_duration_s", 2.0);
    tare_force_range_n_ =
        declare_parameter<double>("tare_force_range_n", 3.0);
    tare_torque_range_nm_ =
        declare_parameter<double>("tare_torque_range_nm", 0.3);
    arm_quiet_force_n_ =
        declare_parameter<double>("arm_quiet_force_n", 3.0);
    arm_quiet_torque_nm_ =
        declare_parameter<double>("arm_quiet_torque_nm", 0.5);

    const auto mass = declare_parameter<std::vector<double>>(
        "virtual_mass", {30.0, 30.0, 30.0, 1.5, 1.5, 1.5});
    const auto damping = declare_parameter<std::vector<double>>(
        "damping", {250.0, 250.0, 250.0, 12.0, 12.0, 12.0});
    const auto stiffness = declare_parameter<std::vector<double>>(
        "stiffness", {1000.0, 1000.0, 1000.0, 30.0, 30.0, 30.0});
    const auto deadband = declare_parameter<std::vector<double>>(
        "deadband", {1.5, 1.5, 1.5, 0.12, 0.12, 0.12});
    const auto max_position = declare_parameter<std::vector<double>>(
        "max_offset", {0.010, 0.010, 0.010, 3.0 * kDeg, 3.0 * kDeg,
                       3.0 * kDeg});
    const auto max_velocity = declare_parameter<std::vector<double>>(
        "max_velocity", {0.010, 0.010, 0.010, 5.0 * kDeg, 5.0 * kDeg,
                         5.0 * kDeg});
    const auto max_acceleration = declare_parameter<std::vector<double>>(
        "max_acceleration", {0.20, 0.20, 0.20, 1.0, 1.0, 1.0});
    const auto enabled = declare_parameter<std::vector<double>>(
        "enabled_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0});
    admittance_.mass = ar_admittance_control::vector6(mass, "virtual_mass");
    admittance_.damping = ar_admittance_control::vector6(damping, "damping");
    admittance_.stiffness =
        ar_admittance_control::vector6(stiffness, "stiffness");
    admittance_.deadband =
        ar_admittance_control::vector6(deadband, "deadband");
    admittance_.max_position =
        ar_admittance_control::vector6(max_position, "max_offset");
    admittance_.max_velocity =
        ar_admittance_control::vector6(max_velocity, "max_velocity");
    admittance_.max_acceleration = ar_admittance_control::vector6(
        max_acceleration, "max_acceleration");
    admittance_.enabled =
        ar_admittance_control::vector6(enabled, "enabled_axes");
    admittance_.filter_cutoff_hz =
        declare_parameter<double>("filter_cutoff_hz", 10.0);
    admittance_.validate();

    const auto tool_to_sensor_xyz = declare_parameter<std::vector<double>>(
        "tool_to_sensor_translation_m", {0.0, 0.0, 0.0});
    const auto tool_to_sensor_rpy = declare_parameter<std::vector<double>>(
        "tool_to_sensor_rpy_rad", {0.0, 0.0, 0.0});
    const auto wrench_sign = declare_parameter<std::vector<double>>(
        "wrench_sign", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0});
    transform_.controlled_p_sensor = ar_admittance_control::vector3(
        tool_to_sensor_xyz, "tool_to_sensor_translation_m");
    transform_.controlled_R_sensor =
        ar_admittance_control::rpyToRotation(tool_to_sensor_rpy);
    transform_.sign =
        ar_admittance_control::vector6(wrench_sign, "wrench_sign");
    transform_.enabled = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "enabled_wrench_axes", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}),
        "enabled_wrench_axes");
    for (Eigen::Index i = 0; i < 6; ++i) {
      if (std::abs(std::abs(transform_.sign[i]) - 1.0) > 1e-9) {
        throw std::invalid_argument("wrench_sign entries must be +1 or -1");
      }
      if (!(transform_.enabled[i] == 0.0 || transform_.enabled[i] == 1.0)) {
        throw std::invalid_argument(
            "enabled_wrench_axes entries must be 0 or 1");
      }
    }

    safety_.hard_force_n =
        declare_parameter<double>("hard_force_n", 20.0);
    safety_.hard_torque_nm =
        declare_parameter<double>("hard_torque_nm", 3.0);
    safety_.raw_force_n =
        declare_parameter<double>("raw_force_sanity_n", 1000.0);
    safety_.raw_torque_nm =
        declare_parameter<double>("raw_torque_sanity_nm", 100.0);
    joint_watchdog_rad_ =
        declare_parameter<double>("joint_watchdog_deg", 20.0) * kDeg;
    elbow_watchdog_rad_ =
        declare_parameter<double>("elbow_watchdog_deg", 12.0) * kDeg;
    validateScalarParameters();

    receiver_ = std::make_unique<WrenchReceiver>(
        *this, wrench_topic_, wrench_timeout_s_);
    RCLCPP_WARN(get_logger(),
                "Mode=%s; full 6D Cartesian admittance; topic=%s. "
                "Commands are offsets in the captured TOOL frame.",
                active_control_ ? "ACTIVE" : "SHADOW", wrench_topic_.c_str());
  }

  int run() {
    if (!receiver_->waitForData(5.0)) {
      RCLCPP_ERROR(get_logger(), "No fresh wrench data within 5 seconds");
      return 2;
    }
    RCLCPP_INFO(get_logger(),
                "Hands off: collecting a %.1f s six-axis tare at this pose...",
                tare_duration_s_);
    std::string reason;
    if (!receiver_->tare(tare_duration_s_, tare_force_range_n_,
                         tare_torque_range_nm_, reason)) {
      RCLCPP_ERROR(get_logger(), "Tare failed: %s", reason.c_str());
      return 3;
    }
    const Vector6d bias = receiver_->bias();
    RCLCPP_INFO(get_logger(),
                "Tare=[%+.2f %+.2f %+.2f N | %+.3f %+.3f %+.3f Nm]",
                bias[0], bias[1], bias[2], bias[3], bias[4], bias[5]);
    return active_control_ ? runActive() : runShadow();
  }

 private:
  void validateScalarParameters() const {
    if (!std::isfinite(duration_s_) || duration_s_ <= 0.0 ||
        duration_s_ > 120.0 || !std::isfinite(wrench_timeout_s_) ||
        wrench_timeout_s_ <= 0.0 || wrench_timeout_s_ > 0.2 ||
        !std::isfinite(tare_duration_s_) || tare_duration_s_ < 0.5 ||
        tare_duration_s_ > 10.0 || safety_.hard_force_n <= 0.0 ||
        safety_.hard_torque_nm <= 0.0 || arm_quiet_force_n_ <= 0.0 ||
        arm_quiet_torque_nm_ <= 0.0 || joint_watchdog_rad_ <= 0.0 ||
        elbow_watchdog_rad_ <= 0.0) {
      throw std::invalid_argument("invalid or unsafe scalar parameter");
    }
    if (admittance_.max_position.head<3>().maxCoeff() > 0.03 ||
        admittance_.max_position.tail<3>().maxCoeff() > 10.0 * kDeg) {
      throw std::invalid_argument(
          "Cartesian first-test envelope exceeds 30 mm or 10 deg");
    }
  }

  int runShadow() {
    RCLCPP_WARN(get_logger(),
                "SHADOW: robot is not connected. Move the sensor to verify "
                "all six signs and the configured sensor-to-tool transform.");
    const auto started = Clock::now();
    auto next_tick = started;
    auto next_log = started;
    while (rclcpp::ok() && !ar_admittance_control::stop_requested.load()) {
      const auto now = Clock::now();
      if (std::chrono::duration<double>(now - started).count() >= duration_s_) {
        break;
      }
      const Vector6d corrected = receiver_->corrected();
      std::string reason;
      if (!safety_.check(*receiver_, corrected, reason)) {
        RCLCPP_ERROR(get_logger(), "SHADOW stop: %s", reason.c_str());
        return 4;
      }
      const Vector6d tool_wrench = transform_.apply(corrected);
      admittance_.step(tool_wrench, 0.004);
      if (now >= next_log) {
        RCLCPP_INFO(
            get_logger(),
            "Wtool=[%+.1f %+.1f %+.1f N | %+.2f %+.2f %+.2f Nm], "
            "offset=[%+.1f %+.1f %+.1f mm | %+.2f %+.2f %+.2f deg]",
            tool_wrench[0], tool_wrench[1], tool_wrench[2], tool_wrench[3],
            tool_wrench[4], tool_wrench[5], admittance_.position[0] * 1000.0,
            admittance_.position[1] * 1000.0,
            admittance_.position[2] * 1000.0,
            admittance_.position[3] / kDeg,
            admittance_.position[4] / kDeg,
            admittance_.position[5] / kDeg);
        next_log = now + std::chrono::milliseconds(250);
      }
      next_tick += std::chrono::milliseconds(4);
      std::this_thread::sleep_until(next_tick);
    }
    RCLCPP_INFO(get_logger(), "SHADOW finished; robot was never connected");
    return 0;
  }

  static const char *faultText(int code) {
    switch (code) {
      case 1: return "wrench data stale or non-finite";
      case 2: return "external force/torque hard limit";
      case 3: return "real-time robot state read failed";
      case 4: return "joint or elbow watchdog";
      case 5: return "TCP tracking/envelope watchdog";
      default: return "unknown watchdog";
    }
  }

  int runActive() {
    if (!sensor_mounted_) {
      RCLCPP_ERROR(get_logger(),
                   "ACTIVE refused: set sensor_mounted_to_robot=true only "
                   "after the sensor is rigidly mounted and its transform is set");
      return 5;
    }
    RCLCPP_WARN(get_logger(),
                "No rokae_ros2 hardware controller or other xCoreSDK client may "
                "control the robot at the same time.");
    std::cout
        << "Verify TCP/load, flange/sensor mounting, all six SHADOW signs, clear "
           "workspace and E-stop.\n"
        << "Type ARM_CARTESIAN_6D exactly: " << std::flush;
    std::string confirmation;
    std::getline(std::cin, confirmation);
    if (confirmation != "ARM_CARTESIAN_6D") {
      RCLCPP_WARN(get_logger(), "Cancelled; robot was not connected");
      return 0;
    }
    RCLCPP_INFO(get_logger(), "Hands off for the 1 s pre-arm quiet check...");
    std::string quiet_reason;
    if (!receiver_->verifyCorrectedQuiet(1.0, arm_quiet_force_n_,
                                         arm_quiet_torque_nm_, quiet_reason)) {
      RCLCPP_ERROR(get_logger(), "Pre-arm check failed: %s",
                   quiet_reason.c_str());
      return 5;
    }

    rokae::ArRobot robot;
    std::shared_ptr<rokae::RtMotionControlCobot<7>> controller;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      std::error_code ec;
      const auto info = robot.robotInfo(ec);
      ar_admittance_control::requireOk(ec, "read robot information");
      if (info.joint_num != 7) {
        throw std::runtime_error("this node requires a seven-axis AR robot");
      }
      RCLCPP_INFO(get_logger(), "Robot=%s controller=%s SDK=%s",
                  info.type.c_str(), info.version.c_str(),
                  rokae::BaseRobot::sdkVersion().c_str());

      ar_admittance_control::powerInNonRealtime(robot);
      std::array<double[2], 7> soft_limits{};
      ar_admittance_control::checkSoftLimits(robot, soft_limits, 10.0 * kDeg);
      ar_admittance_control::switchToRealtime(robot);
      controller = robot.getRtMotionController().lock();
      if (!controller) {
        throw std::runtime_error("real-time controller handle expired");
      }

      robot.startReceiveRobotState(
          std::chrono::milliseconds(1),
          {rokae::RtSupportedFields::tcpPose_m,
           rokae::RtSupportedFields::elbow_m,
           rokae::RtSupportedFields::jointPos_m});
      std::array<double, 16> hold_pose_array{};
      std::array<double, 7> hold_joints{};
      double hold_elbow = 0.0;
      if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m,
                             hold_pose_array) != 0 ||
          robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                             hold_joints) != 0 ||
          robot.getStateData(rokae::RtSupportedFields::elbow_m,
                             hold_elbow) != 0) {
        throw std::runtime_error("read initial robot state failed");
      }
      const Eigen::Isometry3d hold_pose =
          ar_admittance_control::rowMajorToEigen(hold_pose_array);
      RCLCPP_WARN(get_logger(),
                  "ARMED %.1f s at TCP=[%.1f %.1f %.1f] mm. Maximum offsets "
                  "are configured per axis; Ctrl+C stops.",
                  duration_s_, hold_pose.translation().x() * 1000.0,
                  hold_pose.translation().y() * 1000.0,
                  hold_pose.translation().z() * 1000.0);

      std::atomic<int> fault{0};
      const auto started = Clock::now();
      std::function<rokae::CartesianPosition()> callback = [&]() {
        rokae::CartesianPosition command{};
        command.pos = hold_pose_array;
        command.elbow = hold_elbow;
        command.hasElbow = true;

        const Vector6d corrected = receiver_->corrected();
        if (!receiver_->fresh() || !corrected.allFinite()) {
          fault.store(1);
          command.setFinished();
          return command;
        }
        const Vector6d raw = receiver_->raw();
        if (!raw.allFinite() ||
            ar_admittance_control::norm3(raw, 0) >= safety_.raw_force_n ||
            ar_admittance_control::norm3(raw, 3) >= safety_.raw_torque_nm) {
          fault.store(1);
          command.setFinished();
          return command;
        }
        if (ar_admittance_control::norm3(corrected, 0) >=
                safety_.hard_force_n ||
            ar_admittance_control::norm3(corrected, 3) >=
                safety_.hard_torque_nm) {
          fault.store(2);
          command.setFinished();
          return command;
        }

        std::array<double, 16> measured_pose_array{};
        std::array<double, 7> measured_joints{};
        double measured_elbow = 0.0;
        if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m,
                               measured_pose_array) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                               measured_joints) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::elbow_m,
                               measured_elbow) != 0) {
          fault.store(3);
          command.setFinished();
          return command;
        }
        for (std::size_t i = 0; i < 7; ++i) {
          if (std::abs(measured_joints[i] - hold_joints[i]) >
              joint_watchdog_rad_) {
            fault.store(4);
            command.setFinished();
            return command;
          }
        }
        if (std::abs(measured_elbow - hold_elbow) > elbow_watchdog_rad_) {
          fault.store(4);
          command.setFinished();
          return command;
        }

        const Vector6d tool_wrench = transform_.apply(corrected);
        admittance_.step(tool_wrench, ar_admittance_control::kControlDt);
        Eigen::Isometry3d delta = Eigen::Isometry3d::Identity();
        delta.linear() = ar_admittance_control::rotationVectorToMatrix(
            admittance_.position.tail<3>());
        delta.translation() = admittance_.position.head<3>();
        const Eigen::Isometry3d desired = hold_pose * delta;

        const Eigen::Isometry3d measured =
            ar_admittance_control::rowMajorToEigen(measured_pose_array);
        const double translation_error =
            (desired.translation() - measured.translation()).norm();
        const Eigen::AngleAxisd rotation_error(
            measured.linear().transpose() * desired.linear());
        if (translation_error > 0.020 ||
            std::abs(rotation_error.angle()) > 8.0 * kDeg) {
          fault.store(5);
          command.setFinished();
          return command;
        }

        command.pos = ar_admittance_control::eigenToRowMajor(desired);
        const double elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        if (ar_admittance_control::stop_requested.load() ||
            elapsed >= duration_s_) {
          command.setFinished();
        }
        return command;
      };

      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::cartesianPosition);
      controller->startLoop(true);
      if (fault.load() != 0) {
        RCLCPP_ERROR(get_logger(), "WATCHDOG STOP: %s",
                     faultText(fault.load()));
      }
      RCLCPP_INFO(get_logger(),
                  "Final tool offset=[%+.1f %+.1f %+.1f mm | %+.2f %+.2f "
                  "%+.2f deg]",
                  admittance_.position[0] * 1000.0,
                  admittance_.position[1] * 1000.0,
                  admittance_.position[2] * 1000.0,
                  admittance_.position[3] / kDeg,
                  admittance_.position[4] / kDeg,
                  admittance_.position[5] / kDeg);
      ar_admittance_control::safeShutdown(robot, controller);
      return fault.load() == 0 ? 0 : 6;
    } catch (const std::exception &exception) {
      RCLCPP_ERROR(get_logger(), "ACTIVE error: %s", exception.what());
      ar_admittance_control::safeShutdown(robot, controller);
      return 7;
    }
  }

  bool active_control_{false};
  bool sensor_mounted_{false};
  std::string robot_ip_;
  std::string local_ip_;
  std::string wrench_topic_;
  double duration_s_{15.0};
  double wrench_timeout_s_{0.05};
  double tare_duration_s_{2.0};
  double tare_force_range_n_{3.0};
  double tare_torque_range_nm_{0.3};
  double arm_quiet_force_n_{3.0};
  double arm_quiet_torque_nm_{0.5};
  double joint_watchdog_rad_{20.0 * kDeg};
  double elbow_watchdog_rad_{12.0 * kDeg};
  Admittance6D admittance_;
  WrenchTransform transform_;
  WrenchSafety safety_;
  std::unique_ptr<WrenchReceiver> receiver_;
};

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, ar_admittance_control::requestStop);
  std::signal(SIGTERM, ar_admittance_control::requestStop);
  rclcpp::init(argc, argv);
  try {
    const auto node = std::make_shared<CartesianAdmittance6DNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    std::thread spin_thread([&executor]() { executor.spin(); });
    const int result = node->run();
    rclcpp::shutdown();
    spin_thread.join();
    return result;
  } catch (const std::exception &exception) {
    std::cerr << "Fatal: " << exception.what() << '\n';
    if (rclcpp::ok()) {
      rclcpp::shutdown();
    }
    return 1;
  }
}
