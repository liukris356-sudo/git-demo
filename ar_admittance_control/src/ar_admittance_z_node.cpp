#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>

#include "geometry_msgs/msg/twist_stamped.hpp"
#include "geometry_msgs/msg/vector3_stamped.hpp"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rokae/robot.h"

namespace {

using SteadyClock = std::chrono::steady_clock;
constexpr double kPi = 3.14159265358979323846;
constexpr double kControlDt = 0.001;

std::atomic<bool> g_stop_requested{false};

void onSignal(int) { g_stop_requested.store(true); }

double norm3(const std::array<double, 6> &wrench, std::size_t offset) {
  return std::sqrt(wrench[offset] * wrench[offset] +
                   wrench[offset + 1] * wrench[offset + 1] +
                   wrench[offset + 2] * wrench[offset + 2]);
}

double applyDeadband(double value, double deadband) {
  const double magnitude = std::abs(value);
  if (magnitude <= deadband) {
    return 0.0;
  }
  return std::copysign(magnitude - deadband, value);
}

std::size_t axisIndex(const std::string &axis) {
  if (axis == "x") {
    return 0;
  }
  if (axis == "y") {
    return 1;
  }
  if (axis == "z") {
    return 2;
  }
  throw std::invalid_argument("axis must be x, y or z");
}

void setVectorComponent(geometry_msgs::msg::Vector3 &vector,
                        std::size_t axis, double value) {
  if (axis == 0) {
    vector.x = value;
  } else if (axis == 1) {
    vector.y = value;
  } else {
    vector.z = value;
  }
}

double translationDistance(const std::array<double, 16> &a,
                           const std::array<double, 16> &b) {
  const double dx = a[3] - b[3];
  const double dy = a[7] - b[7];
  const double dz = a[11] - b[11];
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

double rotationDistance(const std::array<double, 16> &a,
                        const std::array<double, 16> &b) {
  double trace = 0.0;
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t col = 0; col < 3; ++col) {
      trace += a[row * 4 + col] * b[row * 4 + col];
    }
  }
  const double cosine = std::clamp((trace - 1.0) * 0.5, -1.0, 1.0);
  return std::acos(cosine);
}

void requireOk(const std::error_code &ec, const char *action) {
  if (ec) {
    throw std::runtime_error(std::string(action) + ": " + ec.message());
  }
}

struct AdmittanceAxis {
  double position_m{0.0};
  double velocity_m_s{0.0};
  double filtered_force_n{0.0};

  void step(double measured_force_n, double dt, double mass_kg,
            double damping_n_s_m, double stiffness_n_m,
            double filter_cutoff_hz, double max_velocity_m_s,
            double max_offset_m) {
    const double alpha = 1.0 - std::exp(-2.0 * kPi * filter_cutoff_hz * dt);
    filtered_force_n += alpha * (measured_force_n - filtered_force_n);

    const double acceleration_m_s2 =
        (filtered_force_n - damping_n_s_m * velocity_m_s -
         stiffness_n_m * position_m) /
        mass_kg;
    velocity_m_s = std::clamp(velocity_m_s + acceleration_m_s2 * dt,
                              -max_velocity_m_s, max_velocity_m_s);
    position_m += velocity_m_s * dt;

    if (position_m > max_offset_m) {
      position_m = max_offset_m;
      velocity_m_s = std::min(velocity_m_s, 0.0);
    } else if (position_m < -max_offset_m) {
      position_m = -max_offset_m;
      velocity_m_s = std::max(velocity_m_s, 0.0);
    }
  }
};

