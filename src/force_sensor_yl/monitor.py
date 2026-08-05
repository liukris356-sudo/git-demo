import bisect
import csv
import threading
import time
from array import array
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
        self.output_dir = Path(
            str(self.get_parameter("output_dir").value)
        ).expanduser()

        # Keep enough history for sensors running at up to 1 kHz.
        max_samples = max(2000, int(self.window_seconds * 1000.0) + 1000)
        self._times = deque(maxlen=max_samples)
        self._channels = [deque(maxlen=max_samples) for _ in CHANNEL_NAMES]
        self._lock = threading.Lock()
        self._first_receive_monotonic = None
        self._last_receive_monotonic = None
        self._last_print_monotonic = 0.0
        self.sample_count = 0
        self._recording = False
        self._record_dirty = False
        self._record_columns = [array("d") for _ in CSV_HEADER]

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1000,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.subscription = self.create_subscription(
            WrenchStamped, self.topic_name, self._on_wrench, qos
        )

        self.get_logger().info(f"实时监视话题: {self.topic_name}")
        self.get_logger().info("CSV 自动保存已关闭，请使用曲线窗口按钮记录和保存")

    def _on_wrench(self, message: WrenchStamped):
        receive_monotonic = time.monotonic()
        self._last_receive_monotonic = receive_monotonic
        wall_time = time.time()
        if self._first_receive_monotonic is None:
            self._first_receive_monotonic = receive_monotonic

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
            if self._recording:
                row = (wall_time, ros_stamp, elapsed, *values)
                for column, value in zip(self._record_columns, row):
                    column.append(value)
                self._record_dirty = True

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

        # Limit points drawn per refresh. Button-controlled recording retains
        # every received sample in a compact array of doubles.
        max_plot_points = 4000
        if len(times) > max_plot_points:
            step = (len(times) + max_plot_points - 1) // max_plot_points
            times = times[::step]
            channels = [channel[::step] for channel in channels]
        return times, channels

    def data_age(self) -> float:
        if self._last_receive_monotonic is None:
            return float("inf")
        return time.monotonic() - self._last_receive_monotonic

    def start_recording(self):
        with self._lock:
            self._recording = True

    def stop_recording(self):
        with self._lock:
            self._recording = False

    def clear_recording(self):
        with self._lock:
            self._recording = False
            for column in self._record_columns:
                del column[:]
            self._record_dirty = False

    def recording_state(self):
        with self._lock:
            return (
                self._recording,
                len(self._record_columns[0]),
                self._record_dirty,
            )

    def save_csv(self, path: Path) -> int:
        with self._lock:
            columns = [array("d", column) for column in self._record_columns]

        sample_count = len(columns[0])
        if sample_count == 0:
            return 0

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as log_file:
            writer = csv.writer(log_file)
            writer.writerow(CSV_HEADER)
            writer.writerows(zip(*columns))

        with self._lock:
            self._record_dirty = False
        return sample_count


def _spin_executor(executor):
    try:
        executor.spin()
    except (ExternalShutdownException, KeyboardInterrupt):
        pass


def main(args=None):
    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
        from matplotlib.widgets import Button
        from tkinter import filedialog
    except ImportError as exc:
        raise SystemExit(
            "缺少 matplotlib，请执行: sudo apt install python3-matplotlib"
        ) from exc

    rclpy.init(args=args)
    try:
        node = ForceSensorMonitor()
    except (KeyboardInterrupt, ExternalShutdownException):
        if rclpy.ok():
            rclpy.shutdown()
        return
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
        record_status = figure.text(
            0.5,
            0.095,
            "Not recording. Live curves are not saved automatically.",
            ha="center",
        )
        figure.tight_layout(rect=(0.0, 0.14, 1.0, 0.96))

        start_button = Button(
            figure.add_axes((0.08, 0.02, 0.18, 0.055)), "Start / Resume"
        )
        stop_button = Button(
            figure.add_axes((0.29, 0.02, 0.18, 0.055)), "Stop Recording"
        )
        save_button = Button(
            figure.add_axes((0.53, 0.02, 0.18, 0.055)), "Save CSV..."
        )
        clear_button = Button(
            figure.add_axes((0.74, 0.02, 0.18, 0.055)), "Clear Buffer"
        )

        def update_record_status(message=None):
            recording, count, dirty = node.recording_state()
            if message is None:
                state = "RECORDING" if recording else "STOPPED"
                unsaved = " | unsaved" if dirty else ""
                message = f"{state} | buffered samples: {count}{unsaved}"
            record_status.set_text(message)
            figure.canvas.draw_idle()

        def start_recording(_event):
            node.start_recording()
            update_record_status()

        def stop_recording(_event):
            node.stop_recording()
            update_record_status()

        def clear_recording(_event):
            node.clear_recording()
            update_record_status("Buffer cleared. Nothing will be saved.")

        def save_recording(_event):
            node.stop_recording()
            _, count, _ = node.recording_state()
            if count == 0:
                update_record_status("No recorded samples. Click Start / Resume first.")
                return

            node.output_dir.mkdir(parents=True, exist_ok=True)
            filename = datetime.now().strftime("m3815_%Y%m%d_%H%M%S.csv")
            parent = getattr(figure.canvas.manager, "window", None)
            path = filedialog.asksaveasfilename(
                parent=parent,
                title="Save M3815 force sensor data",
                initialdir=str(node.output_dir),
                initialfile=filename,
                defaultextension=".csv",
                filetypes=(("CSV text", "*.csv"), ("All files", "*.*")),
            )
            if not path:
                update_record_status("Save cancelled. Data remains in memory.")
                return

            try:
                saved_count = node.save_csv(Path(path))
                update_record_status(
                    f"Saved {saved_count} samples to {Path(path).name}"
                )
                print(f"\nCSV 已保存: {path}", flush=True)
            except Exception as exc:
                node.get_logger().error(f"保存 CSV 失败: {exc}")
                update_record_status(f"Save failed: {exc}")

        start_button.on_clicked(start_recording)
        stop_button.on_clicked(stop_recording)
        save_button.on_clicked(save_recording)
        clear_button.on_clicked(clear_recording)
        figure._force_sensor_buttons = (
            start_button,
            stop_button,
            save_button,
            clear_button,
        )

        def update_plot(_frame):
            times, channels = node.snapshot()
            if not times:
                status.set_color("red")
                status.set_text("NO LIVE DATA - waiting for force sensor topic")
                return (*force_lines, *torque_lines, status)

            data_age = node.data_age()
            if data_age > 1.0:
                for line in (*force_lines, *torque_lines):
                    line.set_data([], [])
                status.set_color("red")
                status.set_text(
                    f"NO LIVE DATA - last sample {data_age:.1f} s ago"
                )
                return (*force_lines, *torque_lines, status, record_status)

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
            status.set_color("black")
            status.set_text(
                f"M3815 six-axis force sensor | samples: {node.sample_count} | "
                f"window: {node.window_seconds:g} s"
            )
            recording, count, dirty = node.recording_state()
            state = "RECORDING" if recording else "STOPPED"
            unsaved = " | unsaved" if dirty else ""
            record_status.set_text(
                f"{state} | buffered samples: {count}{unsaved}"
            )
            return (*force_lines, *torque_lines, status, record_status)

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
        _, buffered_count, dirty = node.recording_state()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        if dirty:
            print(
                f"\n警告: {buffered_count} 条记录未保存，关闭窗口后已丢弃。",
                flush=True,
            )


if __name__ == "__main__":
    main()
