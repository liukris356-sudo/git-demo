import time

import rclpy
from geometry_msgs.msg import WrenchStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from force_sensor_ta67l.driver import SERIAL_MODES, TA67LForceSensor


class TA67LForceSensorNode(Node):
    def __init__(self):
        super().__init__("force_sensor_ta67l_node")
        self._shutting_down = False

        self.declare_parameter("port", "/dev/ttyUSB0")
        self.declare_parameter("serial_mode", "modbus")
        self.declare_parameter("baud_rate", 0)
        self.declare_parameter("poll_rate_hz", 25.0)
        self.declare_parameter("frame_id", "force_sensor_link")
        self.declare_parameter("topic_name", "/ta67l/wrench_raw")
        self.declare_parameter("status_topic_name", "/ta67l/channel_status")
        self.declare_parameter("force_counts_per_n", 1000.0)
        self.declare_parameter("torque_counts_per_nm", 1000.0)
        self.declare_parameter("crc_mode", "auto")
        self.declare_parameter("connect_timeout_s", 35.0)
        self.declare_parameter("tare_on_start", True)
        self.declare_parameter("tare_samples", 100)

        self.port = str(self.get_parameter("port").value)
        self.serial_mode = str(self.get_parameter("serial_mode").value)
        baud_parameter = int(self.get_parameter("baud_rate").value)
        self.poll_rate_hz = float(self.get_parameter("poll_rate_hz").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.topic_name = str(self.get_parameter("topic_name").value)
        self.status_topic_name = str(
            self.get_parameter("status_topic_name").value
        )
        force_scale = float(self.get_parameter("force_counts_per_n").value)
        torque_scale = float(self.get_parameter("torque_counts_per_nm").value)
        crc_mode = str(self.get_parameter("crc_mode").value)
        connect_timeout = float(self.get_parameter("connect_timeout_s").value)
        tare_on_start = bool(self.get_parameter("tare_on_start").value)
        tare_samples = int(self.get_parameter("tare_samples").value)

        if self.serial_mode not in SERIAL_MODES:
            raise ValueError(f"serial_mode必须是: {', '.join(SERIAL_MODES)}")
        self.baud_rate = baud_parameter or (
            115200 if self.serial_mode == "modbus" else 460800
        )
        if (
            self.baud_rate <= 0
            or connect_timeout <= 0.0
            or tare_samples <= 0
            or self.poll_rate_hz <= 0.0
        ):
            raise ValueError("波特率、超时、清零采样数和轮询频率必须为正数")

        self.sensor = TA67LForceSensor(
            force_counts_per_n=force_scale,
            torque_counts_per_nm=torque_scale,
            crc_mode=crc_mode,
            serial_mode=self.serial_mode,
        )

        if self.serial_mode == "modbus":
            self.get_logger().info(
                f"正在连接 TA67L Modbus ({self.port}:{self.baud_rate})，"
                "轮询地址1～6"
            )
        else:
            self.get_logger().info(
                f"正在连接 TA67L 连续输出 ({self.port}:{self.baud_rate})；"
                "若刚上电，最多需等待约30秒"
            )
        if not self.sensor.connect(
            self.port,
            self.baud_rate,
            stream_timeout_s=connect_timeout,
        ):
            raise RuntimeError("TA67L 连接失败，请检查串口、供电、A/B和通信模式")

        if tare_on_start:
            if self.sensor.clear_zero(samples=tare_samples):
                self.get_logger().info("TA67L 软件清零成功")
            else:
                self.get_logger().warning("软件清零失败，将发布未去皮数据")
                self.sensor.use_software_tare = False
        else:
            self.sensor.use_software_tare = False
            self.get_logger().warning("已关闭启动软件清零，将发布未去皮数据")

        self.publisher = self.create_publisher(WrenchStamped, self.topic_name, 10)
        self.status_publisher = self.create_publisher(
            UInt8MultiArray, self.status_topic_name, 10
        )
        self._last_statuses = None
        self._last_status_publish = 0.0
        self._last_fault_warning = 0.0
        self._fault_mask = 0x18 if self.serial_mode == "modbus" else 0x33
        timer_period = (
            1.0 / self.poll_rate_hz if self.serial_mode == "modbus" else 0.001
        )
        self.timer = self.create_timer(timer_period, self._publish_available)
        self.get_logger().info(
            f"TA67L 已就绪；mode={self.serial_mode}；"
            f"六维力话题: {self.topic_name}；状态话题: {self.status_topic_name}"
        )

    def _publish_status(self, statuses, now_monotonic: float) -> None:
        changed = statuses != self._last_statuses
        if not changed and now_monotonic - self._last_status_publish < 0.1:
            return

        message = UInt8MultiArray()
        message.data = list(statuses)
        self.status_publisher.publish(message)
        self._last_statuses = statuses
        self._last_status_publish = now_monotonic

        if any(status & self._fault_mask for status in statuses):
            if now_monotonic - self._last_fault_warning >= 1.0:
                self._last_fault_warning = now_monotonic
                formatted = " ".join(f"0x{x:02X}" for x in statuses)
                self.get_logger().warning(f"TA67L 通道状态异常: {formatted}")

    def _publish_available(self) -> None:
        if self._shutting_down or not rclpy.ok():
            return

        for frame in self.sensor.read_available():
            message = WrenchStamped()
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = self.frame_id
            message.wrench.force.x = frame.values[0]
            message.wrench.force.y = frame.values[1]
            message.wrench.force.z = frame.values[2]
            message.wrench.torque.x = frame.values[3]
            message.wrench.torque.y = frame.values[4]
            message.wrench.torque.z = frame.values[5]
            self.publisher.publish(message)
            self._publish_status(frame.statuses, time.monotonic())

    def destroy_node(self):
        self._shutting_down = True
        if hasattr(self, "timer"):
            self.timer.cancel()
        if hasattr(self, "sensor"):
            self.sensor.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = TA67LForceSensorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception as exc:
        if rclpy.ok():
            print(f"TA67L 节点异常退出: {exc}")
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