class ArAdmittanceZNode final : public rclcpp::Node {
 public:
  ArAdmittanceZNode() : Node("ar_admittance_z_node") {
    active_control_ = declare_parameter<bool>("active_control", false);
    robot_ip_ = declare_parameter<std::string>("robot_ip", "192.168.2.160");
    local_ip_ = declare_parameter<std::string>("local_ip", "192.168.2.100");
    wrench_topic_ =
        declare_parameter<std::string>("wrench_topic", "/m3815/wrench_raw");
    duration_s_ = declare_parameter<double>("duration_s", 15.0);
    sensor_force_axis_ =
        declare_parameter<std::string>("sensor_force_axis", "x");
    tool_motion_axis_ =
        declare_parameter<std::string>("tool_motion_axis", "x");
    force_sign_ = declare_parameter<double>("force_sign", 1.0);
    virtual_mass_kg_ = declare_parameter<double>("virtual_mass_kg", 30.0);
    damping_n_s_m_ = declare_parameter<double>("damping_n_s_m", 250.0);
    stiffness_n_m_ = declare_parameter<double>("stiffness_n_m", 1000.0);
    force_deadband_n_ = declare_parameter<double>("force_deadband_n", 2.0);
    filter_cutoff_hz_ = declare_parameter<double>("filter_cutoff_hz", 10.0);
    max_offset_m_ = declare_parameter<double>("max_offset_m", 0.010);
    max_velocity_m_s_ =
        declare_parameter<double>("max_velocity_m_s", 0.010);
    hard_force_n_ = declare_parameter<double>("hard_force_n", 20.0);
    hard_torque_nm_ = declare_parameter<double>("hard_torque_nm", 3.0);
    quiet_force_n_ = declare_parameter<double>("quiet_force_n", 3.0);
    quiet_torque_nm_ = declare_parameter<double>("quiet_torque_nm", 0.8);
    wrench_timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.050);
    quiet_duration_s_ = declare_parameter<double>("quiet_duration_s", 2.0);

    validateParameters();
    sensor_force_index_ = axisIndex(sensor_force_axis_);
    tool_motion_index_ = axisIndex(tool_motion_axis_);

    wrench_subscription_ = create_subscription<geometry_msgs::msg::WrenchStamped>(
        wrench_topic_, rclcpp::SensorDataQoS().keep_last(1),
        [this](const geometry_msgs::msg::WrenchStamped::SharedPtr message) {
          const std::array<double, 6> sample{
              message->wrench.force.x,  message->wrench.force.y,
              message->wrench.force.z,  message->wrench.torque.x,
              message->wrench.torque.y, message->wrench.torque.z};
          for (std::size_t i = 0; i < sample.size(); ++i) {
            wrench_[i].store(sample[i], std::memory_order_relaxed);
          }
          wrench_time_ns_.store(nowSteadyNs(), std::memory_order_release);
          sample_count_.fetch_add(1, std::memory_order_relaxed);
        });

    offset_publisher_ =
        create_publisher<geometry_msgs::msg::Vector3Stamped>(
            "/admittance/offset_tool", 10);
    velocity_publisher_ =
        create_publisher<geometry_msgs::msg::TwistStamped>(
            "/admittance/velocity_tool", 10);

