#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <geometry_msgs/msg/wrench_stamped.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

#include "assembly_force_guard_hook.hpp"

int arFourPointSmoothTrajectoryMain(int argc, char **argv);

namespace {

using Clock = std::chrono::steady_clock;

double norm3(double a, double b, double c) {
  return std::sqrt(a * a + b * b + c * c);
}

class ForceGuardNode final : public rclcpp::Node,
                             public ar_assembly_guard::Hook {
 public:
  ForceGuardNode() : Node("ar_assembly_force_guard_node") {
    wrench_topic_ = declare_parameter<std::string>(
        "wrench_topic", "/m3815/wrench_raw");
    status_topic_ = declare_parameter<std::string>(
        "status_topic", "/assembly/force_guard/status");
    soft_force_n_ = declare_parameter<double>("soft_force_n", 27.0);
    hard_force_n_ = declare_parameter<double>("hard_force_n", 30.0);
    hard_torque_nm_ =
        declare_parameter<double>("hard_torque_nm", 1.25);
    soft_hold_s_ = declare_parameter<double>("soft_hold_s", 0.030);
    timeout_s_ = declare_parameter<double>("wrench_timeout_s", 0.050);
    quiet_check_s_ = declare_parameter<double>("quiet_check_s", 2.0);
    quiet_force_range_n_ =
        declare_parameter<double>("quiet_force_range_n", 3.0);
    quiet_torque_range_nm_ =
        declare_parameter<double>("quiet_torque_range_nm", 0.30);
    filter_cutoff_hz_ =
        declare_parameter<double>("filter_cutoff_hz", 10.0);

    if (!(soft_force_n_ > 0.0 && hard_force_n_ > soft_force_n_ &&
          hard_torque_nm_ > 0.0 && soft_hold_s_ >= 0.010 &&
          soft_hold_s_ <= 0.2 && timeout_s_ >= 0.02 && timeout_s_ <= 0.2 &&
          quiet_check_s_ >= 0.5 && quiet_check_s_ <= 10.0 &&
          filter_cutoff_hz_ > 0.0 && filter_cutoff_hz_ <= 50.0)) {
      throw std::invalid_argument("invalid force-guard parameters");
    }

    status_pub_ = create_publisher<std_msgs::msg::String>(
        status_topic_, rclcpp::QoS(10).reliable().transient_local());
    wrench_sub_ = create_subscription<geometry_msgs::msg::WrenchStamped>(
        wrench_topic_, rclcpp::SensorDataQoS(),
        [this](const geometry_msgs::msg::WrenchStamped::SharedPtr message) {
          onWrench(*message);
        });
    publishState("WAITING", "waiting for fresh wrench samples");
    RCLCPP_WARN(get_logger(),
                "GUARD ONLY: input=%s output=%s; soft=%.1f N, hard=%.1f N, "
                "torque=%.2f Nm. No admittance or automatic forward motion.",
                wrench_topic_.c_str(), status_topic_.c_str(), soft_force_n_,
                hard_force_n_, hard_torque_nm_);
  }

  void prepareForMotion() override {
    const auto data_deadline = Clock::now() + std::chrono::seconds(5);
    while (rclcpp::ok() && Clock::now() < data_deadline &&
           sample_count_.load() < 10) {
      std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (sample_count_.load() < 10 || !fresh()) {
      throw std::runtime_error(
          "no fresh /m3815/wrench_raw data; robot remains unpowered");
    }

    publishState("QUIET_CHECK", "hands off while checking sensor stability");
    const auto deadline = Clock::now() +
                          std::chrono::duration_cast<Clock::duration>(
                              std::chrono::duration<double>(quiet_check_s_));
    double min_force = 1e9;
    double max_force = -1e9;
    double min_torque = 1e9;
    double max_torque = -1e9;
    while (rclcpp::ok() && Clock::now() < deadline) {
      if (!fresh()) {
        throw std::runtime_error("wrench data became stale during quiet check");
      }
      const double force = raw_force_n_.load();
      const double torque = raw_torque_nm_.load();
      min_force = std::min(min_force, force);
      max_force = std::max(max_force, force);
      min_torque = std::min(min_torque, torque);
      max_torque = std::max(max_torque, torque);
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    if (!rclcpp::ok()) throw std::runtime_error("ROS shutdown requested");
    if (max_force - min_force > quiet_force_range_n_ ||
        max_torque - min_torque > quiet_torque_range_nm_) {
      std::ostringstream out;
      out << "sensor not quiet: force range=" << (max_force - min_force)
          << " N, torque range=" << (max_torque - min_torque) << " Nm";
      throw std::runtime_error(out.str());
    }
    RCLCPP_INFO(get_logger(),
                "Quiet wrench verified: force range %.3f N, torque range %.3f "
                "Nm.",
                max_force - min_force, max_torque - min_torque);
  }

  void arm() override {
    decision_.store(ar_assembly_guard::Decision::none);
    soft_since_ns_.store(0);
    armed_.store(true);
  }

  ar_assembly_guard::Decision poll(std::string &reason) override {
    if (!armed_.load()) return ar_assembly_guard::Decision::none;
    if (!fresh()) {
      reason = "wrench topic stale for more than " +
               std::to_string(timeout_s_ * 1000.0) + " ms";
      return ar_assembly_guard::Decision::sensor_timeout;
    }
    const auto decision = decision_.load();
    if (decision == ar_assembly_guard::Decision::none) return decision;
    std::ostringstream out;
    out << std::fixed << std::setprecision(2)
        << "raw force=" << raw_force_n_.load() << " N, filtered force="
        << filtered_force_n_.load() << " N, torque="
        << raw_torque_nm_.load() << " Nm";
    reason = out.str();
    return decision;
  }

  void publishState(const std::string &state,
                    const std::string &detail) override {
    std_msgs::msg::String message;
    std::ostringstream out;
    out << "state=" << state << "; " << detail << "; force_raw="
        << std::fixed << std::setprecision(2) << raw_force_n_.load()
        << " N; force_filtered=" << filtered_force_n_.load()
        << " N; torque=" << raw_torque_nm_.load() << " Nm";
    message.data = out.str();
    status_pub_->publish(message);
    RCLCPP_WARN(get_logger(), "%s", message.data.c_str());
  }

 private:
  static std::int64_t nowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               Clock::now().time_since_epoch())
        .count();
  }

  bool fresh() const {
    const auto last = last_sample_ns_.load();
    if (last == 0) return false;
    return static_cast<double>(nowNs() - last) * 1e-9 <= timeout_s_;
  }

  void onWrench(const geometry_msgs::msg::WrenchStamped &message) {
    const double force = norm3(message.wrench.force.x,
                               message.wrench.force.y,
                               message.wrench.force.z);
    const double torque = norm3(message.wrench.torque.x,
                                message.wrench.torque.y,
                                message.wrench.torque.z);
    const auto now_ns = nowNs();
    const auto previous_ns = last_sample_ns_.exchange(now_ns);
    double filtered = filtered_force_n_.load();
    if (previous_ns == 0) {
      filtered = force;
    } else {
      const double dt = std::clamp(
          static_cast<double>(now_ns - previous_ns) * 1e-9, 0.0001, 0.05);
      const double rc = 1.0 / (2.0 * 3.14159265358979323846 *
                               filter_cutoff_hz_);
      filtered += (dt / (rc + dt)) * (force - filtered);
    }
    raw_force_n_.store(force);
    raw_torque_nm_.store(torque);
    filtered_force_n_.store(filtered);
    sample_count_.fetch_add(1);

    if (!armed_.load()) return;
    if (force >= hard_force_n_ || torque >= hard_torque_nm_) {
      decision_.store(ar_assembly_guard::Decision::hard_stop);
      return;
    }
    if (filtered >= soft_force_n_) {
      auto soft_start = soft_since_ns_.load();
      if (soft_start == 0) {
        soft_since_ns_.compare_exchange_strong(soft_start, now_ns);
      } else if (static_cast<double>(now_ns - soft_start) * 1e-9 >=
                 soft_hold_s_) {
        decision_.store(ar_assembly_guard::Decision::soft_pause);
      }
    } else {
      soft_since_ns_.store(0);
    }
  }

  std::string wrench_topic_;
  std::string status_topic_;
  double soft_force_n_{};
  double hard_force_n_{};
  double hard_torque_nm_{};
  double soft_hold_s_{};
  double timeout_s_{};
  double quiet_check_s_{};
  double quiet_force_range_n_{};
  double quiet_torque_range_nm_{};
  double filter_cutoff_hz_{};
  rclcpp::Subscription<geometry_msgs::msg::WrenchStamped>::SharedPtr
      wrench_sub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr status_pub_;
  std::atomic<std::uint64_t> sample_count_{0};
  std::atomic<std::int64_t> last_sample_ns_{0};
  std::atomic<std::int64_t> soft_since_ns_{0};
  std::atomic<double> raw_force_n_{0.0};
  std::atomic<double> filtered_force_n_{0.0};
  std::atomic<double> raw_torque_nm_{0.0};
  std::atomic<bool> armed_{false};
  std::atomic<ar_assembly_guard::Decision> decision_{
      ar_assembly_guard::Decision::none};
};

}  // namespace

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  int result = 1;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor;
  std::thread spin_thread;
  try {
    auto node = std::make_shared<ForceGuardNode>();
    ar_assembly_guard::active_hook = node.get();
    executor =
        std::make_unique<rclcpp::executors::SingleThreadedExecutor>();
    executor->add_node(node);
    spin_thread = std::thread([&executor]() { executor->spin(); });

    const auto non_ros_arguments = rclcpp::remove_ros_arguments(argc, argv);
    std::vector<std::string> storage = non_ros_arguments;
    std::vector<char *> forwarded;
    forwarded.reserve(storage.size());
    for (auto &argument : storage) forwarded.push_back(argument.data());
    result = arFourPointSmoothTrajectoryMain(
        static_cast<int>(forwarded.size()), forwarded.data());
  } catch (const std::exception &error) {
    std::cerr << "FORCE GUARD NODE ERROR: " << error.what() << '\n';
    result = 1;
  }
  ar_assembly_guard::active_hook = nullptr;
  if (executor) executor->cancel();
  if (spin_thread.joinable()) spin_thread.join();
  if (rclcpp::ok()) rclcpp::shutdown();
  return result;
}
