#ifndef XB7_POINT_CONTROL_XB7_MOTION_SAFETY_HPP_
#define XB7_POINT_CONTROL_XB7_MOTION_SAFETY_HPP_

#include <any>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>

#include "rokae/robot.h"
#include "xb7_point_common.hpp"

namespace xb7_points {

inline bool isStationary(rokae::OperationState state) {
  return state == rokae::OperationState::idle ||
         state == rokae::OperationState::jog ||
         state == rokae::OperationState::drag;
}

inline void requireStationary(rokae::StandardRobot &robot) {
  std::error_code ec;
  const auto state = robot.operationState(ec);
  requireOk(ec, "read robot operation state");
  if (!isStationary(state)) {
    throw std::runtime_error(
        "robot must be stationary before arming point motion");
  }
}

inline bool confirm(const std::string &token) {
  std::cout << "Type " << token << " exactly to continue: " << std::flush;
  std::string input;
  std::getline(std::cin, input);
  return input == token;
}

inline void enterNrtAutomatic(rokae::StandardRobot &robot) {
  std::error_code ec;
  robot.setMotionControlMode(rokae::MotionControlMode::NrtCommand, ec);
  requireOk(ec, "select NrtCommand mode");
  robot.setOperateMode(rokae::OperateMode::automatic, ec);
  requireOk(ec, "select automatic mode");
  robot.setPowerState(true, ec);
  requireOk(ec, "power on");
  robot.moveReset(ec);
  requireOk(ec, "clear queued motion commands");
}

inline void waitForCommand(rokae::StandardRobot &robot,
                           const std::string &command_id,
                           int final_index,
                           std::chrono::seconds timeout) {
  using namespace rokae::EventInfoKey::MoveExecution;
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (!stop_requested.load() && std::chrono::steady_clock::now() < deadline) {
    std::error_code ec;
    const auto info = robot.queryEventInfo(rokae::Event::moveExecution, ec);
    requireOk(ec, "query motion execution event");
    if (info.count(ID) && info.count(WaypointIndex) && info.count(Error) &&
        info.count(ReachTarget)) {
      const auto id = std::any_cast<std::string>(info.at(ID));
      const auto index = std::any_cast<int>(info.at(WaypointIndex));
      const auto move_error = std::any_cast<std::error_code>(info.at(Error));
      if (id == command_id && move_error) {
        throw std::runtime_error("motion failed at point " +
                                 std::to_string(index) + ": " +
                                 move_error.message());
      }
      if (id == command_id && index == final_index &&
          std::any_cast<bool>(info.at(ReachTarget))) {
        return;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }

  std::error_code ignored;
  robot.stop(ignored);
  if (stop_requested.load()) {
    throw std::runtime_error("motion stopped by Ctrl+C");
  }
  throw std::runtime_error("motion completion timed out");
}

inline void safeShutdown(rokae::StandardRobot &robot) noexcept {
  std::error_code ignored;
  robot.stop(ignored);
  robot.moveReset(ignored);
  robot.setPowerState(false, ignored);
  robot.setMotionControlMode(rokae::MotionControlMode::Idle, ignored);
  robot.setOperateMode(rokae::OperateMode::manual, ignored);
  robot.disconnectFromRobot(ignored);
}

}  // namespace xb7_points

#endif  // XB7_POINT_CONTROL_XB7_MOTION_SAFETY_HPP_
