/**
 * @file xb7_point_player.cpp
 * @brief Checked playback of points recorded by xb7_point_recorder.
 *
 * PLAN never connects to the robot. GO moves to one recorded joint point at a
 * low joint-speed ratio. RUN requires the robot to already match the first
 * point, checks the Cartesian path, then executes exact-stop MoveL commands.
 */

#include <array>
#include <chrono>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

#include "xb7_motion_safety.hpp"
#include "xb7_point_common.hpp"

namespace {

constexpr double kRunStartTranslationToleranceM = 0.002;  // 2 mm
constexpr double kRunStartRotationToleranceRad =
    2.0 * xb7_points::kDegToRad;
constexpr double kRunStartJointToleranceRad =
    2.0 * xb7_points::kDegToRad;
constexpr auto kMotionTimeout = std::chrono::seconds(300);

void printUsage(const char *program) {
  std::cerr
      << "Usage:\n"
      << "  " << program << " PLAN POINTS.csv\n"
      << "  " << program << " CHECK ROBOT_IP LOCAL_IP POINTS.csv\n"
      << "  " << program
      << " GO ROBOT_IP LOCAL_IP POINTS.csv POINT_NAME"
         " [JOINT_SPEED_RATIO] [MAX_START_DELTA_DEG]\n"
      << "  " << program
      << " RUN ROBOT_IP LOCAL_IP POINTS.csv"
         " [LINEAR_MM_S] [ROTATION_DEG_S]\n\n"
      << "Examples:\n"
      << "  " << program << " PLAN xb7_points_01.csv\n"
      << "  " << program
      << " CHECK 192.168.2.160 192.168.2.100 xb7_points_01.csv\n"
      << "  " << program
      << " GO 192.168.0.160 192.168.0.180 xb7_points_01.csv P_SAFE\n"
      << "  " << program
      << " RUN 192.168.0.160 192.168.0.180 xb7_points_01.csv 5 2\n";
}

struct SegmentSpeedConfig {
  double linear_speed_mm_s;
  double rotation_speed_rad_s;
  double distance_mm;
  double rotation_deg;
  double linear_time_s;
  double rotation_time_s;
  double segment_time_s;
};

inline std::vector<SegmentSpeedConfig> computeSegmentPlan(
    const xb7_points::PointFile &file,
    double default_linear_speed_mm_s,
    double default_rotation_speed_rad_s,
    bool override_all) {
  std::vector<SegmentSpeedConfig> configs;
  if (file.points.size() < 2) return configs;
  configs.reserve(file.points.size() - 1);

  for (std::size_t i = 1; i < file.points.size(); ++i) {
    const auto &p_prev = file.points[i - 1];
    const auto &p_curr = file.points[i];
    const double dist_m = xb7_points::translationDistance(
        p_prev.tcp_in_reference, p_curr.tcp_in_reference);
    const double dist_mm = dist_m * 1000.0;
    const double max_rot_rad = xb7_points::maximumRotationDistance(
        p_prev.tcp_in_reference, p_curr.tcp_in_reference);
    const double max_rot_deg = max_rot_rad * xb7_points::kRadToDeg;

    double v = default_linear_speed_mm_s;
    double w_rad = default_rotation_speed_rad_s;

    if (!override_all) {
      const auto it = file.segment_speeds.find(p_curr.name);
      if (it != file.segment_speeds.end()) {
        v = it->second.first;
        w_rad = it->second.second * xb7_points::kDegToRad;
      }
    }

    const double t_v = v > 1e-6 ? (dist_mm / v) : 0.0;
    const double w_deg = w_rad * xb7_points::kRadToDeg;
    const double t_w = w_deg > 1e-6 ? (max_rot_deg / w_deg) : 0.0;
    const double t_seg = std::max(t_v, t_w);

    configs.push_back({v, w_rad, dist_mm, max_rot_deg, t_v, t_w, t_seg});
  }
  return configs;
}

inline void printSegmentPlan(const xb7_points::PointFile &file,
                             const std::vector<SegmentSpeedConfig> &configs) {
  if (configs.empty()) return;
  std::cout << "\n--- Segment Speed & Timing Breakdown ---\n";
  double total_time = 0.0;
  double safe_to_insert_time = 0.0;
  bool reached_insert = false;

  for (std::size_t i = 0; i < configs.size(); ++i) {
    const auto &p_prev = file.points[i];
    const auto &p_curr = file.points[i + 1];
    const auto &cfg = configs[i];
    total_time += cfg.segment_time_s;
    if (!reached_insert) {
      safe_to_insert_time += cfg.segment_time_s;
      if (p_curr.name == "P_EDGE_IN") reached_insert = true;
    }

    std::cout << "  Seg " << (i + 1) << ": " << p_prev.name << " -> " << p_curr.name
              << "\n        dist=" << std::fixed << std::setprecision(2) << cfg.distance_mm << " mm"
              << ", rot=" << cfg.rotation_deg << " deg"
              << " | speed=" << cfg.linear_speed_mm_s << " mm/s"
              << ", rotSpeed=" << (cfg.rotation_speed_rad_s * xb7_points::kRadToDeg) << " deg/s"
              << " -> est. " << std::setprecision(1) << cfg.segment_time_s << " s\n";
  }
  std::cout << "----------------------------------------\n";
  if (reached_insert) {
    std::cout << "  Safe -> Insertion point : ~" << std::fixed << std::setprecision(1) << safe_to_insert_time << " s\n"
              << "  Insertion -> Final press: ~" << (total_time - safe_to_insert_time) << " s\n";
  }
  std::cout << "  Total trajectory duration: ~" << std::fixed << std::setprecision(1) << total_time << " s\n\n";
}

void printPlan(const xb7_points::PointFile &file) {
  std::cout << "Recorded robot : " << file.robot << '\n'
            << "Controller     : " << file.controller << '\n'
            << "Recorded SDK   : " << file.sdk << '\n'
            << "Tool/workobject: " << file.tool << " / " << file.workobject
            << '\n'
            << "Points         : " << file.points.size() << "\n\n";
  for (const auto &point : file.points) xb7_points::printPoint(point);
  const auto configs = computeSegmentPlan(file, 0.2, 0.2 * xb7_points::kDegToRad, false);
  printSegmentPlan(file, configs);
}

void verifyRecordedRobot(const xb7_points::PointFile &file,
                         const rokae::Info &actual) {
  if (!file.robot.empty() && file.robot != actual.type) {
    throw std::runtime_error("recorded robot type '" + file.robot +
                             "' does not match connected robot '" +
                             actual.type + "'");
  }
}

std::array<double, 6> currentReferencePose(rokae::StandardRobot &robot) {
  std::error_code ec;
  const auto pose = robot.cartPosture(rokae::CoordinateType::endInRef, ec);
  xb7_points::requireOk(ec, "read current TCP in selected workobject");
  return xb7_points::poseArray(pose);
}

void printJointTransition(const std::array<double, 6> &current,
                          const std::array<double, 6> &target) {
  std::cout << std::fixed << std::setprecision(3)
            << "Current joints [deg]: ";
  for (double value : current) std::cout << value * xb7_points::kRadToDeg << ' ';
  std::cout << "\nTarget joints  [deg]: ";
  for (double value : target) std::cout << value * xb7_points::kRadToDeg << ' ';
  std::cout << '\n';
}

void executeGo(rokae::StandardRobot &robot,
               const xb7_points::PointRecord &point,
               double joint_speed_ratio,
               double max_start_delta_rad) {
  xb7_points::requireStationary(robot);
  std::error_code ec;
  const auto current = robot.jointPos(ec);
  xb7_points::requireOk(ec, "read current joints");
  xb7_points::checkSoftLimits(robot, current);
  xb7_points::checkSoftLimits(robot, point.joints);

  const double maximum_delta =
      xb7_points::maximumJointDistance(current, point.joints);
  printJointTransition(current, point.joints);
  std::cout << "Maximum joint change: "
            << maximum_delta * xb7_points::kRadToDeg << " deg\n";
  if (maximum_delta > max_start_delta_rad) {
    throw std::runtime_error(
        "target is farther than the configured start-delta limit; use "
        "RobotAssist low-speed Jog to approach it first");
  }

  std::cout << "GO will power XB7 and execute one MoveAbsJ to " << point.name
            << " at " << joint_speed_ratio * 100.0
            << "% joint speed, fine stop. Keep E-stop reachable.\n";
  if (!xb7_points::confirm("ARM_XB7_GO")) {
    std::cout << "Cancelled before power-on.\n";
    return;
  }

  xb7_points::enterNrtAutomatic(robot);
  robot.adjustAcceleration(0.2, 0.1, ec);
  xb7_points::requireOk(ec, "set minimum acceleration/jerk percentages");
  rokae::MoveAbsJCommand command(
      std::vector<double>(point.joints.begin(), point.joints.end()), 10.0, 0.0);
  command.jointSpeed = joint_speed_ratio;
  command.customInfo = point.name;
  std::string command_id;
  robot.moveAppend(command, command_id, ec);
  xb7_points::requireOk(ec, "append MoveAbsJ command");
  robot.moveStart(ec);
  xb7_points::requireOk(ec, "start MoveAbsJ command");
  xb7_points::waitForCommand(robot, command_id, 0, kMotionTimeout);
  std::cout << "Reached " << point.name << ".\n";
}

void verifyRunStart(rokae::StandardRobot &robot,
                    const xb7_points::PointRecord &first) {
  std::error_code ec;
  const auto current_joints = robot.jointPos(ec);
  xb7_points::requireOk(ec, "read current joints");
  const auto current_tcp = currentReferencePose(robot);
  const double translation = xb7_points::translationDistance(
      current_tcp, first.tcp_in_reference);
  const double rotation = xb7_points::maximumRotationDistance(
      current_tcp, first.tcp_in_reference);
  const double joint =
      xb7_points::maximumJointDistance(current_joints, first.joints);
  if (translation > kRunStartTranslationToleranceM ||
      rotation > kRunStartRotationToleranceRad ||
      joint > kRunStartJointToleranceRad) {
    std::ostringstream message;
    message << std::fixed << std::setprecision(3)
            << "XB7 is not at first point " << first.name
            << ": TCP delta=" << translation * 1000.0
            << " mm, rotation delta=" << rotation * xb7_points::kRadToDeg
            << " deg, joint delta=" << joint * xb7_points::kRadToDeg
            << " deg. Run GO " << first.name << " first.";
    throw std::runtime_error(message.str());
  }
}

void checkLinearPath(rokae::StandardRobot &robot,
                     const xb7_points::PointFile &file,
                     bool use_recorded_start = false) {
  std::error_code ec;
  std::vector<double> start_joints;
  if (use_recorded_start) {
    start_joints.assign(file.points.front().joints.begin(),
                        file.points.front().joints.end());
  } else {
    const auto current = robot.jointPos(ec);
    xb7_points::requireOk(ec, "read current joints for path check");
    start_joints.assign(current.begin(), current.end());
  }
  std::vector<rokae::CartesianPosition> waypoints;
  waypoints.reserve(file.points.size());
  for (const auto &point : file.points) {
    waypoints.push_back(xb7_points::cartesianPoint(point.tcp_in_reference));
  }
  std::vector<double> calculated_target;
  const auto error_index =
      robot.checkPath(start_joints, waypoints, calculated_target, ec);
  if (ec) {
    throw std::runtime_error("Cartesian path check failed at point index " +
                             std::to_string(error_index) + ": " +
                             ec.message());
  }
  std::cout << "Controller path check passed for " << waypoints.size()
            << " points.\n";
}

void executeRun(rokae::StandardRobot &robot,
                const xb7_points::PointFile &file,
                double default_linear_speed_mm_s,
                double default_rotation_speed_rad_s,
                bool override_speeds = false) {
  if (file.points.size() < 2) {
    throw std::runtime_error("RUN requires at least two recorded points");
  }
  xb7_points::requireStationary(robot);
  verifyRunStart(robot, file.points.front());
  for (const auto &point : file.points) {
    xb7_points::checkSoftLimits(robot, point.joints);
  }
  checkLinearPath(robot, file);

  const auto configs = computeSegmentPlan(
      file, default_linear_speed_mm_s, default_rotation_speed_rad_s,
      override_speeds);
  printSegmentPlan(file, configs);

  std::cout << "RUN will power XB7 and execute " << file.points.size() - 1
            << " exact-stop Cartesian segments. Keep E-stop reachable.\n";
  if (!xb7_points::confirm("ARM_XB7_RUN")) {
    std::cout << "Cancelled before power-on.\n";
    return;
  }

  std::error_code ec;
  xb7_points::enterNrtAutomatic(robot);
  robot.adjustAcceleration(0.2, 0.1, ec);
  xb7_points::requireOk(ec, "set minimum acceleration/jerk percentages");
  robot.setDefaultConfOpt(false, ec);
  xb7_points::requireOk(ec, "select nearest inverse-kinematics solution");

  std::vector<rokae::MoveLCommand> commands;
  commands.reserve(file.points.size() - 1);
  // The current pose has already been verified against points.front().
  // Do not command the start point again: on contact paths that could add an
  // unnecessary final press before a reverse extraction.
  for (std::size_t i = 1; i < file.points.size(); ++i) {
    const auto &point = file.points[i];
    const auto &cfg = configs[i - 1];
    rokae::MoveLCommand command(
        xb7_points::cartesianPoint(point.tcp_in_reference),
        cfg.linear_speed_mm_s, 0.0);
    command.rotSpeed = cfg.rotation_speed_rad_s;
    command.customInfo = point.name;
    commands.push_back(command);
  }

  std::string command_id;
  robot.moveAppend(commands, command_id, ec);
  xb7_points::requireOk(ec, "append MoveL point sequence");
  robot.moveStart(ec);
  xb7_points::requireOk(ec, "start MoveL point sequence");
  xb7_points::waitForCommand(
      robot, command_id, static_cast<int>(commands.size()) - 1,
      kMotionTimeout);
  std::cout << "Recorded point sequence completed.\n";
}

}  // namespace

