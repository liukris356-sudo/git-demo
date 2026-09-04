#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include "Eigen/Geometry"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rokae/robot.h"

namespace ar_admittance_control {

using Clock = std::chrono::steady_clock;
using Vector6d = Eigen::Matrix<double, 6, 1>;
using Vector7d = Eigen::Matrix<double, 7, 1>;
constexpr double kPi = 3.14159265358979323846;
constexpr double kControlDt = 0.001;

inline std::atomic<bool> stop_requested{false};
inline void requestStop(int) { stop_requested.store(true); }

inline std::int64_t steadyNowNs() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             Clock::now().time_since_epoch())
      .count();
}

inline void requireOk(const std::error_code &ec, const char *action) {
  if (ec) {
    throw std::runtime_error(std::string(action) + ": " + ec.message());
  }
}

inline double norm3(const Vector6d &wrench, Eigen::Index offset) {
  return wrench.segment<3>(offset).norm();
}

inline double applyDeadband(double value, double deadband) {
  const double magnitude = std::abs(value);
  return magnitude <= deadband ? 0.0
                               : std::copysign(magnitude - deadband, value);
}

inline std::array<double, 16> eigenToRowMajor(const Eigen::Isometry3d &pose) {
  std::array<double, 16> output{};
  for (Eigen::Index row = 0; row < 4; ++row) {
    for (Eigen::Index col = 0; col < 4; ++col) {
      output[static_cast<std::size_t>(row * 4 + col)] = pose(row, col);
    }
  }
  return output;
}

inline Eigen::Isometry3d rowMajorToEigen(const std::array<double, 16> &pose) {
  Eigen::Matrix4d matrix;
  for (Eigen::Index row = 0; row < 4; ++row) {
    for (Eigen::Index col = 0; col < 4; ++col) {
      matrix(row, col) = pose[static_cast<std::size_t>(row * 4 + col)];
    }
  }
  Eigen::Isometry3d output = Eigen::Isometry3d::Identity();
  output.matrix() = matrix;
  return output;
}

inline Eigen::Matrix3d rpyToRotation(const std::vector<double> &rpy) {
  if (rpy.size() != 3) {
    throw std::invalid_argument("RPY parameter must contain 3 values");
  }
  const Eigen::AngleAxisd roll(rpy[0], Eigen::Vector3d::UnitX());
  const Eigen::AngleAxisd pitch(rpy[1], Eigen::Vector3d::UnitY());
  const Eigen::AngleAxisd yaw(rpy[2], Eigen::Vector3d::UnitZ());
  return (yaw * pitch * roll).toRotationMatrix();
}

inline Eigen::Matrix3d rotationVectorToMatrix(const Eigen::Vector3d &vector) {
  const double angle = vector.norm();
  if (angle < 1e-12) {
    return Eigen::Matrix3d::Identity();
  }
  return Eigen::AngleAxisd(angle, vector / angle).toRotationMatrix();
}

inline Eigen::Vector3d vector3(const std::vector<double> &values,
                               const char *name) {
  if (values.size() != 3) {
    throw std::invalid_argument(std::string(name) + " must contain 3 values");
  }
  return Eigen::Vector3d(values[0], values[1], values[2]);
}

inline Vector6d vector6(const std::vector<double> &values, const char *name) {
  if (values.size() != 6) {
    throw std::invalid_argument(std::string(name) + " must contain 6 values");
  }
  Vector6d result;
  for (Eigen::Index i = 0; i < 6; ++i) {
    result[i] = values[static_cast<std::size_t>(i)];
  }
  return result;
}

inline Vector7d vector7(const std::vector<double> &values, const char *name) {
  if (values.size() != 7) {
    throw std::invalid_argument(std::string(name) + " must contain 7 values");
  }
  Vector7d result;
  for (Eigen::Index i = 0; i < 7; ++i) {
    result[i] = values[static_cast<std::size_t>(i)];
  }
  return result;
}

