/**
 * @file ar_four_point_smooth_trajectory.cpp
 * @brief Checked Cartesian assembly trajectory with optional S-clearance bump.
 *
 * Reads P_SAFE, P_EDGE_NEAR, P_EDGE_IN and P_PRESS from a CSV produced by
 * ar_teach_point_recorder. PLAN is motion-free. RUN requires the measured
 * robot to already match the recorded P_SAFE pose/configuration. GO_SAFE uses
 * a controller-native MoveAbsJ from the current joint pose to the taught
 * P_SAFE joint configuration. AUTO performs GO_SAFE and then the Cartesian
 * assembly trajectory in one armed sequence. When P_COLLISION_NEAR and
 * P_CLEAR are present, a local quintic vertical (+reference Z) clearance hump
 * replaces the original straight P_EDGE_NEAR -> P_EDGE_IN segment. X/Y and
 * orientation remain on the original taught interpolation; P_CLEAR contributes
 * only the measured vertical clearance height.
 *
 * Execution deliberately uses the controller's supported non-real-time MoveL
 * planner instead of a custom RT loop. Primary assembly points use zone=0;
 * generated S-bump samples use a controller blending zone. Acceleration and
 * jerk are set to their documented minimum percentages.
 *
 * WIDE_PLAN/WIDE_TEST/WIDE_RUN implement a derived wide-clearance strategy:
 * move to the measured rear p6 point, descend while retaining the
 * taught tilted P_EDGE_IN orientation, stop just above P_EDGE_IN Z, then move
 * forward and downward together while keeping the tilted orientation until
 * the exact taught P_EDGE_IN, and only then rotate/press to measured p8.
 * Its intermediate poses are generated rather than taught. WIDE_PLAN is
 * read-only, WIDE_TEST stops at P_EDGE_IN, and WIDE_RUN ends at p8.
 * WIDE_REVERSE_PLAN/WIDE_REVERSE_TEST/WIDE_REVERSE_EXTRACT and
 * WIDE_REVERSE_RUN use the exact same
 * Cartesian waypoints in reverse order. The reverse test only releases the
 * final press and stops at P_EDGE_IN; WIDE_REVERSE_EXTRACT safely continues
 * from that point to P_SAFE. The reverse run performs both stages in one
 * command. Reverse motion is deliberately limited to 0.2 mm/s and 0.2 deg/s
 * regardless of the command-line fallback speeds.
 */

#include <algorithm>
#include <any>
#include <array>
#include <chrono>
#include <cmath>
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

#include <Eigen/Geometry>

#include "ar_demo_common.hpp"
#include "assembly_force_guard_hook.hpp"

namespace ar_assembly_guard {
Hook *active_hook = nullptr;
}

namespace {

constexpr std::array<const char *, 4> kRequiredNames{
    "P_SAFE", "P_EDGE_NEAR", "P_EDGE_IN", "P_PRESS"};
constexpr double kStartTranslationToleranceM = 0.002;  // 2 mm
constexpr double kStartRotationToleranceRad =
    2.0 * ar_demo::kDegToRad;
constexpr double kStartJointToleranceRad = 2.0 * ar_demo::kDegToRad;
constexpr double kSoftLimitMarginRad = 3.0 * ar_demo::kDegToRad;
constexpr double kGoSafeJointSpeedRatio = 0.01;  // 1% joint speed
constexpr int kSBumpRiseSamples = 6;
constexpr int kSBumpFallSamples = 6;
constexpr double kSBumpBlendZoneMm = 0.2;
constexpr double kSecondaryClearanceMarginM = 0.0005;  // 0.5 mm
constexpr int kEdgeArcSamples = 16;
constexpr int kHookArcSamples = 8;
// The wide path is generated from the existing taught points. WIDE_PLAN is
// read-only; WIDE_TEST/WIDE_RUN require separate explicit arm tokens because
// these intermediate points have not been individually taught.
// User-measured p6 in g_wobj_0, recorded with g_tool_1 (mm and degrees).
constexpr std::array<double, 6> kDraftBackP6MmDeg{
    224.7736, -337.1420, 2.0454, 175.2683, -1.1645, -154.7335};
constexpr double kDraftBackP6ElbowDeg = 1.2179;
// User-measured final assembled p8 in g_wobj_0 with g_tool_1.
constexpr std::array<double, 6> kDraftFinalP8MmDeg{
    228.7783, -343.0617, -5.8556, -174.7136, 0.7086, -153.7597};
constexpr double kDraftFinalP8ElbowDeg = 1.2180;
constexpr std::array<double, 7> kDraftFinalP8JointsDeg{
    -57.1849, 40.5560, 1.2179, 104.1058, -83.9149, 4.3928, -29.7263};
constexpr double kDraftPreInsertLiftM = 0.0005;    // above P_EDGE_IN
constexpr int kDraftWideInsertSamples = 12;
constexpr double kReverseLinearSpeedMmS = 0.2;
constexpr double kReverseRotationSpeedDegS = 0.2;

struct TaughtPoint {
  std::string name;
  std::array<double, 6> in_reference{};
  std::array<double, 6> in_base{};
  double elbow{};
  std::array<double, 7> joints{};
};

struct TaughtFile {
  std::string tool;
  std::string workobject;
  std::map<std::string, TaughtPoint> points;
};

struct ControllerPath {
  std::vector<rokae::CartesianPosition> points;
  std::vector<std::string> labels;
  std::vector<double> zones_mm;
  // Per-arrival-point speed. Zero means use the command-line fallback speed.
  std::vector<double> linear_speeds_mm_s;
  std::vector<double> rotation_speeds_deg_s;
  bool uses_clearance_bump{false};
  double collision_fraction{};
  std::array<double, 3> clearance_offset_m{};
  double ignored_clearance_lateral_m{};
  bool uses_secondary_clearance{false};
  double secondary_contact_fraction{};
  double secondary_safe_offset_m{};
  double secondary_bump_factor{};
  bool uses_yz_edge_arc{false};
  double third_contact_fraction{};
  double edge_arc_control_z_m{};
  double edge_arc_height_at_third_m{};
  bool uses_over_lip_hook{false};
  std::array<double, 3> hook_c3_high_m{};
  std::array<double, 3> hook_c4_high_m{};
  bool is_unmeasured_wide_preview{false};
  bool is_reverse_wide{false};
};

std::vector<std::string> splitCsv(const std::string &line) {
  std::vector<std::string> fields;
  std::stringstream input(line);
  std::string field;
  while (std::getline(input, field, ',')) fields.push_back(field);
  return fields;
}

double parseCell(const std::vector<std::string> &cells, std::size_t index,
                 const std::string &line) {
  if (index >= cells.size()) throw std::runtime_error("short CSV row: " + line);
  std::size_t used = 0;
  const double value = std::stod(cells[index], &used);
  if (used != cells[index].size() || !std::isfinite(value)) {
    throw std::runtime_error("invalid numeric CSV cell: " + cells[index]);
  }
  return value;
}

TaughtFile loadTaughtFile(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open CSV: " + path);
  TaughtFile result;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    const auto cells = splitCsv(line);
    if (line[0] == '#') {
      if (cells.size() >= 2 && cells[0] == "# tool") result.tool = cells[1];
      if (cells.size() >= 2 && cells[0] == "# workobject") {
        result.workobject = cells[1];
      }
      continue;
    }
    if (cells[0] == "name") continue;
    if (cells.size() < 21) {
      throw std::runtime_error("expected 21 CSV fields: " + line);
    }
    TaughtPoint point;
    point.name = cells[0];
    for (std::size_t i = 0; i < 6; ++i) {
      point.in_reference[i] = parseCell(cells, 1 + i, line);
      point.in_base[i] = parseCell(cells, 7 + i, line);
    }
    point.elbow = parseCell(cells, 13, line);
    for (std::size_t i = 0; i < 7; ++i) {
      point.joints[i] = parseCell(cells, 14 + i, line);
    }
    if (!result.points.emplace(point.name, point).second) {
      throw std::runtime_error("duplicate point name in CSV: " + point.name);
    }
  }
  for (const char *name : kRequiredNames) {
    if (!result.points.count(name)) {
      throw std::runtime_error(std::string("missing required point: ") + name);
    }
  }
  return result;
}

Eigen::Quaterniond quaternionFromRpy(const std::array<double, 6> &pose) {
  return Eigen::Quaterniond(
      Eigen::AngleAxisd(pose[5], Eigen::Vector3d::UnitZ()) *
      Eigen::AngleAxisd(pose[4], Eigen::Vector3d::UnitY()) *
      Eigen::AngleAxisd(pose[3], Eigen::Vector3d::UnitX()));
}