int main(int argc, char **argv) {
  if (argc < 3) {
    printUsage(argv[0]);
    return 2;
  }

  const std::string mode = argv[1];
  try {
    if (mode == "PLAN" || mode == "plan") {
      if (argc != 3) {
        printUsage(argv[0]);
        return 2;
      }
      printPlan(xb7_points::loadPointFile(argv[2]));
      std::cout << "PLAN made no robot connection and sent no motion.\n";
      return 0;
    }

    const bool check_mode = mode == "CHECK" || mode == "check";
    if (mode != "GO" && mode != "go" && mode != "RUN" && mode != "run" &&
        !check_mode) {
      printUsage(argv[0]);
      return 2;
    }
    if (check_mode && argc != 5) {
      printUsage(argv[0]);
      return 2;
    }
    if ((mode == "GO" || mode == "go") && (argc < 6 || argc > 8)) {
      printUsage(argv[0]);
      return 2;
    }
    if ((mode == "RUN" || mode == "run") && (argc < 5 || argc > 7)) {
      printUsage(argv[0]);
      return 2;
    }

    const std::string robot_ip = argv[2];
    const std::string local_ip = argv[3];
    const auto file = xb7_points::loadPointFile(argv[4]);
    printPlan(file);
    xb7_points::installSignalHandlers();

    rokae::StandardRobot robot;
    bool connected = false;
    try {
      std::cout << "Connecting to XB7 " << robot_ip << " from " << local_ip
                << "...\n";
      robot.connectToRobot(robot_ip, local_ip);
      connected = true;
      const auto info = xb7_points::verifyXB7(robot);
      verifyRecordedRobot(file, info);
      std::error_code ec;
      robot.setToolset(file.tool, file.workobject, ec);
      xb7_points::requireOk(ec, "select recorded tool/workobject");

      if (check_mode) {
        for (const auto &point : file.points) {
          xb7_points::checkSoftLimits(robot, point.joints);
        }
        checkLinearPath(robot, file, true);
        std::cout << "CHECK completed without power-on or motion.\n";
        if (connected) {
          std::error_code ignored;
          robot.disconnectFromRobot(ignored);
        }
        return 0;
      }

      if (mode == "GO" || mode == "go") {
        const auto found = file.by_name.find(argv[5]);
        if (found == file.by_name.end()) {
          throw std::runtime_error("point not found: " + std::string(argv[5]));
        }
        const double speed = argc >= 7
            ? xb7_points::parseNumber(argv[6], 0.005, 0.10,
                                      "joint_speed_ratio")
            : 0.02;
        const double max_delta = argc >= 8
            ? xb7_points::parseNumber(argv[7], 1.0, 90.0,
                                      "max_start_delta_deg") *
                  xb7_points::kDegToRad
            : 30.0 * xb7_points::kDegToRad;
        executeGo(robot, file.points[found->second], speed, max_delta);
      } else {
        const bool override_speeds = (argc >= 6);
        const double linear_speed = override_speeds
            ? xb7_points::parseNumber(argv[5], 0.05, 50.0,
                                      "linear_speed_mm_s")
            : 0.2;
        const double rotation_speed = argc >= 7
            ? xb7_points::parseNumber(argv[6], 0.05, 10.0,
                                      "rotation_speed_deg_s") *
                  xb7_points::kDegToRad
            : (override_speeds ? linear_speed * xb7_points::kDegToRad
                               : 0.2 * xb7_points::kDegToRad);
        executeRun(robot, file, linear_speed, rotation_speed, override_speeds);
      }

      if (connected) xb7_points::safeShutdown(robot);
      return 0;
    } catch (...) {
      if (connected) xb7_points::safeShutdown(robot);
      throw;
    }
  } catch (const std::exception &error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