inline void requirePositive(const Eigen::Ref<const Eigen::VectorXd> &values,
                            const char *name) {
  if (!values.allFinite() || (values.array() <= 0.0).any()) {
    throw std::invalid_argument(std::string(name) +
                                " values must all be finite and positive");
  }
}

class WrenchReceiver {
 public:
  WrenchReceiver(rclcpp::Node &node, const std::string &topic,
                 double timeout_s)
      : timeout_s_(timeout_s) {
    subscription_ = node.create_subscription<geometry_msgs::msg::WrenchStamped>(
        topic, rclcpp::SensorDataQoS().keep_last(1),
        [this](const geometry_msgs::msg::WrenchStamped::SharedPtr message) {
          const std::array<double, 6> sample{
              message->wrench.force.x,  message->wrench.force.y,
              message->wrench.force.z,  message->wrench.torque.x,
              message->wrench.torque.y, message->wrench.torque.z};
          sequence_.fetch_add(1, std::memory_order_acq_rel);  // odd: writing
          for (std::size_t i = 0; i < sample.size(); ++i) {
            raw_[i].store(sample[i], std::memory_order_relaxed);
          }
          stamp_ns_.store(steadyNowNs(), std::memory_order_release);
          sequence_.fetch_add(1, std::memory_order_release);  // even: complete
        });
  }

  Vector6d raw() const {
    Vector6d result;
    std::uint64_t before = 0;
    std::uint64_t after = 0;
    do {
      before = sequence_.load(std::memory_order_acquire);
      if ((before & 1U) != 0U) {
        continue;
      }
      for (Eigen::Index i = 0; i < 6; ++i) {
        result[i] = raw_[static_cast<std::size_t>(i)].load(
            std::memory_order_relaxed);
      }
      after = sequence_.load(std::memory_order_acquire);
    } while (before != after || (after & 1U) != 0U);
    return result;
  }

  Vector6d corrected() const { return raw() - bias_; }

  double ageSeconds() const {
    const auto stamp = stamp_ns_.load(std::memory_order_acquire);
    if (stamp == 0) {
      return std::numeric_limits<double>::infinity();
    }
    return static_cast<double>(steadyNowNs() - stamp) * 1e-9;
  }

  bool fresh() const { return ageSeconds() <= timeout_s_; }

