#ifndef XB7_POINT_CONTROL_XB7_POINT_COMMON_HPP_
#define XB7_POINT_CONTROL_XB7_POINT_COMMON_HPP_

#include <algorithm>
#include <any>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include "rokae/robot.h"

namespace xb7_points {

constexpr double kPi = 3.14159265358979323846;
constexpr double kDegToRad = kPi / 180.0;
constexpr double kRadToDeg = 180.0 / kPi;
constexpr double kSoftLimitMarginRad = 3.0 * kDegToRad;

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

inline std::string trim(std::string text) {
  while (!text.empty() &&
         (text.back() == '\r' || text.back() == '\n' || text.back() == ' ')) {
    text.pop_back();
  }
  const auto first = text.find_first_not_of(" \t");
  return first == std::string::npos ? std::string{} : text.substr(first);
}

inline std::vector<std::string> splitCsv(const std::string &line) {
  std::vector<std::string> fields;
  std::stringstream input(line);
  std::string field;
  while (std::getline(input, field, ',')) fields.push_back(trim(field));
  return fields;
}

inline double parseCell(const std::vector<std::string> &cells,
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
  std::map<std::string, std::size_t> by_name;
  std::map<std::string, std::pair<double, double>> segment_speeds;
};

inline std::array<double, 6> poseArray(
    const rokae::CartesianPosition &pose) {
  return {pose.trans[0], pose.trans[1], pose.trans[2],
          pose.rpy[0], pose.rpy[1], pose.rpy[2]};
}

inline rokae::CartesianPosition cartesianPoint(
    const std::array<double, 6> &pose) {
  rokae::CartesianPosition point;
  for (std::size_t i = 0; i < 3; ++i) {
    point.trans[i] = pose[i];
    point.rpy[i] = pose[3 + i];
  }
  point.confData.clear();
  return point;
}

inline double wrappedAngleDistance(double a, double b) {
  return std::abs(std::remainder(a - b, 2.0 * kPi));
}

inline double translationDistance(const std::array<double, 6> &a,
                                  const std::array<double, 6> &b) {
  const double dx = a[0] - b[0];
  const double dy = a[1] - b[1];
  const double dz = a[2] - b[2];
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

inline double maximumRotationDistance(const std::array<double, 6> &a,
                                      const std::array<double, 6> &b) {
  double maximum = 0.0;
  for (std::size_t i = 3; i < 6; ++i) {
    maximum = std::max(maximum, wrappedAngleDistance(a[i], b[i]));
  }
  return maximum;
}

inline double maximumJointDistance(const std::array<double, 6> &a,
                                   const std::array<double, 6> &b) {
  double maximum = 0.0;
  for (std::size_t i = 0; i < 6; ++i) {
    maximum = std::max(maximum, wrappedAngleDistance(a[i], b[i]));
  }
  return maximum;
}

inline rokae::Info verifyXB7(rokae::StandardRobot &robot) {
  std::error_code ec;
  const auto info = robot.robotInfo(ec);
  requireOk(ec, "read robot information");
  if (info.joint_num != 6) {
    throw std::runtime_error("XB7 point tools require a six-axis robot");
  }
  std::cout << "Robot type : " << info.type << '\n'
            << "Controller : " << info.version << '\n'
            << "SDK        : " << rokae::BaseRobot::sdkVersion() << '\n';
  return info;
}

inline void printPoint(const PointRecord &point) {
  std::cout << std::fixed << std::setprecision(4)
            << point.name << "\n  TCP in selected reference [";
  for (std::size_t i = 0; i < 3; ++i) {
    if (i) std::cout << ", ";
    std::cout << point.tcp_in_reference[i] * 1000.0;
  }
  std::cout << " mm | ";
  for (std::size_t i = 3; i < 6; ++i) {
    if (i != 3) std::cout << ", ";
    std::cout << point.tcp_in_reference[i] * kRadToDeg;
  }
  std::cout << " deg]\n  J1..J6 [";
  for (std::size_t i = 0; i < point.joints.size(); ++i) {
    if (i) std::cout << ", ";
    std::cout << point.joints[i] * kRadToDeg;
  }
  std::cout << "] deg\n";
}

inline void writePointFile(const std::string &path,
                           const rokae::Info &info,
                           const std::string &tool,
                           const std::string &workobject,
                           const std::vector<PointRecord> &points) {
  const std::string temporary = path + ".tmp";
  std::ofstream output(temporary, std::ios::out | std::ios::trunc);
  if (!output) throw std::runtime_error("cannot write: " + temporary);
  output << "# format,xb7_point_v1\n"
         << "# robot," << info.type << '\n'
         << "# controller," << info.version << '\n'
         << "# sdk," << rokae::BaseRobot::sdkVersion() << '\n'
         << "# tool," << tool << '\n'
         << "# workobject," << workobject << '\n'
         << "# linear_unit,m\n"
         << "# angular_unit,rad\n"
         << "name,ref_x,ref_y,ref_z,ref_rx,ref_ry,ref_rz,"
            "flange_base_x,flange_base_y,flange_base_z,"
            "flange_base_rx,flange_base_ry,flange_base_rz,"
            "j1,j2,j3,j4,j5,j6\n";
  output << std::setprecision(17);
  for (const auto &point : points) {
    output << point.name;
    for (double value : point.tcp_in_reference) output << ',' << value;
    for (double value : point.flange_in_base) output << ',' << value;
    for (double value : point.joints) output << ',' << value;
    output << '\n';
  }
  output.close();
  if (!output) throw std::runtime_error("failed while writing: " + temporary);

  std::error_code fs_error;
  std::filesystem::rename(temporary, path, fs_error);
  if (fs_error) {
    std::filesystem::remove(temporary);
    throw std::runtime_error("cannot replace output file: " +
                             fs_error.message());
  }
}

inline PointFile loadPointFile(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open CSV: " + path);

  PointFile result;
  std::string line;
  while (std::getline(input, line)) {
    line = trim(line);
    if (line.empty()) continue;
    const auto cells = splitCsv(line);
    if (line[0] == '#') {
      if (cells.size() >= 2 && cells[0] == "# robot") result.robot = cells[1];
      if (cells.size() >= 2 && cells[0] == "# controller") {
        result.controller = cells[1];
      }
      if (cells.size() >= 2 && cells[0] == "# sdk") result.sdk = cells[1];
      if (cells.size() >= 2 && cells[0] == "# tool") result.tool = cells[1];
      if (cells.size() >= 2 && cells[0] == "# workobject") {
        result.workobject = cells[1];
      }
      if (cells.size() >= 3 &&
          (cells[0] == "# segment_speed" || cells[0] == "# speed")) {
        const double v = std::stod(cells[2]);
        const double w = cells.size() >= 4 ? std::stod(cells[3]) : 1.0;
        result.segment_speeds[cells[1]] = {v, w};
      }
      continue;
    }
    if (cells[0] == "name") continue;
    if (cells.size() != 19) {
      throw std::runtime_error(
          "expected 19 CSV fields for an XB7 point: " + line);
    }
    PointRecord point;
    point.name = cells[0];
    if (point.name.empty()) throw std::runtime_error("empty point name");
    for (std::size_t i = 0; i < 6; ++i) {
      point.tcp_in_reference[i] = parseCell(cells, 1 + i, line);
      point.flange_in_base[i] = parseCell(cells, 7 + i, line);
      point.joints[i] = parseCell(cells, 13 + i, line);
    }
    if (result.by_name.count(point.name)) {
      throw std::runtime_error("duplicate point name: " + point.name);
    }
    result.by_name.emplace(point.name, result.points.size());
    result.points.push_back(point);
  }
  if (result.points.empty()) throw std::runtime_error("CSV has no points");
  if (result.tool.empty() || result.workobject.empty()) {
    throw std::runtime_error("CSV is missing tool/workobject metadata");
  }
  return result;
}

inline void checkSoftLimits(rokae::StandardRobot &robot,
                            const std::array<double, 6> &joints) {
  std::array<double[2], 6> limits{};
  std::error_code ec;
  const bool enabled = robot.getSoftLimit(limits, ec);
  requireOk(ec, "read joint soft limits");
  if (!enabled) {
    throw std::runtime_error(
        "joint soft limits are disabled; enable them in RobotAssist first");
  }
  for (std::size_t i = 0; i < joints.size(); ++i) {
    if (joints[i] - limits[i][0] < kSoftLimitMarginRad ||
        limits[i][1] - joints[i] < kSoftLimitMarginRad) {
      throw std::runtime_error("recorded J" + std::to_string(i + 1) +
                               " is within 3 deg of a soft limit");
    }
  }
}

}  // namespace xb7_points

#endif  // XB7_POINT_CONTROL_XB7_POINT_COMMON_HPP_
