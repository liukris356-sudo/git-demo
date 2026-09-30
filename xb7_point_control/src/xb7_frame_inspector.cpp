#include <array>
#include <iomanip>
#include <iostream>
#include <string>
#include <system_error>

#include "rokae/robot.h"

namespace {

void requireOk(const std::error_code &ec, const std::string &action) {
  if (ec) throw std::runtime_error(action + ": " + ec.message());
}

void printFrame(const char *label, const rokae::Frame &frame) {
  std::cout << std::fixed << std::setprecision(6) << label
            << " xyz[m]=[" << frame.trans[0] << ", " << frame.trans[1]
            << ", " << frame.trans[2] << "] rpy[rad]=[" << frame.rpy[0]
            << ", " << frame.rpy[1] << ", " << frame.rpy[2] << "]\n";
}

void printArray(const char *label, const std::array<double, 6> &frame) {
  std::cout << std::fixed << std::setprecision(6) << label
            << " xyz[m]=[" << frame[0] << ", " << frame[1] << ", "
            << frame[2] << "] rpy[rad]=[" << frame[3] << ", " << frame[4]
            << ", " << frame[5] << "]\n";
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 5) {
    std::cerr << "Usage: " << argv[0]
              << " ROBOT_IP LOCAL_IP TOOL WOBJ\n";
    return 2;
  }

  rokae::StandardRobot robot;
  bool connected = false;
  try {
    robot.connectToRobot(argv[1], argv[2]);
    connected = true;
    std::error_code ec;
    const auto info = robot.robotInfo(ec);
    requireOk(ec, "read robot info");
    robot.setToolset(argv[3], argv[4], ec);
    requireOk(ec, "select tool/workobject");
    const auto base = robot.baseFrame(ec);
    requireOk(ec, "read base frame");
    const auto toolset = robot.toolset(ec);
    requireOk(ec, "read selected toolset");

    std::cout << "Robot: " << info.type << "\nSelected: " << argv[3]
              << " / " << argv[4] << '\n';
    printArray("Base relative to World", base);
    printFrame("Selected reference relative to World", toolset.ref);
    printFrame("Selected TCP relative to Flange", toolset.end);
    std::cout << "Load mass[kg]=" << toolset.load.mass
              << " cog[m]=[" << toolset.load.cog[0] << ", "
              << toolset.load.cog[1] << ", " << toolset.load.cog[2]
              << "]\n";

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