  bool waitForData(double timeout_s) const {
    const auto deadline = Clock::now() + std::chrono::duration<double>(timeout_s);
    while (rclcpp::ok() && !stop_requested.load() && Clock::now() < deadline) {
      if (sequence_.load(std::memory_order_acquire) > 10 && fresh()) {
        return true;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return false;
  }

  bool tare(double duration_s, double max_force_range_n,
            double max_torque_range_nm, std::string &reason) {
    Vector6d minimum = Vector6d::Constant(
        std::numeric_limits<double>::infinity());
    Vector6d maximum = Vector6d::Constant(
        -std::numeric_limits<double>::infinity());
    Vector6d sum = Vector6d::Zero();
    std::uint64_t count = 0;
    std::uint64_t last_sequence = sequence_.load(std::memory_order_acquire);
    const auto deadline = Clock::now() + std::chrono::duration<double>(duration_s);
    while (rclcpp::ok() && !stop_requested.load() && Clock::now() < deadline) {
      if (!fresh()) {
        reason = "wrench data became stale while taring";
        return false;
      }
      const auto sequence = sequence_.load(std::memory_order_acquire);
      if (sequence != last_sequence) {
        const Vector6d value = raw();
        if (!value.allFinite()) {
          reason = "non-finite wrench sample";
          return false;
        }
        minimum = minimum.cwiseMin(value);
        maximum = maximum.cwiseMax(value);
        sum += value;
        ++count;
        last_sequence = sequence;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    if (count < 50) {
      reason = "too few wrench samples for tare";
      return false;
    }
    const Vector6d range = maximum - minimum;
    if (range.head<3>().maxCoeff() > max_force_range_n ||
        range.tail<3>().maxCoeff() > max_torque_range_nm) {
      reason = "sensor was not stationary during tare; force range=" +
               std::to_string(range.head<3>().maxCoeff()) +
               " N, torque range=" +
               std::to_string(range.tail<3>().maxCoeff()) + " Nm";
      return false;
    }
    bias_ = sum / static_cast<double>(count);
    return true;
  }

  const Vector6d &bias() const { return bias_; }

  bool verifyCorrectedQuiet(double duration_s, double max_force_n,
                            double max_torque_nm, std::string &reason) const {
    const auto deadline = Clock::now() + std::chrono::duration<double>(duration_s);
    while (rclcpp::ok() && !stop_requested.load() && Clock::now() < deadline) {
      if (!fresh()) {
        reason = "wrench data stale during pre-arm quiet check";
        return false;
      }
      const Vector6d value = corrected();
      if (!value.allFinite() || norm3(value, 0) > max_force_n ||
          norm3(value, 3) > max_torque_nm) {
        reason = "sensor is not unloaded after tare";
        return false;
      }
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    return !stop_requested.load();
  }

 private:
  double timeout_s_;
  std::array<std::atomic<double>, 6> raw_{};
  std::atomic<std::int64_t> stamp_ns_{0};
  std::atomic<std::uint64_t> sequence_{0};
  Vector6d bias_{Vector6d::Zero()};
  rclcpp::Subscription<geometry_msgs::msg::WrenchStamped>::SharedPtr
      subscription_;
};

struct WrenchTransform {
  Eigen::Matrix3d controlled_R_sensor{Eigen::Matrix3d::Identity()};
  Eigen::Vector3d controlled_p_sensor{Eigen::Vector3d::Zero()};
  Vector6d sign{Vector6d::Ones()};
  Vector6d enabled{Vector6d::Ones()};

  Vector6d apply(const Vector6d &sensor_wrench) const {
    const Vector6d signed_wrench =
        enabled.cwiseProduct(sign).cwiseProduct(sensor_wrench);
    Vector6d result;
    result.head<3>() = controlled_R_sensor * signed_wrench.head<3>();
    result.tail<3>() =
        controlled_R_sensor * signed_wrench.tail<3>() +
        controlled_p_sensor.cross(result.head<3>());
    return result;
  }
};

struct WrenchSafety {
  double hard_force_n{20.0};
  double hard_torque_nm{3.0};
  double raw_force_n{1000.0};
  double raw_torque_nm{100.0};

  bool check(const WrenchReceiver &receiver, const Vector6d &corrected,
             std::string &reason) const {
    if (!receiver.fresh()) {
      reason = "wrench data stale: " +
               std::to_string(receiver.ageSeconds() * 1000.0) + " ms";
      return false;
    }
    const Vector6d raw = receiver.raw();
    if (!raw.allFinite() || !corrected.allFinite()) {
      reason = "non-finite wrench data";
      return false;
    }
    if (norm3(raw, 0) >= raw_force_n || norm3(raw, 3) >= raw_torque_nm) {
      reason = "raw wrench exceeds sensor sanity limit";
      return false;
    }
    if (norm3(corrected, 0) >= hard_force_n) {
      reason = "external force hard limit: " +
               std::to_string(norm3(corrected, 0)) + " N";
      return false;
    }
    if (norm3(corrected, 3) >= hard_torque_nm) {
      reason = "external torque hard limit: " +
               std::to_string(norm3(corrected, 3)) + " Nm";
      return false;
    }
    return true;
  }
};

class Admittance6D {
 public:
  Vector6d mass{Vector6d::Ones()};
  Vector6d damping{Vector6d::Ones()};
  Vector6d stiffness{Vector6d::Ones()};
  Vector6d deadband{Vector6d::Zero()};
  Vector6d max_position{Vector6d::Ones()};
  Vector6d max_velocity{Vector6d::Ones()};
  Vector6d max_acceleration{Vector6d::Ones()};
  Vector6d enabled{Vector6d::Ones()};
  double filter_cutoff_hz{10.0};
  Vector6d position{Vector6d::Zero()};
  Vector6d velocity{Vector6d::Zero()};
  Vector6d filtered_input{Vector6d::Zero()};

  void validate() const {
    requirePositive(mass, "virtual_mass");
    requirePositive(damping, "damping");
    requirePositive(stiffness, "stiffness");
    requirePositive(max_position, "max_position");
    requirePositive(max_velocity, "max_velocity");
    requirePositive(max_acceleration, "max_acceleration");
    if (!deadband.allFinite() || (deadband.array() < 0.0).any() ||
        !enabled.allFinite() || !std::isfinite(filter_cutoff_hz) ||
        filter_cutoff_hz <= 0.0 || filter_cutoff_hz > 100.0) {
      throw std::invalid_argument("invalid admittance vector parameter");
    }
  }

  void step(const Vector6d &input, double dt) {
    const double alpha = 1.0 - std::exp(-2.0 * kPi * filter_cutoff_hz * dt);
    filtered_input += alpha * (input - filtered_input);
    Vector6d effective;
    for (Eigen::Index i = 0; i < 6; ++i) {
      effective[i] = enabled[i] > 0.5
                         ? applyDeadband(filtered_input[i], deadband[i])
                         : 0.0;
    }
    Vector6d acceleration =
        (effective - damping.cwiseProduct(velocity) -
         stiffness.cwiseProduct(position))
            .cwiseQuotient(mass);
    acceleration = acceleration.cwiseMax(-max_acceleration)
                       .cwiseMin(max_acceleration);
    velocity += acceleration * dt;
    velocity = velocity.cwiseMax(-max_velocity).cwiseMin(max_velocity);
    position += velocity * dt;
    for (Eigen::Index i = 0; i < 6; ++i) {
      if (position[i] >= max_position[i]) {
        position[i] = max_position[i];
        velocity[i] = std::min(velocity[i], 0.0);
      } else if (position[i] <= -max_position[i]) {
        position[i] = -max_position[i];
        velocity[i] = std::max(velocity[i], 0.0);
      }
    }
  }
};

inline void checkSoftLimits(rokae::ArRobot &robot,
                            std::array<double[2], 7> &limits,
                            double margin_rad) {
  std::error_code ec;
  const auto joints = robot.jointPos(ec);
  requireOk(ec, "read joints before real-time mode");
  const bool enabled = robot.getSoftLimit(limits, ec);
  requireOk(ec, "read joint soft limits");
  if (!enabled) {
    throw std::runtime_error("joint soft limits are disabled");
  }
  for (std::size_t i = 0; i < joints.size(); ++i) {
    if (joints[i] - limits[i][0] < margin_rad ||
        limits[i][1] - joints[i] < margin_rad) {
      throw std::runtime_error("J" + std::to_string(i + 1) +
                               " is too close to a soft limit");
    }
  }
}

inline void powerInNonRealtime(rokae::ArRobot &robot) {
  std::error_code ec;
  robot.setMotionControlMode(rokae::MotionControlMode::NrtCommand, ec);
  requireOk(ec, "select non-real-time mode");
  robot.setOperateMode(rokae::OperateMode::automatic, ec);
  requireOk(ec, "select automatic mode");
  robot.setPowerState(true, ec);
  requireOk(ec, "power on");
}

inline void switchToRealtime(rokae::ArRobot &robot) {
  std::error_code ec;
  robot.setRtNetworkTolerance(50, ec);
  requireOk(ec, "set real-time network tolerance");
  robot.setMotionControlMode(rokae::MotionControlMode::RtCommand, ec);
  requireOk(ec, "select real-time mode");
  robot.setOperateMode(rokae::OperateMode::automatic, ec);
  requireOk(ec, "select automatic mode after real-time mode");
  robot.setPowerState(true, ec);
  requireOk(ec, "power on after real-time mode");
}

inline void safeShutdown(
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

}  // namespace ar_admittance_control
