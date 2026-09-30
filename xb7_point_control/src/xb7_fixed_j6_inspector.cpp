#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <string>
#include <system_error>

#include <Eigen/Dense>

#include "rokae/utility.h"
#include "xb7_point_common.hpp"

namespace {

double wrap(double value) {
  return std::remainder(value, 2.0 * xb7_points::kPi);
}

std::array<double, 5> poseError(const std::array<double, 6> &target,
                                const std::array<double, 6> &actual) {
  return {target[0] - actual[0], target[1] - actual[1],
          target[2] - actual[2], wrap(target[3] - actual[3]),
          wrap(target[4] - actual[4])};
}

std::array<double, 6> solveFixedJ6(
    rokae::Model_T<6> &model, const rokae::Toolset &toolset,
    std::array<double, 6> joints, const std::array<double, 6> &target,
    double fixed_j6) {
  joints[5] = fixed_j6;
  constexpr double h = 1e-6;
  constexpr double damping = 1e-8;
  for (int iter = 0; iter < 80; ++iter) {
    std::error_code ec;
    const auto pose = xb7_points::poseArray(model.calcFk(joints, toolset, ec));
    xb7_points::requireOk(ec, "fixed-J6 FK");
    const auto error = poseError(target, pose);
    Eigen::Matrix<double, 5, 1> e;
    for (int i = 0; i < 5; ++i) e(i) = error[i];
    if (e.head<3>().norm() < 1e-9 && e.tail<2>().norm() < 1e-8) {
      return joints;
    }

    Eigen::Matrix<double, 5, 5> jacobian;
    for (int column = 0; column < 5; ++column) {
      auto perturbed = joints;
      perturbed[column] += h;
      const auto shifted = xb7_points::poseArray(
          model.calcFk(perturbed, toolset, ec));
      xb7_points::requireOk(ec, "fixed-J6 finite-difference FK");
      for (int row = 0; row < 3; ++row) {
        jacobian(row, column) = (shifted[row] - pose[row]) / h;
      }
      jacobian(3, column) = wrap(shifted[3] - pose[3]) / h;
      jacobian(4, column) = wrap(shifted[4] - pose[4]) / h;
    }
    const auto normal = jacobian.transpose() * jacobian +
                        damping * Eigen::Matrix<double, 5, 5>::Identity();
    Eigen::Matrix<double, 5, 1> step =
        normal.ldlt().solve(jacobian.transpose() * e);
    const double largest = step.cwiseAbs().maxCoeff();
    if (largest > 0.1) step *= 0.1 / largest;
    for (int i = 0; i < 5; ++i) joints[i] += step(i);
    joints[5] = fixed_j6;
  }
  throw std::runtime_error("fixed-J6 solver did not converge");
}

void printDerived(const std::string &name, const std::array<double, 6> &joints,
                  rokae::Model_T<6> &model, const rokae::Toolset &toolset,
                  const std::array<double, 6> &base_in_world) {
  std::error_code ec;
  const auto pose = model.calcFk(joints, toolset, ec);
  xb7_points::requireOk(ec, "calculate FK for " + name);
  const auto p = xb7_points::poseArray(pose);
  const auto flange =
      rokae::Utils::EndInRefToFlanInBase(base_in_world, toolset, p);
  std::cout << std::setprecision(17) << name;
  for (double v : p) std::cout << ',' << v;
  for (double v : flange) std::cout << ',' << v;
  for (double v : joints) std::cout << ',' << v;
  std::cout << '\n';
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 7) {
    std::cerr << "Usage: " << argv[0]
              << " ROBOT_IP LOCAL_IP TOOL WOBJ BASE.csv P3.csv\n";
    return 2;
  }
  rokae::StandardRobot robot;
  bool connected = false;
  try {
    const auto base = xb7_points::loadPointFile(argv[5]);
    const auto p3_file = xb7_points::loadPointFile(argv[6]);
    const auto &p3 = p3_file.points.at(p3_file.by_name.at("p3"));
    const auto &p5 = p3_file.points.at(p3_file.by_name.at("p5"));
    const auto &p6 = p3_file.points.at(p3_file.by_name.at("p6"));
    const double fixed_j6 = p3.joints[5];

    robot.connectToRobot(argv[1], argv[2]);
    connected = true;
    std::error_code ec;
    robot.setToolset(argv[3], argv[4], ec);
    xb7_points::requireOk(ec, "select tool/workobject");
    const auto toolset = robot.toolset(ec);
    xb7_points::requireOk(ec, "read toolset");
    const auto base_in_world = robot.baseFrame(ec);
    xb7_points::requireOk(ec, "read base frame");
    auto model = robot.model();

    const auto &edge_record = base.points.at(base.by_name.at("P_EDGE_IN"));
    auto edge_target = edge_record.tcp_in_reference;
    edge_target[0] = p3.tcp_in_reference[0];
    auto edge_joints = solveFixedJ6(
        model, toolset, edge_record.joints, edge_target, fixed_j6);

    const auto &press_record = base.points.at(base.by_name.at("P_PRESS"));
    auto press_target = press_record.tcp_in_reference;
    press_target[0] = p3.tcp_in_reference[0];
    press_target[1] = p3.tcp_in_reference[1];
    auto press_joints = solveFixedJ6(
        model, toolset, press_record.joints, press_target, fixed_j6);

    auto p5_message_target = p5.tcp_in_reference;
    p5_message_target[0] = 0.491648;
    auto p5_message_joints = solveFixedJ6(
        model, toolset, p5.joints, p5_message_target, p5.joints[5]);

    auto edge_y_target = edge_target;
    edge_y_target[1] = p6.tcp_in_reference[1];
    auto edge_y_joints = solveFixedJ6(
        model, toolset, edge_joints, edge_y_target, fixed_j6);

    auto p3_y_target = p3.tcp_in_reference;
    p3_y_target[1] = p6.tcp_in_reference[1];
    auto p3_y_joints = solveFixedJ6(
        model, toolset, p3.joints, p3_y_target, fixed_j6);

    auto final_y_target = p5.tcp_in_reference;
    final_y_target[0] = 0.491648;
    final_y_target[1] = p6.tcp_in_reference[1];
    auto final_y_joints = solveFixedJ6(
        model, toolset, p5_message_joints, final_y_target, p5.joints[5]);

    std::cout << "fixed_j6_rad," << std::setprecision(17) << fixed_j6 << '\n';
    printDerived("P_EDGE_IN_FIXED_J6", edge_joints, model, toolset,
                 base_in_world);
    printDerived("P3", p3.joints, model, toolset, base_in_world);
    printDerived("P_PRESS_FIXED_J6", press_joints, model, toolset,
                 base_in_world);
    printDerived("P5_MESSAGE_X491648", p5_message_joints, model, toolset,
                 base_in_world);
    printDerived("P_EDGE_IN_Y_P6", edge_y_joints, model, toolset,
                 base_in_world);
    printDerived("P3_Y_P6", p3_y_joints, model, toolset, base_in_world);
    printDerived("P_FINAL_X491648_Y_P6", final_y_joints, model, toolset,
                 base_in_world);

    robot.disconnectFromRobot(ec);
    return 0;
  } catch (const std::exception &error) {
    if (connected) {
      std::error_code ignored;
      robot.disconnectFromRobot(ignored);
    }
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
