import bisect
import csv
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import rclpy
from geometry_msgs.msg import WrenchStamped
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy


CHANNEL_NAMES = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")
CSV_HEADER = (
    "wall_time_s",
    "ros_stamp_s",
    "elapsed_s",
    "fx_n",
    "fy_n",
    "fz_n",
    "mx_nm",
    "my_nm",
    "mz_nm",
)


class ForceSensorMonitor(Node):
    def __init__(self):
        super().__init__("force_sensor_yl_monitor")

        self.declare_parameter("topic_name", "force_sensor/force")
        self.declare_parameter("window_seconds", 10.0)
        self.declare_parameter("print_rate_hz", 5.0)
        self.declare_parameter("plot_rate_hz", 20.0)
        self.declare_parameter("output_dir", "~/force_sensor_logs")
        self.declare_parameter("save_enabled", True)

        self.topic_name = str(self.get_parameter("topic_name").value)
        self.window_seconds = max(
            1.0, float(self.get_parameter("window_seconds").value)
        )
        self.print_rate_hz = max(
            0.0, float(self.get_parameter("print_rate_hz").value)
        )
        self.plot_rate_hz = max(
            1.0, float(self.get_parameter("plot_rate_hz").value)
        )
        self.save_enabled = bool(self.get_parameter("save_enabled").value)

        # Keep enough history for sensors running at up to 1 kHz.
        max_samples = max(2000, int(self.window_seconds * 1000.0) + 1000)
        self._times = deque(maxlen=max_samples)
        self._channels = [deque(maxlen=max_samples) for _ in CHANNEL_NAMES]
        self._lock = threading.Lock()
        self._first_receive_monotonic = None
        self._last_print_monotonic = 0.0
        self._last_flush_monotonic = 0.0
        self.sample_count = 0

        self.log_path = None
        self._log_file = None
        self._csv_writer = None
        if self.save_enabled:
            output_dir = Path(
                str(self.get_parameter("output_dir").value)
            ).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = datetime.now().strftime("m3815_%Y%m%d_%H%M%S.csv")
            self.log_path = output_dir / filename
            self._log_file = self.log_path.open(
                "w", encoding="utf-8", newline=""
            )
            self._csv_writer = csv.writer(self._log_file)
            self._csv_writer.writerow(CSV_HEADER)
            self._log_file.flush()

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1000,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.subscription = self.create_subscription(
            WrenchStamped, self.topic_name, self._on_wrench, qos
        )

        self.get_logger().info(f"实时监视话题: {self.topic_name}")
        if self.log_path is not None:
            self.get_logger().info(f"CSV 自动保存: {self.log_path}")
        else:
            self.get_logger().warning("CSV 自动保存已关闭")

    def _on_wrench(self, message: WrenchStamped):
        receive_monotonic = time.monotonic()
        wall_time = time.time()
        if self._first_receive_monotonic is None:
            self._first_receive_monotonic = receive_monotonic
            self._last_flush_monotonic = receive_monotonic

        elapsed = receive_monotonic - self._first_receive_monotonic
        values = (
            message.wrench.force.x,
            message.wrench.force.y,
            message.wrench.force.z,
            message.wrench.torque.x,
            message.wrench.torque.y,
            message.wrench.torque.z,
        )
        ros_stamp = (
            float(message.header.stamp.sec)
            + float(message.header.stamp.nanosec) * 1e-9
        )

        with self._lock:
            self._times.append(elapsed)
            for channel, value in zip(self._channels, values):
                channel.append(value)
            self.sample_count += 1

        if self._csv_writer is not None:
            self._csv_writer.writerow(
                (wall_time, ros_stamp, elapsed, *values)
            )
            if receive_monotonic - self._last_flush_monotonic >= 1.0:
                self._log_file.flush()
                self._last_flush_monotonic = receive_monotonic

        if self.print_rate_hz > 0.0:
            print_period = 1.0 / self.print_rate_hz
            if receive_monotonic - self._last_print_monotonic >= print_period:
                self._last_print_monotonic = receive_monotonic
                fx, fy, fz, mx, my, mz = values
                print(
                    f"Fx={fx:9.3f} N  Fy={fy:9.3f} N  Fz={fz:9.3f} N  "
                    f"Mx={mx:9.5f} Nm  My={my:9.5f} Nm  Mz={mz:9.5f} Nm",
                    flush=True,
                )

    def snapshot(self):
        with self._lock:
            times = list(self._times)
            channels = [list(channel) for channel in self._channels]

        if not times:
            return times, channels

        cutoff = times[-1] - self.window_seconds
        start = bisect.bisect_left(times, cutoff)
        times = times[start:]
        channels = [channel[start:] for channel in channels]

        # Limit points drawn per refresh while retaining every sample in CSV.
        max_plot_points = 4000
        if len(times) > max_plot_points:
            step = (len(times) + max_plot_points - 1) // max_plot_points
            times = times[::step]
            channels = [channel[::step] for channel in channels]
        return times, channels

    def close_log(self):
        if self._log_file is not None:
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None


