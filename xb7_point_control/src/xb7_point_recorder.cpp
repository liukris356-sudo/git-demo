/**
 * @file xb7_point_recorder.cpp
 * @brief Read-only named-point recorder for an XB7 six-axis industrial robot.
 *
 * The operator positions the robot with RobotAssist Jog, releases Jog, then
 * types a point name.  This program never powers or moves the robot.
 */

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cctype>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include "xb7_point_common.hpp"

namespace {

constexpr double kMaxStableTcpMotionM = 0.0003;  // 0.3 mm
constexpr double kMaxStableRotationRad =
    0.15 * xb7_points::kDegToRad;
constexpr double kMaxStableJointMotionRad =
    0.15 * xb7_points::kDegToRad;
constexpr auto kStabilityWindow = std::chrono::milliseconds(300);

bool validIdentifier(const std::string &name) {
  if (name.empty() || name.size() > 32) return false;
  const auto first = static_cast<unsigned char>(name.front());
  if (!std::isalpha(first) && name.front() != '_') return false;
  for (char character : name) {
    const auto value = static_cast<unsigned char>(character);
    if (!std::isalnum(value) && character != '_') return false;
  }
  return true;
}

void rejectMovingState(rokae::StandardRobot &robot) {
  std::error_code ec;
  const auto state = robot.operationState(ec);
  xb7_points::requireOk(ec, "read robot operation state");
  if (state == rokae::OperationState::moving ||
      state == rokae::OperationState::jogging ||
      state == rokae::OperationState::rtControlling ||
      state == rokae::OperationState::rlProgram ||
      state == rokae::OperationState::dynamicIdentify ||
      state == rokae::OperationState::frictionIdentify ||
      state == rokae::OperationState::loadIdentify) {
    throw std::runtime_error(
        "robot is moving; release Jog and wait until it stops");
  }
}

xb7_points::PointRecord readPoint(rokae::StandardRobot &robot,
                                  const std::string &name) {
  std::error_code ec;
  const auto joints = robot.jointPos(ec);
  xb7_points::requireOk(ec, "read XB7 joint position");
  const auto tcp = robot.cartPosture(rokae::CoordinateType::endInRef, ec);
  xb7_points::requireOk(ec, "read TCP in selected workobject");
  const auto flange =
      robot.cartPosture(rokae::CoordinateType::flangeInBase, ec);
  xb7_points::requireOk(ec, "read flange in robot base");

  xb7_points::PointRecord point;
  point.name = name;
  point.tcp_in_reference = xb7_points::poseArray(tcp);
  point.flange_in_base = xb7_points::poseArray(flange);
  point.joints = joints;
  return point;
}

xb7_points::PointRecord captureStablePoint(rokae::StandardRobot &robot,
                                           const std::string &name) {
  rejectMovingState(robot);
  const auto first = readPoint(robot, name);
  std::this_thread::sleep_for(kStabilityWindow);
  rejectMovingState(robot);
  const auto last = readPoint(robot, name);

  const double tcp_motion = xb7_points::translationDistance(
      first.tcp_in_reference, last.tcp_in_reference);
  const double rotation_motion = xb7_points::maximumRotationDistance(
      first.tcp_in_reference, last.tcp_in_reference);
  const double joint_motion =
      xb7_points::maximumJointDistance(first.joints, last.joints);
  if (tcp_motion > kMaxStableTcpMotionM ||
      rotation_motion > kMaxStableRotationRad ||
      joint_motion > kMaxStableJointMotionRad) {
    std::ostringstream message;
    message << std::fixed << std::setprecision(3)
            << "robot moved during capture: TCP=" << tcp_motion * 1000.0
            << " mm, rotation=" << rotation_motion * xb7_points::kRadToDeg
            << " deg, maximum joint="
            << joint_motion * xb7_points::kRadToDeg
            << " deg; release Jog and try again";
    throw std::runtime_error(message.str());
  }
  return last;
}

void printNames(const std::vector<xb7_points::PointRecord> &points) {
  if (points.empty()) {
    std::cout << "No points captured yet.\n";
    return;
  }
  std::cout << "Captured points (" << points.size() << "):";
  for (const auto &point : points) std::cout << ' ' << point.name;
  std::cout << '\n';
}

}  // namespace