    RCLCPP_INFO(get_logger(),
                "Mode: %s; wrench: %s; F%s -> tool %s; M=%.1f D=%.1f K=%.1f",
                active_control_ ? "ACTIVE" : "SHADOW", wrench_topic_.c_str(),
                sensor_force_axis_.c_str(), tool_motion_axis_.c_str(),
                virtual_mass_kg_, damping_n_s_m_, stiffness_n_m_);
    if (!active_control_) {
      RCLCPP_WARN(get_logger(),
                  "SHADOW mode: the robot will not be connected or commanded.");
    }
  }

  int run() {
    if (!waitForSensor(std::chrono::seconds(5))) {
      RCLCPP_ERROR(get_logger(), "No fresh wrench data received within 5 seconds.");
      return 2;
    }

    if (!active_control_) {
      return runShadow();
    }
    return runActive();
  }

 private:
  static std::int64_t nowSteadyNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               SteadyClock::now().time_since_epoch())
        .count();
  }

  void validateParameters() const {
    const auto positive = [](double v) { return std::isfinite(v) && v > 0.0; };
    if (!positive(duration_s_) || duration_s_ > 120.0 ||
        !positive(virtual_mass_kg_) || !positive(damping_n_s_m_) ||
        !positive(stiffness_n_m_) || !positive(filter_cutoff_hz_) ||
        !positive(max_offset_m_) || max_offset_m_ > 0.030 ||
        !positive(max_velocity_m_s_) || max_velocity_m_s_ > 0.030 ||
        !positive(hard_force_n_) || !positive(hard_torque_nm_) ||
        !positive(wrench_timeout_s_) || wrench_timeout_s_ > 0.2 ||
        !positive(quiet_duration_s_) ||
        (sensor_force_axis_ != "x" && sensor_force_axis_ != "y" &&
         sensor_force_axis_ != "z") ||
        (tool_motion_axis_ != "x" && tool_motion_axis_ != "y" &&
         tool_motion_axis_ != "z") ||
        !(force_sign_ == 1.0 || force_sign_ == -1.0)) {
      throw std::invalid_argument("invalid or unsafe admittance parameter");
    }
  }

  std::array<double, 6> latestWrench() const {
    std::array<double, 6> result{};
    for (std::size_t i = 0; i < result.size(); ++i) {
      result[i] = wrench_[i].load(std::memory_order_relaxed);
    }
    return result;
  }

  double wrenchAgeSeconds() const {
    const std::int64_t stamp = wrench_time_ns_.load(std::memory_order_acquire);
    if (stamp == 0) {
      return std::numeric_limits<double>::infinity();
    }
    return static_cast<double>(nowSteadyNs() - stamp) * 1e-9;
  }

  bool waitForSensor(std::chrono::seconds timeout) const {
    const auto deadline = SteadyClock::now() + timeout;
    while (rclcpp::ok() && !g_stop_requested.load() &&
           SteadyClock::now() < deadline) {
      if (sample_count_.load(std::memory_order_relaxed) > 10 &&
          wrenchAgeSeconds() <= wrench_timeout_s_) {
        return true;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    return false;
  }

  bool waitForQuietSensor() const {
    RCLCPP_INFO(get_logger(),
                "Hands off. Checking fresh, quiet wrench data for %.1f s...",
                quiet_duration_s_);
    auto quiet_since = SteadyClock::now();
    while (rclcpp::ok() && !g_stop_requested.load()) {
      const auto wrench = latestWrench();
      const bool fresh = wrenchAgeSeconds() <= wrench_timeout_s_;
      const bool quiet = norm3(wrench, 0) <= quiet_force_n_ &&
                         norm3(wrench, 3) <= quiet_torque_nm_;
      if (!fresh || !quiet) {
        quiet_since = SteadyClock::now();
      } else if (std::chrono::duration<double>(SteadyClock::now() - quiet_since)
                     .count() >= quiet_duration_s_) {
        return true;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return false;
  }

  bool checkWrench(const std::array<double, 6> &wrench, std::string &reason) {
    const double age = wrenchAgeSeconds();
    const double force = norm3(wrench, 0);
    const double torque = norm3(wrench, 3);
    if (age > wrench_timeout_s_) {
      reason = "wrench data stale: " + std::to_string(age * 1000.0) + " ms";
      return false;
    }
    if (force >= hard_force_n_) {
      reason = "force hard limit: " + std::to_string(force) + " N";
      return false;
    }
    if (torque >= hard_torque_nm_) {
      reason = "torque hard limit: " + std::to_string(torque) + " Nm";
      return false;
    }
    return true;
  }

  void publishAdmittance(const AdmittanceAxis &axis) {
    const auto stamp = now();
    geometry_msgs::msg::Vector3Stamped offset;
    offset.header.stamp = stamp;
    offset.header.frame_id = "tool0";
    setVectorComponent(offset.vector, tool_motion_index_, axis.position_m);
    offset_publisher_->publish(offset);

    geometry_msgs::msg::TwistStamped velocity;
    velocity.header = offset.header;
    setVectorComponent(
        velocity.twist.linear, tool_motion_index_, axis.velocity_m_s);
    velocity_publisher_->publish(velocity);
  }

  int runShadow() {
    if (!waitForQuietSensor()) {
      return 1;
    }

    RCLCPP_INFO(get_logger(),
                "SHADOW started for %.1f s. Push sensor %s; output is tool %s.",
                duration_s_, sensor_force_axis_.c_str(),
                tool_motion_axis_.c_str());
    AdmittanceAxis axis;
    const auto started = SteadyClock::now();
    auto next_tick = started;
    auto next_log = started;
    while (rclcpp::ok() && !g_stop_requested.load()) {
      const auto now_time = SteadyClock::now();
      if (std::chrono::duration<double>(now_time - started).count() >=
          duration_s_) {
        break;
      }
      const auto wrench = latestWrench();
      std::string reason;
      if (!checkWrench(wrench, reason)) {
        RCLCPP_ERROR(get_logger(), "SHADOW stop: %s", reason.c_str());
        return 3;
      }

      const double force = applyDeadband(
          force_sign_ * wrench[sensor_force_index_], force_deadband_n_);
      axis.step(force, 0.004, virtual_mass_kg_, damping_n_s_m_,
                stiffness_n_m_, filter_cutoff_hz_, max_velocity_m_s_,
                max_offset_m_);
      publishAdmittance(axis);

      if (now_time >= next_log) {
        RCLCPP_INFO(get_logger(),
                    "F%s=%+.2f N, filtered=%+.2f N, d%s=%+.2f mm, v%s=%+.2f mm/s",
                    sensor_force_axis_.c_str(), wrench[sensor_force_index_],
                    axis.filtered_force_n, tool_motion_axis_.c_str(),
                    axis.position_m * 1000.0, axis.velocity_m_s * 1000.0);
        next_log = now_time + std::chrono::milliseconds(250);
      }
      next_tick += std::chrono::milliseconds(4);
      std::this_thread::sleep_until(next_tick);
    }
    RCLCPP_INFO(get_logger(), "SHADOW finished; the robot was never connected.");
    return 0;
  }

  void setFault(std::string reason) {
    bool expected = false;
    if (faulted_.compare_exchange_strong(expected, true)) {
      std::lock_guard<std::mutex> lock(fault_mutex_);
      fault_reason_ = std::move(reason);
    }
  }

  std::string faultReason() const {
    std::lock_guard<std::mutex> lock(fault_mutex_);
    return fault_reason_;
  }

  static void safeShutdown(
      rokae::ArRobot &robot,
      const std::shared_ptr<rokae::RtMotionControlCobot<7>> &controller) noexcept {
    if (controller) {
      try {
        controller->stopMove();
      } catch (...) {
      }
      controller->disconnectNetwork();
    }
    std::error_code ec;
    robot.stopReceiveRobotState();
    robot.setPowerState(false, ec);
    ec.clear();
    robot.setMotionControlMode(rokae::MotionControlMode::Idle, ec);
    ec.clear();
    robot.setOperateMode(rokae::OperateMode::manual, ec);
  }

  int runActive() {
    if (!waitForQuietSensor()) {
      return 1;
    }

    RCLCPP_WARN(get_logger(),
                "ACTIVE maps sensor F%s to tool %s. Confirm this mapping and "
                "sign in SHADOW first. No rokae_ros2 controller may be running.",
                sensor_force_axis_.c_str(), tool_motion_axis_.c_str());
    std::cout
        << "Robot unloaded, workspace clear, E-stop reachable.\n"
        << "Sensor must be tared at the current stationary pose.\n"
        << "Type ARM_ADMITTANCE_AXIS exactly to connect and power on: "
        << std::flush;
    std::string confirmation;
    std::getline(std::cin, confirmation);
    if (confirmation != "ARM_ADMITTANCE_AXIS") {
      RCLCPP_WARN(get_logger(), "Cancelled; robot was not connected.");
      return 0;
    }

    rokae::ArRobot robot;
    std::shared_ptr<rokae::RtMotionControlCobot<7>> controller;
    try {
      robot.connectToRobot(robot_ip_, local_ip_);
      std::error_code ec;
      const auto info = robot.robotInfo(ec);
      requireOk(ec, "read robot information");
      if (info.joint_num != 7) {
        throw std::runtime_error("this controller requires a seven-axis AR robot");
      }
      RCLCPP_INFO(get_logger(), "Robot=%s controller=%s SDK=%s",
                  info.type.c_str(), info.version.c_str(),
                  rokae::BaseRobot::sdkVersion().c_str());

      robot.setMotionControlMode(rokae::MotionControlMode::NrtCommand, ec);
      requireOk(ec, "select non-real-time mode");
      robot.setOperateMode(rokae::OperateMode::automatic, ec);
      requireOk(ec, "select automatic mode");
      robot.setPowerState(true, ec);
      requireOk(ec, "power on");

      const auto nrt_joints = robot.jointPos(ec);
      requireOk(ec, "read joints before real-time mode");
      std::array<double[2], 7> soft_limits{};
      const bool soft_limits_enabled = robot.getSoftLimit(soft_limits, ec);
      requireOk(ec, "read joint soft limits");
      if (!soft_limits_enabled) {
        throw std::runtime_error("joint soft limits are disabled");
      }
      constexpr double kSoftLimitMargin = 10.0 * kPi / 180.0;
      for (std::size_t i = 0; i < nrt_joints.size(); ++i) {
        if (nrt_joints[i] - soft_limits[i][0] < kSoftLimitMargin ||
            soft_limits[i][1] - nrt_joints[i] < kSoftLimitMargin) {
          throw std::runtime_error("J" + std::to_string(i + 1) +
                                   " is less than 10 deg from a soft limit");
        }
      }

      robot.setRtNetworkTolerance(50, ec);
      requireOk(ec, "set real-time network tolerance");
      robot.setMotionControlMode(rokae::MotionControlMode::RtCommand, ec);
      requireOk(ec, "select real-time mode");
      robot.setOperateMode(rokae::OperateMode::automatic, ec);
      requireOk(ec, "select automatic mode after real-time mode");
      robot.setPowerState(true, ec);
      requireOk(ec, "power on after real-time mode");

      controller = robot.getRtMotionController().lock();
      if (!controller) {
        throw std::runtime_error("real-time controller handle expired");
      }

      robot.startReceiveRobotState(
          std::chrono::milliseconds(1),
          {rokae::RtSupportedFields::tcpPose_m,
           rokae::RtSupportedFields::elbow_m,
           rokae::RtSupportedFields::jointPos_m});

      std::array<double, 16> hold_pose{};
      std::array<double, 7> hold_joints{};
      double hold_elbow = 0.0;
      if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m, hold_pose) !=
              0 ||
          robot.getStateData(rokae::RtSupportedFields::elbow_m, hold_elbow) !=
              0 ||
          robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                             hold_joints) != 0) {
        throw std::runtime_error("read initial TCP, elbow or joints failed");
      }

      const std::array<double, 3> tool_axis_in_base{
          hold_pose[tool_motion_index_],
          hold_pose[4 + tool_motion_index_],
          hold_pose[8 + tool_motion_index_]};
      const double axis_norm =
          std::sqrt(tool_axis_in_base[0] * tool_axis_in_base[0] +
                    tool_axis_in_base[1] * tool_axis_in_base[1] +
                    tool_axis_in_base[2] * tool_axis_in_base[2]);
      if (std::abs(axis_norm - 1.0) > 0.01) {
        throw std::runtime_error("captured tool axis is not normalized");
      }

      RCLCPP_INFO(get_logger(),
                  "Captured TCP xyz=[%.1f %.1f %.1f] mm, elbow=%.2f deg",
                  hold_pose[3] * 1000.0, hold_pose[7] * 1000.0,
                  hold_pose[11] * 1000.0, hold_elbow * 180.0 / kPi);

      AdmittanceAxis axis;
      const auto started = SteadyClock::now();
      std::atomic<std::int64_t> loop_count{0};
      std::function<rokae::CartesianPosition()> callback = [&]() {
        rokae::CartesianPosition command{};
        command.pos = hold_pose;
        command.elbow = hold_elbow;
        command.hasElbow = true;

        const auto wrench = latestWrench();
        std::string reason;
        if (!checkWrench(wrench, reason)) {
          setFault(reason);
          command.setFinished();
          return command;
        }

        std::array<double, 16> measured_pose{};
        std::array<double, 7> measured_joints{};
        double measured_elbow = 0.0;
        if (robot.getStateData(rokae::RtSupportedFields::tcpPose_m,
                               measured_pose) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::elbow_m,
                               measured_elbow) != 0 ||
            robot.getStateData(rokae::RtSupportedFields::jointPos_m,
                               measured_joints) != 0) {
          setFault("real-time robot state read failed");
          command.setFinished();
          return command;
        }

        constexpr double kJointWatchdog = 8.0 * kPi / 180.0;
        constexpr double kElbowWatchdog = 5.0 * kPi / 180.0;
        constexpr double kRotationWatchdog = 2.0 * kPi / 180.0;
        for (std::size_t i = 0; i < measured_joints.size(); ++i) {
          if (std::abs(measured_joints[i] - hold_joints[i]) >
              kJointWatchdog) {
            setFault("J" + std::to_string(i + 1) +
                     " exceeded the 8 deg watchdog");
            command.setFinished();
            return command;
          }
        }
        if (std::abs(measured_elbow - hold_elbow) > kElbowWatchdog) {
          setFault("AR elbow exceeded the 5 deg watchdog");
          command.setFinished();
          return command;
        }
        if (translationDistance(measured_pose, hold_pose) >
            max_offset_m_ + 0.005) {
          setFault("measured TCP exceeded the translation envelope");
          command.setFinished();
          return command;
        }
        if (rotationDistance(measured_pose, hold_pose) >
            kRotationWatchdog) {
          setFault("measured TCP rotation exceeded the 2 deg watchdog");
          command.setFinished();
          return command;
        }

        const double force = applyDeadband(
            force_sign_ * wrench[sensor_force_index_], force_deadband_n_);
        axis.step(force, kControlDt, virtual_mass_kg_, damping_n_s_m_,
                  stiffness_n_m_, filter_cutoff_hz_, max_velocity_m_s_,
                  max_offset_m_);

        command.pos[3] = hold_pose[3] + tool_axis_in_base[0] * axis.position_m;
        command.pos[7] = hold_pose[7] + tool_axis_in_base[1] * axis.position_m;
        command.pos[11] =
            hold_pose[11] + tool_axis_in_base[2] * axis.position_m;

        const double elapsed =
            std::chrono::duration<double>(SteadyClock::now() - started).count();
        if (g_stop_requested.load() || elapsed >= duration_s_) {
          command.setFinished();
        }
        loop_count.fetch_add(1, std::memory_order_relaxed);
        return command;
      };

      controller->setControlLoop(callback, 0, true);
      controller->startMove(rokae::RtControllerMode::cartesianPosition);
      RCLCPP_WARN(get_logger(),
                  "ARMED for %.1f s: sensor F%s commands at most %.1f mm "
                  "along captured tool %s. Ctrl+C stops.",
                  duration_s_, sensor_force_axis_.c_str(),
                  max_offset_m_ * 1000.0, tool_motion_axis_.c_str());
      controller->startLoop(true);

      if (faulted_.load()) {
        RCLCPP_ERROR(get_logger(), "WATCHDOG STOP: %s", faultReason().c_str());
      } else {
        RCLCPP_INFO(get_logger(), "Finished normally; RT callbacks=%ld",
                    static_cast<long>(loop_count.load()));
      }
      RCLCPP_INFO(get_logger(),
                  "Final command state: d%s=%+.2f mm, v%s=%+.2f mm/s, "
                  "filtered F%s=%+.2f N",
                  tool_motion_axis_.c_str(), axis.position_m * 1000.0,
                  tool_motion_axis_.c_str(), axis.velocity_m_s * 1000.0,
                  sensor_force_axis_.c_str(), axis.filtered_force_n);
      safeShutdown(robot, controller);
      return faulted_.load() ? 3 : 0;
    } catch (const std::exception &exception) {
      RCLCPP_ERROR(get_logger(), "ACTIVE error: %s", exception.what());
      safeShutdown(robot, controller);
      return 4;
    }
  }

  bool active_control_{false};
  std::string robot_ip_;
  std::string local_ip_;
  std::string wrench_topic_;
  std::string sensor_force_axis_{"x"};
  std::string tool_motion_axis_{"x"};
  std::size_t sensor_force_index_{0};
  std::size_t tool_motion_index_{0};
  double duration_s_{15.0};
  double force_sign_{1.0};
  double virtual_mass_kg_{30.0};
  double damping_n_s_m_{250.0};
  double stiffness_n_m_{1000.0};
  double force_deadband_n_{2.0};
  double filter_cutoff_hz_{10.0};
  double max_offset_m_{0.010};
  double max_velocity_m_s_{0.010};
  double hard_force_n_{20.0};
  double hard_torque_nm_{3.0};
  double quiet_force_n_{3.0};
  double quiet_torque_nm_{0.8};
  double wrench_timeout_s_{0.050};
  double quiet_duration_s_{2.0};

  std::array<std::atomic<double>, 6> wrench_{};
  std::atomic<std::int64_t> wrench_time_ns_{0};
  std::atomic<std::uint64_t> sample_count_{0};
  std::atomic<bool> faulted_{false};
  mutable std::mutex fault_mutex_;
  std::string fault_reason_;

  rclcpp::Subscription<geometry_msgs::msg::WrenchStamped>::SharedPtr
      wrench_subscription_;
  rclcpp::Publisher<geometry_msgs::msg::Vector3Stamped>::SharedPtr
      offset_publisher_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr
      velocity_publisher_;
};

}  // namespace

int main(int argc, char **argv) {
  std::signal(SIGINT, onSignal);
  std::signal(SIGTERM, onSignal);
  rclcpp::init(argc, argv);

  try {
    const auto node = std::make_shared<ArAdmittanceZNode>();
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