def _spin_executor(executor):
    try:
        executor.spin()
    except (ExternalShutdownException, KeyboardInterrupt):
        pass


def main(args=None):
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
    except ImportError as exc:
        raise SystemExit(
            "缺少 matplotlib，请执行: sudo apt install python3-matplotlib"
        ) from exc

    rclpy.init(args=args)
    node = ForceSensorMonitor()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(
        target=_spin_executor, args=(executor,), daemon=True
    )
    spin_thread.start()

    figure = None
    try:
        figure, (force_axis, torque_axis) = plt.subplots(
            2, 1, figsize=(12, 8), sharex=True
        )
        force_lines = [
            force_axis.plot([], [], label=name, linewidth=1.0)[0]
            for name in CHANNEL_NAMES[:3]
        ]
        torque_lines = [
            torque_axis.plot([], [], label=name, linewidth=1.0)[0]
            for name in CHANNEL_NAMES[3:]
        ]

        force_axis.set_ylabel("Force (N)")
        torque_axis.set_ylabel("Torque (Nm)")
        torque_axis.set_xlabel("Elapsed time (s)")
        force_axis.grid(True, alpha=0.3)
        torque_axis.grid(True, alpha=0.3)
        force_axis.legend(loc="upper right", ncol=3)
        torque_axis.legend(loc="upper right", ncol=3)
        status = figure.suptitle("Waiting for /force_sensor/force ...")
        figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))

        def update_plot(_frame):
            times, channels = node.snapshot()
            if not times:
                return (*force_lines, *torque_lines, status)

            for line, values in zip(force_lines, channels[:3]):
                line.set_data(times, values)
            for line, values in zip(torque_lines, channels[3:]):
                line.set_data(times, values)

            right = times[-1]
            left = max(0.0, right - node.window_seconds)
            force_axis.set_xlim(left, max(node.window_seconds, right))
            force_axis.relim()
            force_axis.autoscale_view(scalex=False, scaley=True)
            torque_axis.relim()
            torque_axis.autoscale_view(scalex=False, scaley=True)
            status.set_text(
                f"M3815 six-axis force sensor | samples: {node.sample_count} | "
                f"window: {node.window_seconds:g} s"
            )
            return (*force_lines, *torque_lines, status)

        animation = FuncAnimation(
            figure,
            update_plot,
            interval=max(20, int(1000.0 / node.plot_rate_hz)),
            blit=False,
            cache_frame_data=False,
        )
        # Keep a live reference until the GUI exits.
        figure._force_sensor_animation = animation
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        if figure is not None:
            plt.close(figure)
        executor.shutdown(timeout_sec=2.0)
        spin_thread.join(timeout=2.0)
        node.close_log()
        log_path = node.log_path
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        if log_path is not None:
            print(f"\nCSV 已保存: {log_path}")


if __name__ == "__main__":
    main()
