#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "ar_admittance_control/admittance_common.hpp"

namespace {

using ar_admittance_control::Clock;
using ar_admittance_control::Vector6d;
using ar_admittance_control::Vector7d;
using ar_admittance_control::WrenchReceiver;
using ar_admittance_control::WrenchSafety;
using ar_admittance_control::WrenchTransform;
constexpr double kDeg = ar_admittance_control::kPi / 180.0;

struct JointAdmittance {
  Vector7d inertia{Vector7d::Ones()};
  Vector7d damping{Vector7d::Ones()};
  Vector7d stiffness{Vector7d::Ones()};
  Vector7d deadband{Vector7d::Zero()};
  Vector7d max_offset{Vector7d::Ones()};
  Vector7d max_velocity{Vector7d::Ones()};
  Vector7d max_acceleration{Vector7d::Ones()};
  Vector7d offset{Vector7d::Zero()};
  Vector7d velocity{Vector7d::Zero()};
  Vector7d filtered_torque{Vector7d::Zero()};
  double filter_cutoff_hz{10.0};

  void validate() const {
    ar_admittance_control::requirePositive(inertia, "virtual_inertia");
    ar_admittance_control::requirePositive(damping, "joint_damping");
    ar_admittance_control::requirePositive(stiffness, "joint_stiffness");
    ar_admittance_control::requirePositive(max_offset, "max_joint_offset");
    ar_admittance_control::requirePositive(max_velocity, "max_joint_velocity");
    ar_admittance_control::requirePositive(max_acceleration,
                                           "max_joint_acceleration");
    if (!deadband.allFinite() || (deadband.array() < 0.0).any() ||
        !std::isfinite(filter_cutoff_hz) || filter_cutoff_hz <= 0.0 ||
        filter_cutoff_hz > 100.0 || max_offset.maxCoeff() > 10.0 * kDeg ||
        max_velocity.maxCoeff() > 30.0 * kDeg) {
      throw std::invalid_argument("invalid or unsafe joint admittance parameter");
    }
  }