int main(int argc, char **argv) {
  using xb7_points::installSignalHandlers;
  using xb7_points::requireOk;

  if (argc != 6) {
    std::cerr
        << "Usage: " << argv[0]
        << " ROBOT_IP LOCAL_IP GLOBAL_TOOL GLOBAL_WOBJ OUTPUT.csv\n"
        << "Example: " << argv[0]
        << " 192.168.0.160 192.168.0.180 g_tool_0 g_wobj_0"
           " xb7_points_01.csv\n";
    return 2;
  }

  const std::string robot_ip = argv[1];
  const std::string local_ip = argv[2];
  const std::string tool_name = argv[3];
  const std::string workobject_name = argv[4];
  const std::string output_path = argv[5];
  if (std::ifstream(output_path).good()) {
    std::cerr << "Refusing to overwrite existing file: " << output_path
              << "\nChoose a new filename.\n";
    return 2;
  }

  installSignalHandlers();
  rokae::StandardRobot robot;
  bool connected = false;
  try {
    std::cout
        << "READ-ONLY XB7 POINT RECORDER: no power or motion command is sent.\n"
        << "Connecting to " << robot_ip << " from " << local_ip << "...\n";
    robot.connectToRobot(robot_ip, local_ip);
    connected = true;
    const auto info = xb7_points::verifyXB7(robot);

    std::error_code ec;
    robot.setToolset(tool_name, workobject_name, ec);
    requireOk(ec, "select tool/workobject");

    std::cout
        << "Selected tool/workobject: " << tool_name << " / "
        << workobject_name << "\nOutput: " << output_path << "\n\n"
        << "Use RobotAssist low-speed Jog to position XB7. Release Jog, then\n"
        << "type a point name here. Every accepted point is saved immediately.\n"
        << "Commands: CURRENT, LIST, UNDO, QUIT\n"
        << "Suggested names: P_SAFE P_PRE P_EDGE_NEAR P_EDGE_IN P_PRESS\n";

    std::vector<xb7_points::PointRecord> points;
    std::set<std::string> used_names;
    while (!xb7_points::stop_requested.load()) {
      std::cout << "\nPoint name or command: " << std::flush;
      std::string input;
      if (!std::getline(std::cin, input)) break;
      input = xb7_points::trim(input);
      if (input == "QUIT" || input == "quit") break;
      if (input == "LIST" || input == "list") {
        printNames(points);
        continue;
      }
      if (input == "CURRENT" || input == "current") {
        try {
          rejectMovingState(robot);
          xb7_points::printPoint(readPoint(robot, "CURRENT"));
        } catch (const std::exception &error) {
          std::cout << "Cannot read current point: " << error.what() << '\n';
        }
        continue;
      }
      if (input == "UNDO" || input == "undo") {
        if (points.empty()) {
          std::cout << "Nothing to undo.\n";
        } else {
          used_names.erase(points.back().name);
          std::cout << "Removed " << points.back().name << ".\n";
          points.pop_back();
          xb7_points::writePointFile(output_path, info, tool_name,
                                     workobject_name, points);
        }
        continue;
      }
      if (!validIdentifier(input)) {
        std::cout << "Use 1-32 letters/digits/underscores; the first character "
                     "cannot be a digit.\n";
        continue;
      }
      if (used_names.count(input)) {
        std::cout << "Point name already exists. Use UNDO or another name.\n";
        continue;
      }

      try {
        const auto point = captureStablePoint(robot, input);
        points.push_back(point);
        used_names.insert(input);
        xb7_points::writePointFile(output_path, info, tool_name,
                                   workobject_name, points);
        xb7_points::printPoint(point);
        std::cout << "Saved immediately to " << output_path << ".\n";
      } catch (const std::exception &error) {
        std::cout << "Point rejected: " << error.what() << '\n';
      }
    }

    if (connected) {
      std::error_code ignored;
      robot.disconnectFromRobot(ignored);
    }
    std::cout << "Recorder stopped. No robot motion was commanded.\n";
    return 0;
  } catch (const std::exception &error) {
    if (connected) {
      std::error_code ignored;
      robot.disconnectFromRobot(ignored);
    }
    std::cerr << "ERROR: " << error.what()
              << "\nNo robot motion was commanded.\n";
    return 1;
  }
}