double translationDistance(const std::array<double, 6> &a,
                           const std::array<double, 6> &b) {
  const double dx = a[0] - b[0];
  const double dy = a[1] - b[1];
  const double dz = a[2] - b[2];
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

double rotationDistance(const std::array<double, 6> &a,
                        const std::array<double, 6> &b) {
  Eigen::Quaterniond qa = quaternionFromRpy(a).normalized();
  Eigen::Quaterniond qb = quaternionFromRpy(b).normalized();
  const double dot = std::min(1.0, std::abs(qa.dot(qb)));
  return 2.0 * std::acos(dot);
}

double maximumJointDistance(const std::array<double, 7> &a,
                            const std::array<double, 7> &b) {
  double result = 0.0;
  for (std::size_t i = 0; i < a.size(); ++i) {
    result = std::max(result, std::abs(a[i] - b[i]));
  }
  return result;
}

double unwrapNear(double angle, double reference) {
  while (angle - reference > ar_demo::kPi) angle -= 2.0 * ar_demo::kPi;
  while (angle - reference < -ar_demo::kPi) angle += 2.0 * ar_demo::kPi;
  return angle;
}

double quinticSmoothStep(double u) {
  u = std::clamp(u, 0.0, 1.0);
  return u * u * u * (10.0 + u * (-15.0 + 6.0 * u));
}

rokae::CartesianPosition taughtPose(const TaughtPoint &taught,
                                     const std::array<double, 3> *near_rpy) {
  rokae::CartesianPosition point;
  for (std::size_t i = 0; i < 3; ++i) {
    point.trans[i] = taught.in_reference[i];
    point.rpy[i] = taught.in_reference[3 + i];
    if (near_rpy) point.rpy[i] = unwrapNear(point.rpy[i], (*near_rpy)[i]);
  }
  point.elbow = taught.elbow;
  point.hasElbow = true;
  return point;
}

void appendPoint(ControllerPath &path, const std::string &label,
                 const rokae::CartesianPosition &point, double zone_mm,
                 double linear_speed_mm_s = 0.0,
                 double rotation_speed_deg_s = 0.0) {
  path.points.push_back(point);
  path.labels.push_back(label);
  path.zones_mm.push_back(zone_mm);
  path.linear_speeds_mm_s.push_back(linear_speed_mm_s);
  path.rotation_speeds_deg_s.push_back(rotation_speed_deg_s);
}

ControllerPath makeControllerPath(const TaughtFile &file) {
  ControllerPath path;
  const auto safe = taughtPose(file.points.at("P_SAFE"), nullptr);
  appendPoint(path, "P_SAFE", safe, 0.0);

  const auto edge_near =
      taughtPose(file.points.at("P_EDGE_NEAR"), &path.points.back().rpy);
  appendPoint(path, "P_EDGE_NEAR", edge_near, 0.0);

  const bool has_collision = file.points.count("P_COLLISION_NEAR") != 0;
  const bool has_clear = file.points.count("P_CLEAR") != 0;
  if (has_collision != has_clear) {
    throw std::runtime_error(
        "clearance path requires both P_COLLISION_NEAR and P_CLEAR");
  }

  const auto edge_in =
      taughtPose(file.points.at("P_EDGE_IN"), &path.points.back().rpy);
  if (has_collision) {
    const auto &collision = file.points.at("P_COLLISION_NEAR");
    const auto &clear = file.points.at("P_CLEAR");
    std::array<double, 3> line{};
    std::array<double, 3> from_start{};
    double line_sq = 0.0;
    double projection = 0.0;
    for (std::size_t axis = 0; axis < 3; ++axis) {
      line[axis] = edge_in.trans[axis] - edge_near.trans[axis];
      from_start[axis] =
          collision.in_reference[axis] - edge_near.trans[axis];
      line_sq += line[axis] * line[axis];
      projection += from_start[axis] * line[axis];
    }
    if (line_sq < 1e-8) {
      throw std::runtime_error("P_EDGE_NEAR and P_EDGE_IN are too close");
    }
    const double s_collision = projection / line_sq;
    path.collision_fraction = s_collision;
    if (s_collision < 0.1 || s_collision > 0.9) {
      throw std::runtime_error(
          "P_COLLISION_NEAR is not inside the middle 80% of the insertion "
          "segment");
    }

    std::array<double, 6> collision_nominal{};
    std::array<double, 6> collision_recorded = collision.in_reference;
    double residual_sq = 0.0;
    for (std::size_t axis = 0; axis < 3; ++axis) {
      collision_nominal[axis] =
          edge_near.trans[axis] + s_collision * line[axis];
      const double residual =
          collision.in_reference[axis] - collision_nominal[axis];
      residual_sq += residual * residual;
    }
    const double residual_m = std::sqrt(residual_sq);
    if (residual_m > 0.001) {
      throw std::runtime_error(
          "P_COLLISION_NEAR is more than 1 mm away from the original "
          "P_EDGE_NEAR -> P_EDGE_IN line");
    }

    // P_CLEAR is deliberately used only as a height measurement. Applying its
    // full XYZ delta would reproduce hand/Jog lateral error and move the tool
    // away from the original insertion centreline.
    path.clearance_offset_m = {
        0.0, 0.0,
        clear.in_reference[2] - collision.in_reference[2]};
    const double lateral_dx =
        clear.in_reference[0] - collision.in_reference[0];
    const double lateral_dy =
        clear.in_reference[1] - collision.in_reference[1];
    path.ignored_clearance_lateral_m =
        std::sqrt(lateral_dx * lateral_dx + lateral_dy * lateral_dy);
    const double vertical_clearance_m = path.clearance_offset_m[2];
    if (vertical_clearance_m < 0.0005 || vertical_clearance_m > 0.010) {
      throw std::runtime_error(
          "P_CLEAR must be 0.5 mm to 10 mm above P_COLLISION_NEAR in "
          "reference Z");
    }

    const bool has_contact_2 = file.points.count("P_CONTACT_2") != 0;
    const bool has_clear_2 = file.points.count("P_CLEAR_2") != 0;
    if (has_contact_2 != has_clear_2) {
      throw std::runtime_error(
          "secondary clearance requires both P_CONTACT_2 and P_CLEAR_2");
    }
    if (has_contact_2) {
      const auto &contact_2 = file.points.at("P_CONTACT_2");
      const auto &clear_2 = file.points.at("P_CLEAR_2");
      const double line_xy_sq = line[0] * line[0] + line[1] * line[1];
      if (line_xy_sq < 1e-10) {
        throw std::runtime_error(
            "cannot locate P_CONTACT_2 because insertion XY motion is too "
            "small");
      }
      const double s_contact_2 =
          ((contact_2.in_reference[0] - edge_near.trans[0]) * line[0] +
           (contact_2.in_reference[1] - edge_near.trans[1]) * line[1]) /
          line_xy_sq;
      if (s_contact_2 <= s_collision || s_contact_2 >= 0.98) {
        throw std::runtime_error(
            "P_CONTACT_2 must be after P_COLLISION_NEAR and before the last "
            "2% of the insertion segment");
      }
      const double nominal_x_2 =
          edge_near.trans[0] + s_contact_2 * line[0];
      const double nominal_y_2 =
          edge_near.trans[1] + s_contact_2 * line[1];
      const double residual_x_2 =
          contact_2.in_reference[0] - nominal_x_2;
      const double residual_y_2 =
          contact_2.in_reference[1] - nominal_y_2;
      if (std::hypot(residual_x_2, residual_y_2) > 0.001) {
        throw std::runtime_error(
            "P_CONTACT_2 is more than 1 mm laterally from the original "
            "insertion centreline");
      }
      if (std::hypot(clear_2.in_reference[0] - contact_2.in_reference[0],
                     clear_2.in_reference[1] - contact_2.in_reference[1]) >
          0.001) {
        throw std::runtime_error(
            "P_CLEAR_2 must be recorded within 1 mm XY of P_CONTACT_2");
      }
      const double measured_lift_2 =
          clear_2.in_reference[2] - contact_2.in_reference[2];
      if (measured_lift_2 < 0.0005 || measured_lift_2 > 0.010) {
        throw std::runtime_error(
            "P_CLEAR_2 must be 0.5 mm to 10 mm above P_CONTACT_2");
      }

      const double nominal_z_2 =
          edge_near.trans[2] + s_contact_2 * line[2];
      const double safe_offset_2 =
          clear_2.in_reference[2] - nominal_z_2;
      const double fall_u =
          (s_contact_2 - s_collision) / (1.0 - s_collision);
      const double bump_factor_2 = 1.0 - quinticSmoothStep(fall_u);
      if (safe_offset_2 <= 0.0 || bump_factor_2 < 0.05) {
        throw std::runtime_error(
            "P_CONTACT_2/P_CLEAR_2 cannot define a safe clearance hump");
      }
      const double required_peak_2 =
          (safe_offset_2 + kSecondaryClearanceMarginM) / bump_factor_2;
      path.clearance_offset_m[2] = std::max(
          path.clearance_offset_m[2] + kSecondaryClearanceMarginM,
          required_peak_2);
      if (path.clearance_offset_m[2] > 0.010) {
        throw std::runtime_error(
            "secondary clearance requires a peak above the 10 mm safety "
            "limit; record a different path");
      }
      path.uses_secondary_clearance = true;
      path.secondary_contact_fraction = s_contact_2;
      path.secondary_safe_offset_m = safe_offset_2;
      path.secondary_bump_factor = bump_factor_2;
    }

    for (std::size_t axis = 0; axis < 3; ++axis) {
      collision_nominal[3 + axis] =
          edge_near.rpy[axis] +
          s_collision * (edge_in.rpy[axis] - edge_near.rpy[axis]);
    }
    if (rotationDistance(collision_nominal, collision_recorded) >
        1.0 * ar_demo::kDegToRad) {
      throw std::runtime_error(
          "P_COLLISION_NEAR orientation differs from the nominal insertion "
          "orientation by more than 1 deg");
    }
    const bool has_p3 = file.points.count("p3") != 0;
    const bool has_c3 = file.points.count("c3") != 0;
    if (has_p3 != has_c3) {
      throw std::runtime_error(
          "Y-Z edge arc requires both lowercase p3 and c3 points");
    }
    const bool has_p4 = file.points.count("p4") != 0;
    const bool has_c4 = file.points.count("c4") != 0;
    if (has_p4 != has_c4) {
      throw std::runtime_error(
          "over-lip hook requires both lowercase p4 and c4 points");
    }
    if (has_p4 && !has_p3) {
      throw std::runtime_error(
          "over-lip hook requires the earlier p3/c3 clearance pair");
    }

    auto append_bump_sample = [&](double s, double bump,
                                  const std::string &label,
                                  double zone_mm) {
      rokae::CartesianPosition point;
      for (std::size_t axis = 0; axis < 3; ++axis) {
        point.trans[axis] = edge_near.trans[axis] + s * line[axis] +
                            bump * path.clearance_offset_m[axis];
        point.rpy[axis] = edge_near.rpy[axis] +
                          s * (edge_in.rpy[axis] - edge_near.rpy[axis]);
      }
      point.elbow = edge_near.elbow +
                    s * (edge_in.elbow - edge_near.elbow);
      point.hasElbow = true;
      appendPoint(path, label, point, zone_mm);
    };

    if (has_p3) {
      const auto &contact_3 = file.points.at("p3");
      const auto &clear_3 = file.points.at("c3");
      const double line_xy_sq = line[0] * line[0] + line[1] * line[1];
      const double s_contact_3 =
          ((contact_3.in_reference[0] - edge_near.trans[0]) * line[0] +
           (contact_3.in_reference[1] - edge_near.trans[1]) * line[1]) /
          line_xy_sq;
      if (s_contact_3 < 0.90 || s_contact_3 >= 0.99) {
        throw std::runtime_error(
            "p3 must lie between 90% and 99% of the insertion XY path");
      }
      const double nominal_x_3 =
          edge_near.trans[0] + s_contact_3 * line[0];
      const double nominal_y_3 =
          edge_near.trans[1] + s_contact_3 * line[1];
      if (std::hypot(contact_3.in_reference[0] - nominal_x_3,
                     contact_3.in_reference[1] - nominal_y_3) > 0.001) {
        throw std::runtime_error(
            "p3 is more than 1 mm laterally from the insertion centreline");
      }
      if (std::hypot(clear_3.in_reference[0] - contact_3.in_reference[0],
                     clear_3.in_reference[1] - contact_3.in_reference[1]) >
          0.001) {
        throw std::runtime_error("c3 must be recorded within 1 mm XY of p3");
      }
      const double clear_lift_3 =
          clear_3.in_reference[2] - contact_3.in_reference[2];
      if (clear_lift_3 < 0.0005 || clear_lift_3 > 0.010) {
        throw std::runtime_error("c3 must be 0.5 mm to 10 mm above p3");
      }

      if (has_p4) {
        const auto &contact_4 = file.points.at("p4");
        const auto &clear_4 = file.points.at("c4");
        const double p4_dx = contact_4.in_reference[0] - edge_in.trans[0];
        const double p4_dy = contact_4.in_reference[1] - edge_in.trans[1];
        const double p4_dz = contact_4.in_reference[2] - edge_in.trans[2];
        if (std::sqrt(p4_dx * p4_dx + p4_dy * p4_dy + p4_dz * p4_dz) >
            0.001) {
          throw std::runtime_error(
              "p4 must be within 1 mm of the recorded P_EDGE_IN");
        }
        if (clear_4.in_reference[1] - contact_4.in_reference[1] < 0.0005 ||
            clear_4.in_reference[2] - contact_4.in_reference[2] < 0.0005) {
          throw std::runtime_error(
              "c4 must be at least 0.5 mm farther in +Y and +Z than p4");
        }

        auto c3_high = taughtPose(clear_3, &edge_near.rpy);
        c3_high.trans[2] += kSecondaryClearanceMarginM;
        auto c4_high = taughtPose(clear_4, &c3_high.rpy);
        c4_high.trans[2] += kSecondaryClearanceMarginM;

        // Stay above the measured clearance envelope while approaching the
        // lip, then overshoot it in +Y. P_SAFE remains the global approach;
        // c4 is a local, behind-the-lip waypoint and does not replace P_SAFE.
        appendPoint(path, "P_CLEAR_BEFORE_LIP", c3_high,
                    kSBumpBlendZoneMm);

        auto append_quadratic = [&](const rokae::CartesianPosition &start,
                                    const std::array<double, 3> &control,
                                    const rokae::CartesianPosition &finish,
                                    const std::string &prefix,
                                    const std::string &last_label,
                                    double last_zone) {
          for (int i = 1; i <= kHookArcSamples; ++i) {
            const double t = static_cast<double>(i) / kHookArcSamples;
            const double omt = 1.0 - t;
            const double blend = quinticSmoothStep(t);
            rokae::CartesianPosition point;
            for (std::size_t axis = 0; axis < 3; ++axis) {
              point.trans[axis] =
                  omt * omt * start.trans[axis] +
                  2.0 * omt * t * control[axis] +
                  t * t * finish.trans[axis];
              point.rpy[axis] =
                  start.rpy[axis] +
                  blend * (finish.rpy[axis] - start.rpy[axis]);
            }
            point.elbow =
                start.elbow + blend * (finish.elbow - start.elbow);
            point.hasElbow = true;
            const bool last = i == kHookArcSamples;
            appendPoint(path,
                        last ? last_label : prefix + std::to_string(i),
                        point, last ? last_zone : kSBumpBlendZoneMm);
          }
        };

        // First quarter-arc: move behind the lip in +Y while staying high,
        // then bend downward into the measured c4-behind-lip region.
        const std::array<double, 3> over_lip_control{
            c4_high.trans[0], c4_high.trans[1], c3_high.trans[2]};
        append_quadratic(c3_high, over_lip_control, c4_high,
                         "HOOK_OVER_", "P_BEHIND_LIP", kSBumpBlendZoneMm);

        // The lower side of the shell is obstructed, so never descend at c4's
        // behind-the-lip Y. First settle to the measured c4 height, translate
        // forward in -Y at constant Z to a point directly above the original
        // P_EDGE_IN, and only then descend at the correct insertion X/Y.
        auto c4_low = taughtPose(clear_4, &c4_high.rpy);
        appendPoint(path, "P_BEHIND_LIP_LOW", c4_low,
                    kSBumpBlendZoneMm);
        auto insert_above = edge_in;
        insert_above.trans[2] = clear_4.in_reference[2];
        appendPoint(path, "P_INSERT_ABOVE", insert_above,
                    kSBumpBlendZoneMm);
        appendPoint(path, "P_EDGE_IN", edge_in, 0.0);

        path.uses_over_lip_hook = true;
        for (std::size_t axis = 0; axis < 3; ++axis) {
          path.hook_c3_high_m[axis] = c3_high.trans[axis];
          path.hook_c4_high_m[axis] = c4_high.trans[axis];
        }
      } else {
        // A quadratic Bezier in the original insertion vertical plane. The
        // translation control point has the final X/Y, so the path initially
        // moves over the edge in +Y and approaches P_EDGE_IN with a vertical
        // tangent. Its Z is solved so the curve clears c3 by 0.5 mm at p3's XY.
        const double t_contact_3 = 1.0 - std::sqrt(1.0 - s_contact_3);
        const double one_minus_t = 1.0 - t_contact_3;
        const double control_weight =
            2.0 * one_minus_t * t_contact_3;
        const double required_z_3 =
            clear_3.in_reference[2] + kSecondaryClearanceMarginM;
        const double control_z =
            (required_z_3 -
             one_minus_t * one_minus_t * edge_near.trans[2] -
             t_contact_3 * t_contact_3 * edge_in.trans[2]) /
            control_weight;
        if (!std::isfinite(control_z) ||
            control_z <
                std::min(edge_near.trans[2], edge_in.trans[2]) - 0.010 ||
            control_z >
                std::max(edge_near.trans[2], edge_in.trans[2]) + 0.020) {
          throw std::runtime_error(
              "p3/c3 require an unreasonable Y-Z arc control height");
        }

        for (int i = 1; i <= kEdgeArcSamples; ++i) {
          const double t = static_cast<double>(i) / kEdgeArcSamples;
          const double omt = 1.0 - t;
          const double s = 2.0 * t - t * t;
          rokae::CartesianPosition point;
          point.trans[0] = omt * omt * edge_near.trans[0] +
                           2.0 * omt * t * edge_in.trans[0] +
                           t * t * edge_in.trans[0];
          point.trans[1] = omt * omt * edge_near.trans[1] +
                           2.0 * omt * t * edge_in.trans[1] +
                           t * t * edge_in.trans[1];
          point.trans[2] = omt * omt * edge_near.trans[2] +
                           2.0 * omt * t * control_z +
                           t * t * edge_in.trans[2];
          for (std::size_t axis = 0; axis < 3; ++axis) {
            point.rpy[axis] = edge_near.rpy[axis] +
                              s * (edge_in.rpy[axis] - edge_near.rpy[axis]);
          }
          point.elbow = edge_near.elbow +
                        s * (edge_in.elbow - edge_near.elbow);
          point.hasElbow = true;
          const bool last = i == kEdgeArcSamples;
          appendPoint(path, last ? "P_EDGE_IN"
                                 : "ARC_YZ_" + std::to_string(i),
                      point, last ? 0.0 : kSBumpBlendZoneMm);
        }
        path.uses_yz_edge_arc = true;
        path.third_contact_fraction = s_contact_3;
        path.edge_arc_control_z_m = control_z;
        path.edge_arc_height_at_third_m = required_z_3;
      }
    } else {
      for (int i = 1; i <= kSBumpRiseSamples; ++i) {
        const double u = static_cast<double>(i) / kSBumpRiseSamples;
        const double s = s_collision * u;
        const std::string label =
            i == kSBumpRiseSamples ? "P_CLEAR"
                                   : "S_RISE_" + std::to_string(i);
        const double zone_mm = i == kSBumpRiseSamples ? 0.0
                                                      : kSBumpBlendZoneMm;
        append_bump_sample(s, quinticSmoothStep(u), label, zone_mm);
      }
      for (int i = 1; i <= kSBumpFallSamples; ++i) {
        const double u = static_cast<double>(i) / kSBumpFallSamples;
        const double s = s_collision + (1.0 - s_collision) * u;
        const double zone_mm = i == kSBumpFallSamples ? 0.0
                                                      : kSBumpBlendZoneMm;
        const std::string label =
            i == kSBumpFallSamples ? "P_EDGE_IN"
                                   : "S_FALL_" + std::to_string(i);
        append_bump_sample(s, 1.0 - quinticSmoothStep(u), label, zone_mm);
      }
      path.uses_clearance_bump = true;
    }
  } else {
    appendPoint(path, "P_EDGE_IN", edge_in, 0.0);
  }

  const auto press =
      taughtPose(file.points.at("P_PRESS"), &path.points.back().rpy);
  appendPoint(path, "P_PRESS", press, 0.0);
  return path;
}

ControllerPath makeUnmeasuredWidePreviewPath(const TaughtFile &file) {
  ControllerPath path;
  path.is_unmeasured_wide_preview = true;

  const auto safe = taughtPose(file.points.at("P_SAFE"), nullptr);
  appendPoint(path, "P_SAFE", safe, 0.0);

  // Keep the taught angled insertion orientation, but use the user's measured
  // collision-free p6 XYZ as the rear approach point.
  const auto edge_near =
      taughtPose(file.points.at("P_EDGE_NEAR"), &safe.rpy);
  const auto edge_in =
      taughtPose(file.points.at("P_EDGE_IN"), &edge_near.rpy);
  auto press = edge_in;
  for (std::size_t axis = 0; axis < 3; ++axis) {
    press.trans[axis] = kDraftFinalP8MmDeg[axis] * 0.001;
    press.rpy[axis] = unwrapNear(
        kDraftFinalP8MmDeg[3 + axis] * ar_demo::kDegToRad,
        edge_in.rpy[axis]);
  }
  press.elbow = kDraftFinalP8ElbowDeg * ar_demo::kDegToRad;
  press.hasElbow = true;

  auto back_high = edge_in;
  for (std::size_t axis = 0; axis < 3; ++axis) {
    back_high.trans[axis] = kDraftBackP6MmDeg[axis] * 0.001;
    back_high.rpy[axis] = unwrapNear(
        kDraftBackP6MmDeg[3 + axis] * ar_demo::kDegToRad,
        edge_in.rpy[axis]);
  }
  back_high.elbow = kDraftBackP6ElbowDeg * ar_demo::kDegToRad;
  back_high.hasElbow = true;
  // P_SAFE is now the measured rear p6 pose. Do not append p6 again: xCore
  // rejects identical adjacent Cartesian waypoints.

  // This exact-stop waypoint is the requested Z trigger: only after the TCP
  // reaches 0.5 mm above the taught angled insertion Z does forward insertion
  // begin. The full P_EDGE_IN tilt and the retracted +Y are retained.
  auto back_low = back_high;
  back_low.trans[2] = edge_in.trans[2] + kDraftPreInsertLiftM;
  appendPoint(path, "P_BACK_LOW_TILT_DRAFT", back_low, 0.0,
              1.0, 1.0);

  // Move forward and downward together to the exact taught P_EDGE_IN while
  // keeping the angled orientation. This maintains a geometric forward motion
  // throughout the final descent instead of inserting and then dropping
  // vertically. It is position control, not a regulated contact force.
  const auto insert_target = edge_in;
  for (int i = 1; i <= kDraftWideInsertSamples; ++i) {
    const double t =
        static_cast<double>(i) / static_cast<double>(kDraftWideInsertSamples);
    const double s = quinticSmoothStep(t);
    auto point = back_low;
    for (std::size_t axis = 0; axis < 3; ++axis) {
      point.trans[axis] =
          back_low.trans[axis] +
          s * (insert_target.trans[axis] - back_low.trans[axis]);
      point.rpy[axis] =
          back_low.rpy[axis] +
          s * (insert_target.rpy[axis] - back_low.rpy[axis]);
    }
    point.elbow =
        back_low.elbow + s * (insert_target.elbow - back_low.elbow);
    point.hasElbow = true;
    const bool last = i == kDraftWideInsertSamples;
    appendPoint(path,
                last ? "P_EDGE_IN"
                     : "WIDE_INSERT_DOWN_" + std::to_string(i),
                point, last ? 0.0 : kSBumpBlendZoneMm,
                0.8, 0.8);
  }

  // Final rotation/press ends at the user's measured assembled p8 pose.
  appendPoint(path, "P_PRESS_P8", press, 0.0, 0.3, 0.5);
  return path;
}

std::array<double, 6> poseArray(const rokae::CartesianPosition &pose) {
  return {pose.trans[0], pose.trans[1], pose.trans[2],
          pose.rpy[0], pose.rpy[1], pose.rpy[2]};
}

std::array<double, 7> finalP8JointsRad() {
  std::array<double, 7> result{};
  for (std::size_t i = 0; i < result.size(); ++i) {
    result[i] = kDraftFinalP8JointsDeg[i] * ar_demo::kDegToRad;
  }
  return result;
}

ControllerPath makeReverseWidePath(const ControllerPath &forward) {
  if (forward.points.size() < 2 ||
      forward.points.size() != forward.labels.size() ||
      forward.points.size() != forward.zones_mm.size()) {
    throw std::runtime_error("cannot reverse an invalid forward wide path");
  }
  ControllerPath reverse;
  reverse.points.assign(forward.points.rbegin(), forward.points.rend());
  reverse.labels.assign(forward.labels.rbegin(), forward.labels.rend());
  reverse.zones_mm.assign(forward.zones_mm.rbegin(),
                          forward.zones_mm.rend());
  reverse.linear_speeds_mm_s.assign(reverse.points.size(),
                                    kReverseLinearSpeedMmS);
  reverse.rotation_speeds_deg_s.assign(reverse.points.size(),
                                       kReverseRotationSpeedDegS);
  reverse.zones_mm.front() = 0.0;
  reverse.is_unmeasured_wide_preview = true;
  reverse.is_reverse_wide = true;
  return reverse;
}

void printPlan(const ControllerPath &path,
               double linear_speed_mm_s, double rotation_speed_deg_s) {
  std::cout << std::fixed << std::setprecision(3)
            << "Assembly path (active TCP relative to selected workobject):\n";
  double estimated_s = 0.0;
  for (std::size_t i = 0; i < path.points.size(); ++i) {
    const auto pose = poseArray(path.points[i]);
    const double segment_linear_speed =
        path.linear_speeds_mm_s[i] > 0.0
            ? path.linear_speeds_mm_s[i]
            : linear_speed_mm_s;
    const double segment_rotation_speed =
        path.rotation_speeds_deg_s[i] > 0.0
            ? path.rotation_speeds_deg_s[i]
            : rotation_speed_deg_s;
    if (i > 0) {
      const auto prev = poseArray(path.points[i - 1]);
      const double distance_mm = translationDistance(prev, pose) * 1000.0;
      const double angle_deg = rotationDistance(prev, pose) * ar_demo::kRadToDeg;
      const double segment_s =
          std::max(distance_mm / segment_linear_speed,
                   angle_deg / segment_rotation_speed);
      estimated_s += segment_s;
    }
    if (path.labels[i].rfind("P_", 0) == 0) {
      std::cout << "  " << path.labels[i] << " xyz=["
                << pose[0] * 1000.0 << ", " << pose[1] * 1000.0 << ", "
                << pose[2] * 1000.0 << "] mm rpy=["
                << pose[3] * ar_demo::kRadToDeg << ", "
                << pose[4] * ar_demo::kRadToDeg << ", "
                << pose[5] * ar_demo::kRadToDeg << "] deg elbow="
                << path.points[i].elbow * ar_demo::kRadToDeg
                << " deg zone=" << path.zones_mm[i] << " mm";
      if (i > 0 && (path.linear_speeds_mm_s[i] > 0.0 ||
                    path.rotation_speeds_deg_s[i] > 0.0)) {
        std::cout << " arrive_speed=" << segment_linear_speed
                  << " mm/s, " << segment_rotation_speed << " deg/s";
      }
      std::cout << '\n';
    }
  }
  if (path.is_reverse_wide) {
    std::cout
        << "WIDE_REVERSE_PLAN estimated duration >= " << estimated_s
        << " s.\n"
        << "Exact reverse order: measured p8 -> P_EDGE_IN -> rear low "
           "trigger -> P_SAFE/p6.\n"
        << "Reverse arrival speeds are fixed at "
        << kReverseLinearSpeedMmS << " mm/s and "
        << kReverseRotationSpeedDegS << " deg/s.\n"
        << "This is position-controlled extraction, not force-regulated "
           "pulling. Stop immediately if the force rises or the part binds.\n";
  } else if (path.is_unmeasured_wide_preview) {
    std::cout
        << "WIDE_PLAN estimated duration >= " << estimated_s << " s.\n"
        << "Measured rear point p6 xyz=["
        << kDraftBackP6MmDeg[0] << ", "
        << kDraftBackP6MmDeg[1] << ", "
        << kDraftBackP6MmDeg[2] << "] mm.\n"
        << "Forward insertion is triggered after reaching "
        << kDraftPreInsertLiftM * 1000.0
        << " mm above taught P_EDGE_IN Z.\n"
        << "The path moves to p6, descends while tilted, stops at the trigger "
           "height, then moves forward and downward together at constant "
           "tilt to P_EDGE_IN before rotating/pressing to measured p8.\n"
        << "The generated intermediate poses are not measured collision-free. "
           "WIDE_PLAN never moves; WIDE_TEST/WIDE_RUN execute them only "
           "after their explicit arm tokens are entered.\n";
  } else {
    std::cout << "Speed: " << linear_speed_mm_s << " mm/s, rotation "
              << rotation_speed_deg_s << " deg/s; estimated >= "
              << estimated_s << " s.\n";
  }
  if (path.uses_over_lip_hook) {
    std::cout
        << "Over-lip Y-Z hook: P_SAFE is unchanged. The local path stays "
           "above c3 and overshoots the lip to c4 in +Y. It then settles to "
           "the measured c4 height, translates forward in -Y at constant Z "
           "to P_INSERT_ABOVE, descends at the original P_EDGE_IN X/Y, and "
           "only then executes P_PRESS.\n"
        << "  generated c3-high xyz=[" << path.hook_c3_high_m[0] * 1000.0
        << ", " << path.hook_c3_high_m[1] * 1000.0 << ", "
        << path.hook_c3_high_m[2] * 1000.0 << "] mm\n"
        << "  generated c4-behind-lip-high xyz=["
        << path.hook_c4_high_m[0] * 1000.0 << ", "
        << path.hook_c4_high_m[1] * 1000.0 << ", "
        << path.hook_c4_high_m[2] * 1000.0 << "] mm\n"
        << "  one quadratic over-lip arc, " << kHookArcSamples
        << " samples, followed by explicit c4-low, forward-insert and "
           "in-place descent stages; intermediate zone="
        << kSBumpBlendZoneMm << " mm.\n";
  } else if (path.uses_yz_edge_arc) {
    std::cout << "Quadratic Y-Z edge-clearing arc: +Y is the dominant "
                 "insertion direction; X remains on the original top-view "
                 "centreline. p3 is at "
              << path.third_contact_fraction * 100.0
              << "%; curve Z there is "
              << path.edge_arc_height_at_third_m * 1000.0
              << " mm (c3 + " << kSecondaryClearanceMarginM * 1000.0
              << " mm). Bezier control Z="
              << path.edge_arc_control_z_m * 1000.0 << " mm; "
              << kEdgeArcSamples << " controller samples; intermediate zone="
              << kSBumpBlendZoneMm << " mm.\n";
  } else if (path.uses_clearance_bump) {
    const double vertical_clearance_mm =
        path.clearance_offset_m[2] * 1000.0;
    std::cout << "Local quintic vertical-clearance hump: collision at "
              << path.collision_fraction * 100.0
              << "% of P_EDGE_NEAR -> P_EDGE_IN; +reference-Z height "
              << vertical_clearance_mm << " mm; recorded X/Y shift "
              << path.ignored_clearance_lateral_m * 1000.0
              << " mm is deliberately ignored; "
              << kSBumpRiseSamples + kSBumpFallSamples
              << " controller samples; P_CLEAR is exact-stop (zone=0), "
                 "other intermediate zone="
              << kSBumpBlendZoneMm << " mm.\n";
    if (path.uses_secondary_clearance) {
      std::cout << "Secondary contact at "
                << path.secondary_contact_fraction * 100.0
                << "%: P_CLEAR_2 requires "
                << path.secondary_safe_offset_m * 1000.0
                << " mm above the original line; bump factor there is "
                << path.secondary_bump_factor
                << "; peak was automatically expanded with a "
                << kSecondaryClearanceMarginM * 1000.0
                << " mm vertical margin.\n";
    }
  } else if (!path.is_unmeasured_wide_preview) {
    std::cout << "No P_COLLISION_NEAR/P_CLEAR pair found; original straight "
                 "insertion segment is active.\n";
  }
  std::cout << "P_PRE is intentionally ignored.\n";
}

void checkStoredJointMargins(rokae::ArRobot &robot,
                             const TaughtFile &file) {
  std::array<double[2], 7> limits{};
  std::error_code ec;
  const bool enabled = robot.getSoftLimit(limits, ec);
  ar_demo::requireOk(ec, "read joint soft limits");
  if (!enabled) throw std::runtime_error("joint soft limits are disabled");
  std::vector<std::string> names(kRequiredNames.begin(), kRequiredNames.end());
  if (file.points.count("P_COLLISION_NEAR")) {
    names.emplace_back("P_COLLISION_NEAR");
  }
  if (file.points.count("P_CLEAR")) names.emplace_back("P_CLEAR");
  if (file.points.count("P_CONTACT_2")) names.emplace_back("P_CONTACT_2");
  if (file.points.count("P_CLEAR_2")) names.emplace_back("P_CLEAR_2");
  if (file.points.count("p3")) names.emplace_back("p3");
  if (file.points.count("c3")) names.emplace_back("c3");
  if (file.points.count("p4")) names.emplace_back("p4");
  if (file.points.count("c4")) names.emplace_back("c4");
  for (const auto &name : names) {
    const auto &q = file.points.at(name).joints;
    for (std::size_t i = 0; i < q.size(); ++i) {
      if (q[i] - limits[i][0] < kSoftLimitMarginRad ||
          limits[i][1] - q[i] < kSoftLimitMarginRad) {
        throw std::runtime_error(name + " J" +
                                 std::to_string(i + 1) +
                                 " is within 3 deg of a soft limit");
      }
    }
  }
}

void checkControllerPath(rokae::ArRobot &robot,
                         const std::array<double, 7> &start_joints,
                         const std::vector<rokae::CartesianPosition> &points) {
  std::vector<double> start_joint(start_joints.begin(), start_joints.end());
  std::vector<double> target_joint;
  std::error_code ec;
  const int failed_index =
      robot.checkPath(start_joint, points, target_joint, ec);
  if (ec) {
    throw std::runtime_error("controller checkPath failed near point index " +
                             std::to_string(failed_index) + ": " +
                             ec.message());
  }
  if (target_joint.size() < 7) {
    throw std::runtime_error("controller checkPath returned no 7-axis result");
  }
  std::cout << "Controller checkPath: PASS; calculated final joints [";
  for (std::size_t i = 0; i < 7; ++i) {
    if (i) std::cout << ", ";
    std::cout << target_joint[i] * ar_demo::kRadToDeg;
  }
  std::cout << "] deg\n";
}

void requireAtReverseStart(rokae::ArRobot &robot,
                           const ControllerPath &reverse_path) {
  std::error_code ec;
  const auto measured_q = robot.jointPos(ec);
  ar_demo::requireOk(ec, "read current joints");
  const auto measured_pose =
      robot.cartPosture(rokae::CoordinateType::endInRef, ec);
  ar_demo::requireOk(ec, "read current TCP in workobject");
  const auto measured = poseArray(measured_pose);
  const auto expected = poseArray(reverse_path.points.front());
  const auto expected_q = finalP8JointsRad();
  const double trans_error = translationDistance(measured, expected);
  const double rot_error = rotationDistance(measured, expected);
  const double joint_error = maximumJointDistance(measured_q, expected_q);
  std::cout << std::fixed << std::setprecision(3)
            << "Current versus extraction start p8: "
            << trans_error * 1000.0 << " mm / "
            << rot_error * ar_demo::kRadToDeg
            << " deg; maximum joint "
            << joint_error * ar_demo::kRadToDeg << " deg\n";
  if (trans_error > kStartTranslationToleranceM ||
      rot_error > kStartRotationToleranceRad ||
      joint_error > kStartJointToleranceRad) {
    throw std::runtime_error(
        "reverse run refused: robot is not at the measured assembled p8");
  }
}

void requireAtTaughtPointStart(rokae::ArRobot &robot,
                               const TaughtPoint &expected_point,
                               const std::string &label) {
  std::error_code ec;
  const auto measured_q = robot.jointPos(ec);
  ar_demo::requireOk(ec, "read current joints");
  const auto measured_pose =
      robot.cartPosture(rokae::CoordinateType::endInRef, ec);
  ar_demo::requireOk(ec, "read current TCP in workobject");
  const auto measured = poseArray(measured_pose);
  const double trans_error =
      translationDistance(measured, expected_point.in_reference);
  const double rot_error =
      rotationDistance(measured, expected_point.in_reference);
  const double joint_error =
      maximumJointDistance(measured_q, expected_point.joints);
  std::cout << std::fixed << std::setprecision(3)
            << "Current versus " << label << ": "
            << trans_error * 1000.0 << " mm / "
            << rot_error * ar_demo::kRadToDeg
            << " deg; maximum joint "
            << joint_error * ar_demo::kRadToDeg << " deg\n";
  if (trans_error > kStartTranslationToleranceM ||
      rot_error > kStartRotationToleranceRad ||
      joint_error > kStartJointToleranceRad) {
    throw std::runtime_error("run refused: robot is not at " + label);
  }
}

void requireAtSafeStart(rokae::ArRobot &robot, const TaughtFile &file) {
  std::error_code ec;
  const auto measured_q = robot.jointPos(ec);
  ar_demo::requireOk(ec, "read current joints");
  const auto measured_pose =
      robot.cartPosture(rokae::CoordinateType::endInRef, ec);
  ar_demo::requireOk(ec, "read current TCP in workobject");
  const auto measured = poseArray(measured_pose);
  const auto &safe = file.points.at("P_SAFE");
  const double trans_error = translationDistance(measured, safe.in_reference);
  const double rot_error = rotationDistance(measured, safe.in_reference);
  const double joint_error = maximumJointDistance(measured_q, safe.joints);
  std::cout << std::fixed << std::setprecision(3)
            << "Current versus P_SAFE: " << trans_error * 1000.0
            << " mm / " << rot_error * ar_demo::kRadToDeg
            << " deg; maximum joint "
            << joint_error * ar_demo::kRadToDeg << " deg\n";
  if (trans_error > kStartTranslationToleranceM ||
      rot_error > kStartRotationToleranceRad ||
      joint_error > kStartJointToleranceRad) {
    throw std::runtime_error(
        "RUN refused: manually return to recorded P_SAFE first");
  }
}

std::array<double, 7> inspectGoSafe(rokae::ArRobot &robot,
                                    const TaughtFile &file) {
  std::error_code ec;
  const auto current = robot.jointPos(ec);
  ar_demo::requireOk(ec, "read current joints for GO_SAFE");
  const auto &target = file.points.at("P_SAFE").joints;

  std::cout << std::fixed << std::setprecision(3)
            << "GO_SAFE uses controller MoveAbsJ from the current joint pose.\n"
            << "Current joints [";
  for (std::size_t i = 0; i < current.size(); ++i) {
    if (i) std::cout << ", ";
    std::cout << current[i] * ar_demo::kRadToDeg;
  }
  std::cout << "] deg\nP_SAFE joints [";
  for (std::size_t i = 0; i < target.size(); ++i) {
    if (i) std::cout << ", ";
    std::cout << target[i] * ar_demo::kRadToDeg;
  }
  std::cout << "] deg\nMaximum joint change: "
            << maximumJointDistance(current, target) * ar_demo::kRadToDeg
            << " deg; joint speed: " << kGoSafeJointSpeedRatio * 100.0
            << "%\n";
  return current;
}

void ensureMotorPowerOn(rokae::ArRobot &robot,
                        std::chrono::seconds timeout) {
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  bool requested_power_on = false;
  int consecutive_on_samples = 0;
  while (std::chrono::steady_clock::now() < deadline) {
    std::error_code ec;
    const auto power = robot.powerState(ec);
    ar_demo::requireOk(ec, "read motor power state");
    if (power == rokae::PowerState::estop) {
      throw std::runtime_error(
          "motor power is blocked because the emergency stop is active");
    }
    if (power == rokae::PowerState::gstop) {
      throw std::runtime_error(
          "motor power is blocked because the safety gate/stop is active");
    }
    if (power == rokae::PowerState::on) {
      ++consecutive_on_samples;
      if (consecutive_on_samples >= 3) {
        const auto state = robot.operationState(ec);
        ar_demo::requireOk(ec, "read operation state after power on");
        if (state != rokae::OperationState::idle) {
          throw std::runtime_error(
              "motor is on but robot operation state is not idle before "
              "motion start");
        }
        std::cout << "Motor power verified ON and controller idle.\n";
        return;
      }
    } else {
      consecutive_on_samples = 0;
      if (power == rokae::PowerState::off && !requested_power_on) {
        robot.setPowerState(true, ec);
        ar_demo::requireOk(ec, "request motor power on");
        requested_power_on = true;
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  throw std::runtime_error(
      "motor did not reach a stable ON state within the power-on timeout");
}

void waitForCommand(rokae::ArRobot &robot, const std::string &command_id,
                    int final_waypoint, std::chrono::seconds timeout) {
  using namespace rokae::EventInfoKey::MoveExecution;
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  auto next_event_query = std::chrono::steady_clock::now();
  while (!ar_demo::stop_requested.load() &&
         std::chrono::steady_clock::now() < deadline) {
    if (ar_assembly_guard::active_hook) {
      std::string guard_reason;
      const auto decision =
          ar_assembly_guard::active_hook->poll(guard_reason);
      if (decision != ar_assembly_guard::Decision::none) {
        std::error_code stop_ec;
        robot.stop(stop_ec);
        // Stage 2 never auto-resumes after a force event. Clear the queued
        // remainder for soft, hard and stale-data stops alike.
        std::error_code reset_ec;
        robot.moveReset(reset_ec);
        ar_assembly_guard::active_hook->publishState(
            decision == ar_assembly_guard::Decision::soft_pause
                ? "SOFT_PAUSE"
                : decision == ar_assembly_guard::Decision::sensor_timeout
                      ? "SENSOR_TIMEOUT"
                      : "HARD_STOP",
            guard_reason);
        throw std::runtime_error("force guard: " + guard_reason);
      }
    }
    const auto now = std::chrono::steady_clock::now();
    if (now < next_event_query) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      continue;
    }
    next_event_query = now + std::chrono::milliseconds(100);
    std::error_code ec;
    const auto info = robot.queryEventInfo(rokae::Event::moveExecution, ec);
    ar_demo::requireOk(ec, "query NRT motion execution event");
    if (info.count(ID) && info.count(WaypointIndex) &&
        info.count(ReachTarget) && info.count(Error)) {
      const auto id = std::any_cast<std::string>(info.at(ID));
      const int index = std::any_cast<int>(info.at(WaypointIndex));
      if (id == command_id) {
        const auto motion_error =
            std::any_cast<std::error_code>(info.at(Error));
        std::string remark;
        if (info.count(Remark)) {
          remark = std::any_cast<std::string>(info.at(Remark));
        }
        if (motion_error) {
          throw std::runtime_error(
              "controller rejected/aborted command at waypoint " +
              std::to_string(index) + ": " + motion_error.message() +
              (remark.empty() ? "" : " (" + remark + ")"));
        }
        if (index == final_waypoint &&
            std::any_cast<bool>(info.at(ReachTarget))) {
          std::cout << "Controller reports command " << command_id
                    << " waypoint " << index << " reached.\n";
          return;
        }
      }
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  std::error_code ignored;
  robot.stop(ignored);
  if (ar_demo::stop_requested.load()) {
    throw std::runtime_error("stopped by Ctrl+C");
  }
  throw std::runtime_error("motion command did not finish before timeout");
}

}  // namespace

int arFourPointSmoothTrajectoryMain(int argc, char **argv) {
  using namespace rokae;
  if (argc < 7 || argc > 9) {
    std::cerr
        << "Usage: " << argv[0]
        << " ROBOT_IP LOCAL_IP TOOL WOBJ POINTS.csv"
           " PLAN|WIDE_PLAN|WIDE_TEST|WIDE_RUN|WIDE_AUTO|WIDE_REVERSE_PLAN|"
           "WIDE_REVERSE_TEST|WIDE_REVERSE_EXTRACT|WIDE_REVERSE_RUN|"
           "ARC_TEST|RUN|GO_SAFE|AUTO"
           " [LINEAR_MM_S] [ROTATION_DEG_S]\n"
        << "Example PLAN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv PLAN\n"
        << "Example WIDE_PLAN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv WIDE_PLAN\n"
        << "Example WIDE_TEST: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv WIDE_TEST\n"
        << "Example WIDE_RUN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv WIDE_RUN\n"
        << "Example WIDE_REVERSE_PLAN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv WIDE_REVERSE_PLAN\n"
        << "Example WIDE_REVERSE_RUN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv WIDE_REVERSE_RUN\n"
        << "Example RUN: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv RUN 0.5 0.5\n"
        << "Example GO_SAFE: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv GO_SAFE 0.5 0.5\n"
        << "Example AUTO: " << argv[0]
        << " 192.168.2.160 192.168.2.100 g_tool_1 g_wobj_0"
           " points.csv AUTO 0.5 0.5\n";
    return 2;
  }

  const std::string robot_ip = argv[1];
  const std::string local_ip = argv[2];
  const std::string tool_name = argv[3];
  const std::string wobj_name = argv[4];
  const std::string csv_path = argv[5];
  const std::string mode = argv[6];
  const bool forward_wide_mode =
      mode == "WIDE_PLAN" || mode == "WIDE_TEST" || mode == "WIDE_RUN" ||
      mode == "WIDE_AUTO";
  const bool reverse_wide_mode =
      mode == "WIDE_REVERSE_PLAN" || mode == "WIDE_REVERSE_TEST" ||
      mode == "WIDE_REVERSE_EXTRACT" || mode == "WIDE_REVERSE_RUN";
  const bool reverse_extract_mode = mode == "WIDE_REVERSE_EXTRACT";
  const bool wide_mode = forward_wide_mode || reverse_wide_mode;
  const bool go_safe_mode =
      mode == "GO_SAFE" || mode == "AUTO" || mode == "WIDE_AUTO";
  if (mode != "PLAN" && !wide_mode &&
      mode != "ARC_TEST" && mode != "RUN" && !go_safe_mode) {
    std::cerr << "Unsupported mode.\n";
    return 2;
  }
  double linear_speed_mm_s = 0.5;
  double rotation_speed_deg_s = 0.5;
  try {
    if (argc >= 8) {
      linear_speed_mm_s =
          ar_demo::parseNumber(argv[7], 0.1, 2.0, "LINEAR_MM_S");
    }
    if (argc >= 9) {
      rotation_speed_deg_s =
          ar_demo::parseNumber(argv[8], 0.1, 2.0, "ROTATION_DEG_S");
    }
  } catch (const std::exception &e) {
    std::cerr << "Invalid argument: " << e.what() << '\n';
    return 2;
  }

  ar_demo::installSignalHandlers();
  ArRobot robot;
  bool powered = false;
  try {
    const auto taught = loadTaughtFile(csv_path);
    if (!taught.tool.empty() && taught.tool != tool_name) {
      throw std::runtime_error("CSV tool is " + taught.tool +
                               ", but command selected " + tool_name);
    }
    if (!taught.workobject.empty() && taught.workobject != wobj_name) {
      throw std::runtime_error("CSV workobject is " + taught.workobject +
                               ", but command selected " + wobj_name);
    }

    std::cout << "Connecting to " << robot_ip << " from " << local_ip
              << "...\n";
    robot.connectToRobot(robot_ip, local_ip);
    ar_demo::verifyRobot(robot);
    std::error_code ec;
    robot.setToolset(tool_name, wobj_name, ec);
    ar_demo::requireOk(ec, "select recorded tool/workobject");

    checkStoredJointMargins(robot, taught);
    auto controller_path =
        wide_mode ? makeUnmeasuredWidePreviewPath(taught)
                  : makeControllerPath(taught);
    if (reverse_wide_mode) {
      controller_path = makeReverseWidePath(controller_path);
      if (reverse_extract_mode) {
        const auto edge_it =
            std::find(controller_path.labels.begin(),
                      controller_path.labels.end(), "P_EDGE_IN");
        if (edge_it == controller_path.labels.end()) {
          throw std::runtime_error(
              "internal error: P_EDGE_IN missing from reverse path");
        }
        const auto erase_count =
            static_cast<std::size_t>(edge_it - controller_path.labels.begin());
        controller_path.points.erase(
            controller_path.points.begin(),
            controller_path.points.begin() + erase_count);
        controller_path.labels.erase(
            controller_path.labels.begin(),
            controller_path.labels.begin() + erase_count);
        controller_path.zones_mm.erase(
            controller_path.zones_mm.begin(),
            controller_path.zones_mm.begin() + erase_count);
        controller_path.linear_speeds_mm_s.erase(
            controller_path.linear_speeds_mm_s.begin(),
            controller_path.linear_speeds_mm_s.begin() + erase_count);
        controller_path.rotation_speeds_deg_s.erase(
            controller_path.rotation_speeds_deg_s.begin(),
            controller_path.rotation_speeds_deg_s.begin() + erase_count);
        controller_path.zones_mm.front() = 0.0;
      }
    }
    printPlan(controller_path, linear_speed_mm_s, rotation_speed_deg_s);
    const auto path_start_joints =
        reverse_extract_mode ? taught.points.at("P_EDGE_IN").joints
        : reverse_wide_mode ? finalP8JointsRad()
                          : taught.points.at("P_SAFE").joints;
    checkControllerPath(robot, path_start_joints, controller_path.points);

    if (mode == "PLAN" || mode == "WIDE_PLAN" ||
        mode == "WIDE_REVERSE_PLAN") {
      std::cout
          << (mode == "WIDE_REVERSE_PLAN"
                  ? "WIDE_REVERSE_PLAN ONLY: reverse reachability passed. No "
                    "power or motion command was sent.\n"
                  : mode == "WIDE_PLAN"
                  ? "WIDE_PLAN ONLY: generated reachability passed. No power "
                    "or motion command was sent.\n"
                  : "PLAN ONLY: reachability passed. No power or motion "
                    "command was sent.\n")
          << "This does not check the real phone/board geometry.\n";
      return 0;
    }

    if (go_safe_mode) {
      inspectGoSafe(robot, taught);
      std::cout
          << "The current-to-P_SAFE path is a controller-generated joint "
             "trajectory.\n"
          << "It is smooth but has NO external-obstacle model; the TCP path "
             "is not a straight line. Clear the entire swept workspace and "
             "hold the E-stop.\n";
    } else if (reverse_extract_mode) {
      requireAtTaughtPointStart(robot, taught.points.at("P_EDGE_IN"),
                                "P_EDGE_IN extraction start");
    } else if (reverse_wide_mode) {
      requireAtReverseStart(robot, controller_path);
    } else {
      requireAtSafeStart(robot, taught);
    }

    if (mode == "WIDE_AUTO") {
      std::cout
          << "WIDE_AUTO will first MoveAbsJ to P_SAFE, verify it, pause for "
             "2 s, then execute the generated wide assembly path to p8.\n";
    } else if (mode == "AUTO") {
      std::cout
          << "AUTO will first MoveAbsJ to P_SAFE, verify it, pause for 2 s, "
             "then execute P_EDGE_NEAR, P_EDGE_IN and P_PRESS.\n";
    } else if (mode == "GO_SAFE") {
      std::cout << "GO_SAFE will stop and power off after reaching P_SAFE.\n";
    } else if (mode == "WIDE_TEST") {
      std::cout << "WIDE_TEST stops at the taught tilted P_EDGE_IN without "
                   "executing P_PRESS.\n";
    } else if (mode == "WIDE_RUN") {
      std::cout << "WIDE_RUN executes the generated wide path and ends at "
                   "the measured assembled p8 pose.\n";
    } else if (mode == "WIDE_REVERSE_TEST") {
      std::cout << "WIDE_REVERSE_TEST slowly releases the final press and "
                   "stops at P_EDGE_IN. Continue with "
                   "WIDE_REVERSE_EXTRACT.\n";
    } else if (mode == "WIDE_REVERSE_EXTRACT") {
      std::cout << "WIDE_REVERSE_EXTRACT continues slowly from P_EDGE_IN "
                   "back to P_SAFE/p6.\n";
    } else if (mode == "WIDE_REVERSE_RUN") {
      std::cout << "WIDE_REVERSE_RUN slowly follows the verified assembly "
                   "path backward from p8 to P_SAFE/p6.\n";
    } else if (mode == "ARC_TEST") {
      std::cout
          << "ARC_TEST will execute the Cartesian path only through "
             "P_EDGE_IN, then stop and power off without P_PRESS.\n";
    } else {
      std::cout
          << "RUN will execute controller-native MoveL segments with exact"
             " stops at P_EDGE_NEAR, P_EDGE_IN and P_PRESS.\n";
    }
    std::cout
        << "Real-object collision is NOT guaranteed absent. Use a dummy part,"
           " clear workspace and hold the E-stop.\n";

    const char *arm_token = "ARM_FOUR_POINT_RUN";
    if (mode == "WIDE_TEST") arm_token = "ARM_WIDE_DRAFT_TEST";
    if (mode == "WIDE_RUN") arm_token = "ARM_WIDE_DRAFT_RUN";
    if (mode == "WIDE_AUTO") arm_token = "ARM_GO_SAFE_AND_WIDE_RUN";
    if (mode == "WIDE_REVERSE_TEST") {
      arm_token = "ARM_WIDE_REVERSE_TEST";
    }
    if (mode == "WIDE_REVERSE_RUN") {
      arm_token = "ARM_WIDE_REVERSE_RUN";
    }
    if (mode == "WIDE_REVERSE_EXTRACT") {
      arm_token = "ARM_WIDE_REVERSE_EXTRACT";
    }
    if (mode == "AUTO") arm_token = "ARM_GO_SAFE_AND_RUN";
    if (mode == "GO_SAFE") arm_token = "ARM_GO_SAFE";
    if (mode == "ARC_TEST") arm_token = "ARM_ARC_TEST";
    if (!ar_demo::confirm(arm_token)) {
      std::cout << "Cancelled; robot was not powered on.\n";
      return 0;
    }

    if (ar_assembly_guard::active_hook) {
      ar_assembly_guard::active_hook->prepareForMotion();
      ar_assembly_guard::active_hook->publishState(
          "READY", "fresh and quiet wrench data verified");
    }

    ar_demo::enterNrtAutomatic(robot);
    powered = true;
    robot.adjustAcceleration(0.2, 0.1, ec);
    ar_demo::requireOk(ec, "set minimum acceleration/jerk percentages");
    robot.adjustSpeedOnline(1.0, ec);
    ar_demo::requireOk(ec, "set NRT online speed scale to 100 percent");
    std::cout << "NRT online speed scale: 100%; command-specific speed limits "
                 "remain active.\n";
    robot.moveReset(ec);
    ar_demo::requireOk(ec, "reset NRT motion queue");
    if (controller_path.uses_clearance_bump ||
        controller_path.uses_yz_edge_arc ||
        controller_path.uses_over_lip_hook ||
        controller_path.is_unmeasured_wide_preview) {
      robot.setAutoIgnoreZone(false, ec);
      ar_demo::requireOk(ec, "preserve clearance-path blending zones");
    }
    ensureMotorPowerOn(robot, std::chrono::seconds(10));
    if (ar_assembly_guard::active_hook) {
      ar_assembly_guard::active_hook->arm();
      ar_assembly_guard::active_hook->publishState(
          "ARMED", "force guard is monitoring all commanded motion");
    }

    if (go_safe_mode) {
      const auto &safe_joints = taught.points.at("P_SAFE").joints;
      MoveAbsJCommand go_safe(
          JointPosition(std::vector<double>(safe_joints.begin(),
                                            safe_joints.end())),
          50.0, 0.0);
      go_safe.jointSpeed = kGoSafeJointSpeedRatio;
      std::string go_safe_id;
      robot.moveAppend(go_safe, go_safe_id, ec);
      ar_demo::requireOk(ec, "append smooth MoveAbsJ to P_SAFE");
      std::cout << "GO_SAFE command queued as " << go_safe_id
                << "; starting now.\n";
      robot.moveStart(ec);
      ar_demo::requireOk(ec, "start smooth MoveAbsJ to P_SAFE");
      waitForCommand(robot, go_safe_id, 0, std::chrono::seconds(600));
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
      requireAtSafeStart(robot, taught);
      std::cout << "P_SAFE reached and verified.\n";

      if (mode == "GO_SAFE") {
        if (ar_assembly_guard::active_hook) {
          ar_assembly_guard::active_hook->publishState(
              "COMPLETE", "P_SAFE reached");
        }
        ar_demo::safeShutdown(robot);
        powered = false;
        return 0;
      }
      std::cout << "Holding P_SAFE for 2 seconds before assembly path.\n";
      std::this_thread::sleep_for(std::chrono::seconds(2));
      ensureMotorPowerOn(robot, std::chrono::seconds(5));
    }

    std::size_t execution_point_count = controller_path.points.size();
    if (mode == "ARC_TEST" || mode == "WIDE_TEST" ||
        mode == "WIDE_REVERSE_TEST") {
      const std::string arc_test_target =
          "P_EDGE_IN";
      const auto edge_it =
          std::find(controller_path.labels.begin(),
                    controller_path.labels.end(), arc_test_target);
      if (edge_it == controller_path.labels.end()) {
        throw std::runtime_error("internal error: ARC_TEST target not in path");
      }
      execution_point_count =
          static_cast<std::size_t>(edge_it - controller_path.labels.begin()) +
          1;
    }

    std::vector<MoveLCommand> commands;
    for (std::size_t i = 1; i < execution_point_count; ++i) {
      const double segment_linear_speed =
          controller_path.linear_speeds_mm_s[i] > 0.0
              ? controller_path.linear_speeds_mm_s[i]
              : linear_speed_mm_s;
      const double segment_rotation_speed =
          controller_path.rotation_speeds_deg_s[i] > 0.0
              ? controller_path.rotation_speeds_deg_s[i]
              : rotation_speed_deg_s;
      MoveLCommand command(controller_path.points[i], segment_linear_speed,
                           controller_path.zones_mm[i]);
      command.rotSpeed = segment_rotation_speed * ar_demo::kDegToRad;
      commands.push_back(command);
    }
    std::string assembly_id;
    robot.moveAppend(commands, assembly_id, ec);
    ar_demo::requireOk(ec, "append assembly MoveL sequence");
    std::cout << "Assembly command queued as " << assembly_id
              << "; starting now.\n";
    robot.moveStart(ec);
    ar_demo::requireOk(ec, "start assembly MoveL sequence");

    double estimated_s = 0.0;
    for (std::size_t i = 1; i < execution_point_count; ++i) {
      const auto a = poseArray(controller_path.points[i - 1]);
      const auto b = poseArray(controller_path.points[i]);
      const double segment_linear_speed =
          controller_path.linear_speeds_mm_s[i] > 0.0
              ? controller_path.linear_speeds_mm_s[i]
              : linear_speed_mm_s;
      const double segment_rotation_speed =
          controller_path.rotation_speeds_deg_s[i] > 0.0
              ? controller_path.rotation_speeds_deg_s[i]
              : rotation_speed_deg_s;
      estimated_s += std::max(
          translationDistance(a, b) * 1000.0 / segment_linear_speed,
          rotationDistance(a, b) * ar_demo::kRadToDeg /
              segment_rotation_speed);
    }
    const auto timeout = std::chrono::seconds(
        static_cast<long long>(std::ceil(estimated_s * 5.0 + 60.0)));
    waitForCommand(robot, assembly_id,
                   static_cast<int>(commands.size() - 1), timeout);
    std::cout << (mode == "WIDE_REVERSE_TEST"
                      ? "WIDE_REVERSE_TEST finished at P_EDGE_IN; the part "
                        "was not fully extracted.\n"
                      : mode == "WIDE_TEST"
                      ? "WIDE_TEST finished at tilted P_EDGE_IN; P_PRESS was not "
                        "commanded.\n"
                      : mode == "ARC_TEST"
                      ? "ARC_TEST finished at P_EDGE_IN; P_PRESS was not "
                        "commanded.\n"
                      : mode == "WIDE_RUN"
                      ? "WIDE_RUN finished at measured P_PRESS_P8.\n"
                      : mode == "WIDE_REVERSE_RUN"
                      ? "WIDE_REVERSE_RUN finished at P_SAFE/p6.\n"
                      : mode == "WIDE_REVERSE_EXTRACT"
                      ? "WIDE_REVERSE_EXTRACT finished at P_SAFE/p6.\n"
                      : "Assembly trajectory finished at P_PRESS.\n");
    if (ar_assembly_guard::active_hook) {
      ar_assembly_guard::active_hook->publishState(
          "COMPLETE", "commanded trajectory reached its final waypoint");
    }
    ar_demo::safeShutdown(robot);
    powered = false;
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "ERROR: " << e.what() << "\nStopping and powering off.\n";
    if (powered) ar_demo::safeShutdown(robot);
    else robot.stopReceiveRobotState();
    return 1;
  }
}

#ifndef AR_FORCE_GUARD_ROS2
int main(int argc, char **argv) {
  return arFourPointSmoothTrajectoryMain(argc, argv);
}
#endif
