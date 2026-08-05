import bisect
import csv
import math
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
        self.declare_parameter("display_sample_rate_hz", 25.0)
        self.declare_parameter("display_cutoff_hz", 8.0)
        self.declare_parameter("dominant_threshold_n", 0.10)
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
        self.display_sample_rate_hz = max(
            1.0, float(self.get_parameter("display_sample_rate_hz").value)
        )
        self.display_cutoff_hz = max(
            0.1, float(self.get_parameter("display_cutoff_hz").value)
        )
        self.dominant_threshold_n = max(
            0.0, float(self.get_parameter("dominant_threshold_n").value)
        )
        self.output_dir = Path(
            str(self.get_parameter("output_dir").value)
        ).expanduser()

        # The plot keeps a filtered, decimated display stream. CSV recording
        # remains at the full incoming sensor rate.
        max_samples = max(
            500,
            int(self.window_seconds * self.display_sample_rate_hz) + 200,
        )
        self._times = deque(maxlen=max_samples)
        self._channels = [deque(maxlen=max_samples) for _ in CHANNEL_NAMES]
        self._dominant_codes = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._first_receive_monotonic = None
        self._last_receive_monotonic = None
        self._last_display_monotonic = None
        self._last_print_monotonic = 0.0
        self._filtered_values = None
        self._latest_values = None
        self._dominant_axis = None
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
        self.get_logger().info(
            f"显示滤波 {self.display_cutoff_hz:.1f} Hz，"
            f"显示采样 {self.display_sample_rate_hz:.1f} Hz；"
            "CSV 记录保持原始速率"
        )
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
            self._latest_values = values
            self.sample_count += 1
            if self._recording:
                row = (wall_time, ros_stamp, elapsed, *values)
                for column, value in zip(self._record_columns, row):
                    column.append(value)
                self._record_dirty = True

            if self._filtered_values is None:
                self._filtered_values = list(values)
            else:
                # Nominal 500 Hz is used deliberately because USB serial data
                # can arrive in bursts with near-zero host-side intervals.
                alpha = 1.0 - math.exp(
                    -2.0 * math.pi * self.display_cutoff_hz / 500.0
                )
                for index, value in enumerate(values):
                    self._filtered_values[index] += alpha * (
                        value - self._filtered_values[index]
                    )

            display_period = 1.0 / self.display_sample_rate_hz
            if (
                self._last_display_monotonic is None
                or receive_monotonic - self._last_display_monotonic
                >= display_period
            ):
                self._last_display_monotonic = receive_monotonic
                self._append_display_sample(elapsed)

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

    def _append_display_sample(self, elapsed):
        values = tuple(self._filtered_values)
        self._times.append(elapsed)
        for channel, value in zip(self._channels, values):
            channel.append(value)

        force_abs = [abs(value) for value in values[:3]]
        candidate = max(range(3), key=force_abs.__getitem__)
        if force_abs[candidate] < self.dominant_threshold_n:
            self._dominant_axis = None
            dominant_code = 0
        else:
            if self._dominant_axis is not None and candidate != self._dominant_axis:
                current_value = force_abs[self._dominant_axis]
                if force_abs[candidate] < current_value * 1.20:
                    candidate = self._dominant_axis
            self._dominant_axis = candidate
            sign = 1 if values[candidate] >= 0.0 else -1
            dominant_code = sign * (candidate + 1)
        self._dominant_codes.append(dominant_code)

    def snapshot(self):
        with self._lock:
            times = list(self._times)
            channels = [list(channel) for channel in self._channels]
            dominant_codes = list(self._dominant_codes)

        if not times:
            return times, channels, dominant_codes

        cutoff = times[-1] - self.window_seconds
        start = bisect.bisect_left(times, cutoff)
        times = times[start:]
        channels = [channel[start:] for channel in channels]
        dominant_codes = dominant_codes[start:]
        return times, channels, dominant_codes

    def latest_display_values(self):
        with self._lock:
            if self._filtered_values is None:
                return None
            return tuple(self._filtered_values)

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
        plt.rcParams["font.sans-serif"] = [
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
            "SimHei",
            "Microsoft YaHei",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        figure, (force_axis, torque_axis, dominant_axis) = plt.subplots(
            3,
            1,
            figsize=(12, 10),
            sharex=True,
            gridspec_kw={"height_ratios": (2.0, 2.0, 1.0)},
        )
        force_lines = [
            force_axis.plot([], [], label=name, linewidth=1.0)[0]
            for name in CHANNEL_NAMES[:3]
        ]
        torque_lines = [
            torque_axis.plot([], [], label=name, linewidth=1.0)[0]
            for name in CHANNEL_NAMES[3:]
        ]
        dominant_line = dominant_axis.step(
            [], [], where="post", color="#7b2cbf", linewidth=1.5
        )[0]

        force_axis.set_ylabel("力（N）")
        torque_axis.set_ylabel("力矩（Nm）")
        dominant_axis.set_ylabel("主导方向")
        dominant_axis.set_xlabel("经过时间（秒）")
        force_axis.grid(True, alpha=0.3)
        torque_axis.grid(True, alpha=0.3)
        dominant_axis.grid(True, alpha=0.3)
        force_axis.legend(loc="upper right", ncol=3)
        torque_axis.legend(loc="upper right", ncol=3)
        dominant_axis.set_yticks((-3, -2, -1, 0, 1, 2, 3))
        dominant_axis.set_yticklabels(("-Z", "-Y", "-X", "无", "+X", "+Y", "+Z"))
        dominant_axis.set_ylim(-3.4, 3.4)
        status = figure.suptitle("正在等待六维力传感器数据……")
        current_values = figure.text(
            0.5,
            0.132,
            "当前值：尚无数据",
            ha="center",
            fontsize=10,
        )
        record_status = figure.text(
            0.5,
            0.088,
            "未记录：实时曲线不会自动保存",
            ha="center",
        )
        figure.tight_layout(rect=(0.0, 0.18, 1.0, 0.96))

        start_button = Button(
            figure.add_axes((0.025, 0.02, 0.17, 0.052)), "开始/继续记录"
        )
        stop_button = Button(
            figure.add_axes((0.215, 0.02, 0.17, 0.052)), "停止记录"
        )
        save_button = Button(
            figure.add_axes((0.405, 0.02, 0.17, 0.052)), "保存CSV……"
        )
        clear_button = Button(
            figure.add_axes((0.595, 0.02, 0.17, 0.052)), "清空记录"
        )
        pause_button = Button(
            figure.add_axes((0.785, 0.02, 0.17, 0.052)), "暂停显示"
        )

        display_paused = False
        paused_snapshot = None
        paused_values = None

        def format_current_values(values, dominant_code, paused=False):
            if values is None:
                return "当前值：尚无数据"
            fx, fy, fz, mx, my, mz = values
            prefix = "暂停时刻" if paused else "当前滤波值"
            numeric = (
                f"{prefix}：Fx={fx:+.3f} N  Fy={fy:+.3f} N  "
                f"Fz={fz:+.3f} N  Mx={mx:+.4f} Nm  "
                f"My={my:+.4f} Nm  Mz={mz:+.4f} Nm"
            )
            if dominant_code == 0:
                dominant = "无明显主导力"
            else:
                axis_index = abs(int(dominant_code)) - 1
                direction = ("+" if dominant_code > 0 else "-") + "XYZ"[
                    axis_index
                ]
                dominant = (
                    f"主导力（传感器坐标系）：{direction} "
                    f"({values[axis_index]:+.3f} N)"
                )
            return f"{numeric}\n{dominant}"

        def update_record_status(message=None):
            recording, count, dirty = node.recording_state()
            if message is None:
                state = "正在记录" if recording else "记录已停止"
                unsaved = "｜尚未保存" if dirty else ""
                message = f"{state}｜缓存样本：{count}{unsaved}"
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
            update_record_status("记录缓存已清空，不会保存任何数据")

        def save_recording(_event):
            node.stop_recording()
            _, count, _ = node.recording_state()
            if count == 0:
                update_record_status("没有可保存的数据，请先点击“开始/继续记录”")
                return

            node.output_dir.mkdir(parents=True, exist_ok=True)
            filename = datetime.now().strftime("m3815_%Y%m%d_%H%M%S.csv")
            parent = getattr(figure.canvas.manager, "window", None)
            path = filedialog.asksaveasfilename(
                parent=parent,
                title="保存 M3815 六维力数据",
                initialdir=str(node.output_dir),
                initialfile=filename,
                defaultextension=".csv",
                filetypes=(("CSV 文本", "*.csv"), ("所有文件", "*.*")),
            )
            if not path:
                update_record_status("已取消保存，数据仍保留在内存中")
                return

            try:
                saved_count = node.save_csv(Path(path))
                update_record_status(
                    f"已保存 {saved_count} 条样本到 {Path(path).name}"
                )
                print(f"\nCSV 已保存: {path}", flush=True)
            except Exception as exc:
                node.get_logger().error(f"保存 CSV 失败: {exc}")
                update_record_status(f"保存失败：{exc}")

        def toggle_pause(_event):
            nonlocal display_paused, paused_snapshot, paused_values
            if not display_paused:
                paused_snapshot = node.snapshot()
                paused_values = node.latest_display_values()
                display_paused = True
                pause_button.label.set_text("继续显示")
            else:
                display_paused = False
                paused_snapshot = None
                paused_values = None
                pause_button.label.set_text("暂停显示")
            figure.canvas.draw_idle()

        start_button.on_clicked(start_recording)
        stop_button.on_clicked(stop_recording)
        save_button.on_clicked(save_recording)
        clear_button.on_clicked(clear_recording)
        pause_button.on_clicked(toggle_pause)
        figure._force_sensor_buttons = (
            start_button,
            stop_button,
            save_button,
            clear_button,
            pause_button,
        )

        def update_plot(_frame):
            if display_paused and paused_snapshot is not None:
                times, channels, dominant_codes = paused_snapshot
                values = paused_values
            else:
                times, channels, dominant_codes = node.snapshot()
                values = node.latest_display_values()

            if not times:
                status.set_color("red")
                status.set_text("无实时数据——正在等待传感器话题")
                current_values.set_text("当前值：尚无数据")
                return (*force_lines, *torque_lines, dominant_line, status)

            data_age = node.data_age()
            if not display_paused and data_age > 1.0:
                for line in (*force_lines, *torque_lines):
                    line.set_data([], [])
                dominant_line.set_data([], [])
                status.set_color("red")
                status.set_text(
                    f"无实时数据——最后一帧距今 {data_age:.1f} 秒"
                )
                current_values.set_text("当前值：数据已断流")
                return (
                    *force_lines,
                    *torque_lines,
                    dominant_line,
                    status,
                    record_status,
                    current_values,
                )

            for line, series in zip(force_lines, channels[:3]):
                line.set_data(times, series)
            for line, series in zip(torque_lines, channels[3:]):
                line.set_data(times, series)
            dominant_line.set_data(times, dominant_codes)

            right = times[-1]
            left = max(0.0, right - node.window_seconds)
            force_axis.set_xlim(left, max(node.window_seconds, right))
            force_axis.relim()
            force_axis.autoscale_view(scalex=False, scaley=True)
            torque_axis.relim()
            torque_axis.autoscale_view(scalex=False, scaley=True)
            if display_paused:
                status.set_color("#d97706")
                status.set_text(
                    "显示已暂停——后台接收和正在进行的记录不受影响"
                )
            else:
                status.set_color("black")
                status.set_text(
                    f"M3815 六维力传感器｜实时样本：{node.sample_count}｜"
                    f"显示窗口：{node.window_seconds:g} 秒｜"
                    f"显示滤波：{node.display_cutoff_hz:g} Hz"
                )
            dominant_code = dominant_codes[-1] if dominant_codes else 0
            current_values.set_text(
                format_current_values(values, dominant_code, display_paused)
            )
            recording, count, dirty = node.recording_state()
            state = "正在记录" if recording else "记录已停止"
            unsaved = "｜尚未保存" if dirty else ""
            record_status.set_text(
                f"{state}｜缓存样本：{count}{unsaved}"
            )
            return (
                *force_lines,
                *torque_lines,
                dominant_line,
                status,
                record_status,
                current_values,
            )

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
