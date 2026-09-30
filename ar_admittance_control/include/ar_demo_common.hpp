#ifndef XCORESDK_EXAMPLE_AR_CONTROL_SUITE_AR_DEMO_COMMON_HPP_
#define XCORESDK_EXAMPLE_AR_CONTROL_SUITE_AR_DEMO_COMMON_HPP_

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>

#include "rokae/robot.h"

namespace ar_demo {

constexpr double kPi = 3.14159265358979323846;
constexpr double kDegToRad = kPi / 180.0;
constexpr double kRadToDeg = 180.0 / kPi;
constexpr double kStartLimitMarginRad = 10.0 * kDegToRad;
constexpr double kStopLimitMarginRad = 3.0 * kDegToRad;

inline std::atomic<bool> stop_requested{false};

inline void onSignal(int) { stop_requested.store(true); }

inline void installSignalHandlers() {
  std::signal(SIGINT, onSignal);
  std::signal(SIGTERM, onSignal);
}

inline void requireOk(const std::error_code &ec, const std::string &action) {
  if (ec) throw std::runtime_error(action + ": " + ec.message());
}

inline double parseNumber(const char *text, double lower, double upper,
                          const char *name) {
  char *end = nullptr;
  const double value = std::strtod(text, &end);
  if (end == text || *end != '\0' || !std::isfinite(value) ||
      value < lower || value > upper) {
    throw std::invalid_argument(std::string(name) + " must be in [" +
                                std::to_string(lower) + ", " +
                                std::to_string(upper) + "]");
  }
  return value;
}

inline int parseInteger(const char *text, int lower, int upper,
                        const char *name) {
  char *end = nullptr;
  const long value = std::strtol(text, &end, 10);
  if (end == text || *end != '\0' || value < lower || value > upper) {
    throw std::invalid_argument(std::string(name) + " must be in [" +
                                std::to_string(lower) + ", " +
                                std::to_string(upper) + "]");
  }
  return static_cast<int>(value);
}

inline bool confirm(const std::string &token) {
  std::cout << "Type " << token << " exactly to continue: " << std::flush;
  std::string input;
  std::getline(std::cin, input);
  return input == token;
}

inline rokae::Info verifyRobot(rokae::ArRobot &robot) {
  std::error_code ec;
  const auto info = robot.robotInfo(ec);
  requireOk(ec, "read robot information");
  if (info.joint_num != 7) {
    throw std::runtime_error("this suite requires a seven-axis ArRobot");
  }
  std::cout << "Robot type : " << info.type << '\n'
            << "Controller : " << info.version << '\n'
            << "SDK        : " << rokae::BaseRobot::sdkVersion() << '\n';
  return info;
}

inline void printJointsDeg(const char *label,
                           const std::array<double, 7> &q) {
  std::cout << label << " [";
  for (std::size_t i = 0; i < q.size(); ++i) {
    if (i) std::cout << ", ";
    std::cout << q[i] * kRadToDeg;
  }
  std::cout << "] deg\n";
}

inline bool readAndCheckSoftLimits(
    rokae::ArRobot &robot, const std::array<double, 7> &q,
    std::array<double[2], 7> &limits) {
  std::error_code ec;
  const bool enabled = robot.getSoftLimit(limits, ec);
  requireOk(ec, "read joint soft limits");
  if (!enabled) {
    throw std::runtime_error(
        "soft limits are disabled; enable and verify them in RobotAssist first");
  }
  for (std::size_t i = 0; i < q.size(); ++i) {
    if (q[i] - limits[i][0] < kStartLimitMarginRad ||
        limits[i][1] - q[i] < kStartLimitMarginRad) {
      throw std::runtime_error("J" + std::to_string(i + 1) +
                               " is less than 10 deg from a soft limit");
    }
  }
  return true;
}

inline bool insideStopMargins(const std::array<double, 7> &q,
                              const std::array<double[2], 7> &limits,
                              std::string &reason) {
  for (std::size_t i = 0; i < q.size(); ++i) {
    if (q[i] - limits[i][0] < kStopLimitMarginRad ||
        limits[i][1] - q[i] < kStopLimitMarginRad) {
      reason = "J" + std::to_string(i + 1) +
               " entered the 3 deg soft-limit stop margin";
      return false;
    }
  }
  return true;
}

inline void enterNrtAutomatic(rokae::ArRobot &robot) {
  std::error_code ec;
  robot.setMotionControlMode(rokae::MotionControlMode::NrtCommand, ec);
  requireOk(ec, "select NrtCommand mode");
  robot.setOperateMode(rokae::OperateMode::automatic, ec);
  requireOk(ec, "select automatic mode");
  robot.setPowerState(true, ec);
  requireOk(ec, "power on");
}

inline std::shared_ptr<rokae::RtMotionControlCobot<7>> enterRtAutomatic(
    rokae::ArRobot &robot) {
  enterNrtAutomatic(robot);
  std::error_code ec;
  robot.setRtNetworkTolerance(50, ec);
  requireOk(ec, "set real-time network tolerance");
  robot.setMotionControlMode(rokae::MotionControlMode::RtCommand, ec);
  requireOk(ec, "select RtCommand mode");
  robot.setOperateMode(rokae::OperateMode::automatic, ec);
  requireOk(ec, "select automatic mode after entering RtCommand");
  robot.setPowerState(true, ec);
  requireOk(ec, "power on after entering RtCommand");
  auto rt = robot.getRtMotionController().lock();
  if (!rt) throw std::runtime_error("real-time controller handle expired");
  return rt;
}

inline void waitUntilIdle(rokae::ArRobot &robot,
                          std::chrono::seconds timeout) {
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (!stop_requested.load() && std::chrono::steady_clock::now() < deadline) {
    std::error_code ec;
    const auto state = robot.operationState(ec);
    requireOk(ec, "read operation state while waiting");
    if (state == rokae::OperationState::idle) return;
    if (state == rokae::OperationState::unknown) {
      throw std::runtime_error("operation state became unknown");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  std::error_code ignored;
  robot.stop(ignored);
  if (stop_requested.load()) throw std::runtime_error("stopped by Ctrl+C");
  throw std::runtime_error("motion did not finish before timeout");
}

inline void safeShutdown(
    rokae::ArRobot &robot,
    const std::shared_ptr<rokae::RtMotionControlCobot<7>> &rt = {}) noexcept {
  if (rt) {
    try { rt->stopMove(); } catch (...) {}
    rt->disconnectNetwork();
  }
  robot.stopReceiveRobotState();
  std::error_code ignored;
  robot.stop(ignored);
  robot.setPowerState(false, ignored);
  robot.setMotionControlMode(rokae::MotionControlMode::Idle, ignored);
  robot.setOperateMode(rokae::OperateMode::manual, ignored);
}

inline double minimumJerk(double u) {
  return u * u * u * (10.0 + u * (-15.0 + 6.0 * u));
}

inline double outAndBackOffset(double elapsed, double duration,
                               double amplitude) {
  const double u = std::min(1.0, std::max(0.0, elapsed / duration));
  if (u <= 0.5) return amplitude * minimumJerk(2.0 * u);
  return amplitude * (1.0 - minimumJerk(2.0 * u - 1.0));
}

inline double tcpDistance(const std::array<double, 16> &a,
                          const std::array<double, 16> &b) {
  const double dx = a[3] - b[3];
  const double dy = a[7] - b[7];
  const double dz = a[11] - b[11];
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

}  // namespace ar_demo

#endif