  void step(const Vector7d &external_torque, double dt) {
    const double alpha =
        1.0 - std::exp(-2.0 * ar_admittance_control::kPi *
                       filter_cutoff_hz * dt);
    filtered_torque += alpha * (external_torque - filtered_torque);
    Vector7d effective;
    for (Eigen::Index i = 0; i < 7; ++i) {
      effective[i] = ar_admittance_control::applyDeadband(
          filtered_torque[i], deadband[i]);
    }
    Vector7d acceleration =
        (effective - damping.cwiseProduct(velocity) -
         stiffness.cwiseProduct(offset))
            .cwiseQuotient(inertia);
    acceleration = acceleration.cwiseMax(-max_acceleration)
                       .cwiseMin(max_acceleration);
    velocity += acceleration * dt;
    velocity = velocity.cwiseMax(-max_velocity).cwiseMin(max_velocity);
    offset += velocity * dt;
    for (Eigen::Index i = 0; i < 7; ++i) {
      if (offset[i] >= max_offset[i]) {
        offset[i] = max_offset[i];
        velocity[i] = std::min(velocity[i], 0.0);
      } else if (offset[i] <= -max_offset[i]) {
        offset[i] = -max_offset[i];
        velocity[i] = std::max(velocity[i], 0.0);
      }
    }
  }
};

class JointAdmittance6DNode final : public rclcpp::Node {
 public:
  JointAdmittance6DNode() : Node("ar_admittance_joint_6d_node") {
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

    admittance_.inertia = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "virtual_inertia", {8.0, 8.0, 6.0, 5.0, 2.0, 1.5, 1.0}),
        "virtual_inertia");
    admittance_.damping = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "joint_damping", {35.0, 35.0, 28.0, 22.0, 10.0, 8.0, 6.0}),
        "joint_damping");
    admittance_.stiffness = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "joint_stiffness", {80.0, 80.0, 65.0, 50.0, 25.0, 18.0, 12.0}),
        "joint_stiffness");
    admittance_.deadband = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "joint_torque_deadband", {0.30, 0.30, 0.25, 0.20, 0.12, 0.10,
                                      0.08}),
        "joint_torque_deadband");
    admittance_.max_offset = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "max_joint_offset_rad",
            {3.0 * kDeg, 3.0 * kDeg, 3.0 * kDeg, 3.0 * kDeg,
             3.0 * kDeg, 3.0 * kDeg, 3.0 * kDeg}),
        "max_joint_offset_rad");
    admittance_.max_velocity = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "max_joint_velocity_rad_s",
            {5.0 * kDeg, 5.0 * kDeg, 5.0 * kDeg, 5.0 * kDeg,
             5.0 * kDeg, 5.0 * kDeg, 5.0 * kDeg}),
        "max_joint_velocity_rad_s");
    admittance_.max_acceleration = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "max_joint_acceleration_rad_s2",
            {0.5, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8}),
        "max_joint_acceleration_rad_s2");
    admittance_.filter_cutoff_hz =
        declare_parameter<double>("filter_cutoff_hz", 10.0);
    admittance_.validate();

    generalized_torque_limit_ = ar_admittance_control::vector7(
        declare_parameter<std::vector<double>>(
            "generalized_torque_limit_nm",
            {12.0, 12.0, 10.0, 8.0, 5.0, 4.0, 3.0}),
        "generalized_torque_limit_nm");
    ar_admittance_control::requirePositive(generalized_torque_limit_,
                                           "generalized_torque_limit_nm");

    transform_.controlled_p_sensor = ar_admittance_control::vector3(
        declare_parameter<std::vector<double>>(
            "flange_to_sensor_translation_m", {0.0, 0.0, 0.0}),
        "flange_to_sensor_translation_m");
    transform_.controlled_R_sensor = ar_admittance_control::rpyToRotation(
        declare_parameter<std::vector<double>>(
            "flange_to_sensor_rpy_rad", {0.0, 0.0, 0.0}));
    transform_.sign = ar_admittance_control::vector6(
        declare_parameter<std::vector<double>>(
            "wrench_sign", {1.0, 1.0, 1.0, 1.0, 1.0, 1.0}),
        "wrench_sign");
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
    tracking_watchdog_rad_ =
        declare_parameter<double>("tracking_watchdog_deg", 4.0) * kDeg;
    validateScalarParameters();

    receiver_ = std::make_unique<WrenchReceiver>(
        *this, wrench_topic_, wrench_timeout_s_);
    RCLCPP_WARN(get_logger(),
                "Mode=%s; 6D sensor wrench -> J(q)^T -> 7-joint admittance; "
                "topic=%s",
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
        arm_quiet_torque_nm_ <= 0.0 || tracking_watchdog_rad_ <= 0.0) {
      throw std::invalid_argument("invalid or unsafe scalar parameter");
    }
  }

  int runShadow() {
    RCLCPP_WARN(get_logger(),
                "SHADOW does not connect to the robot, so it validates the "
                "six-axis sensor and flange transform only; J^T is computed "
                "only in ACTIVE with measured joints.");
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
      const Vector6d flange_wrench = transform_.apply(corrected);
      if (now >= next_log) {
        RCLCPP_INFO(get_logger(),
                    "Wflange=[%+.1f %+.1f %+.1f N | %+.2f %+.2f %+.2f Nm]",
                    flange_wrench[0], flange_wrench[1], flange_wrench[2],
                    flange_wrench[3], flange_wrench[4], flange_wrench[5]);
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
      case 3: return "real-time joint state read failed";
      case 4: return "generalized torque limit";
      case 5: return "joint command soft-limit margin";
      case 6: return "joint tracking watchdog";
      default: return "unknown watchdog";
    }
  }

  int runActive() {
    if (!sensor_mounted_) {
      RCLCPP_ERROR(get_logger(),
                   "ACTIVE refused: set sensor_mounted_to_robot=true only "
                   "after rigid mounting and flange-to-sensor calibration");
      return 5;
    }
    RCLCPP_WARN(get_logger(),
                "No rokae_ros2 hardware controller or other xCoreSDK client may "
                "control the robot at the same time.");
    std::cout
        << "Verify TCP/load, sensor transform, all six SHADOW signs, clear "
           "workspace and E-stop.\n"
        << "Type ARM_JOINT_6D exactly: " << std::flush;
    std::string confirmation;
    std::getline(std::cin, confirmation);
    if (confirmation != "ARM_JOINT_6D") {
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
      auto model = robot.model();
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
          {rokae::RtSupportedFields::jointPos_m});
      std::array<double, 7> hold_joints{};
      if (robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                             hold_joints) != 0) {
        throw std::runtime_error("read initial joints failed");
      }
      RCLCPP_WARN(get_logger(),
                  "ARMED %.1f s. A 6D sensor wrench is transformed to the "
                  "flange, rotated to base, then mapped by J(q)^T.",
                  duration_s_);

      std::atomic<int> fault{0};
      const auto started = Clock::now();
      std::function<rokae::JointPosition()> callback = [&]() {
        rokae::JointPosition command(7);
        for (std::size_t i = 0; i < 7; ++i) {
          command.joints[i] = hold_joints[i];
        }

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

        std::array<double, 7> measured_joints{};
        if (robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                               measured_joints) != 0) {
          fault.store(3);
          command.setFinished();
          return command;
        }
        Eigen::Map<const Vector7d> q(measured_joints.data());
        const Vector6d flange_wrench = transform_.apply(corrected);
        const auto flange_pose_array =
            model.getCartPose(measured_joints, rokae::SegmentFrame::flange);
        const Eigen::Matrix3d base_R_flange =
            ar_admittance_control::rowMajorToEigen(flange_pose_array).linear();
        Vector6d base_wrench;
        base_wrench.head<3>() = base_R_flange * flange_wrench.head<3>();
        base_wrench.tail<3>() = base_R_flange * flange_wrench.tail<3>();

        const auto jacobian_array =
            model.jacobian(measured_joints, rokae::SegmentFrame::flange);
        const Eigen::Map<
            const Eigen::Matrix<double, 6, 7, Eigen::RowMajor>>
            jacobian(jacobian_array.data());
        Vector7d generalized_torque = jacobian.transpose() * base_wrench;
        if ((generalized_torque.cwiseAbs().array() >=
             generalized_torque_limit_.array())
                .any()) {
          fault.store(4);
          command.setFinished();
          return command;
        }
        admittance_.step(generalized_torque,
                         ar_admittance_control::kControlDt);
        const Vector7d desired = Eigen::Map<const Vector7d>(hold_joints.data()) +
                                 admittance_.offset;
        for (Eigen::Index i = 0; i < 7; ++i) {
          const auto index = static_cast<std::size_t>(i);
          if (desired[i] <= soft_limits[index][0] + 5.0 * kDeg ||
              desired[i] >= soft_limits[index][1] - 5.0 * kDeg) {
            fault.store(5);
            command.setFinished();
            return command;
          }
          if (std::abs(q[i] - desired[i]) > tracking_watchdog_rad_) {
            fault.store(6);
            command.setFinished();
            return command;
          }
          command.joints[index] = desired[i];
        }

        const double elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        if (ar_admittance_control::stop_requested.load() ||
            elapsed >= duration_s_) {
          command.setFinished();
        }
        return command;
      };

      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::jointPosition);
      controller->startLoop(true);
      if (fault.load() != 0) {
        RCLCPP_ERROR(get_logger(), "WATCHDOG STOP: %s",
                     faultText(fault.load()));
      }
      RCLCPP_INFO(get_logger(),
                  "Final joint offsets=[%+.2f %+.2f %+.2f %+.2f %+.2f "
                  "%+.2f %+.2f] deg",
                  admittance_.offset[0] / kDeg, admittance_.offset[1] / kDeg,
                  admittance_.offset[2] / kDeg, admittance_.offset[3] / kDeg,
                  admittance_.offset[4] / kDeg, admittance_.offset[5] / kDeg,
                  admittance_.offset[6] / kDeg);
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
  double tracking_watchdog_rad_{4.0 * kDeg};
  JointAdmittance admittance_;
  Vector7d generalized_torque_limit_{Vector7d::Ones()};
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
    const auto node = std::make_shared<JointAdmittance6DNode>();
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
