import rclpy
from geometry_msgs.msg import WrenchStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from force_sensor_yl.driver import SRIForceSensor


class ForceSensorNode(Node):
    def __init__(self):
        super().__init__("force_sensor_yl_node")
        self._shutting_down = False
        self.sensor = SRIForceSensor()

        self.declare_parameter("port", "/dev/ttyUSB0")
        self.declare_parameter("baud_rate", 115200)
        self.declare_parameter("frame_id", "force_sensor_link")
        self.declare_parameter("topic_name", "force_sensor/force")

        self.port = self.get_parameter("port").value
        self.baud_rate = self.get_parameter("baud_rate").value
        self.frame_id = self.get_parameter("frame_id").value
        self.topic_name = self.get_parameter("topic_name").value

        self.get_logger().info(
            f"正在连接 M3815CA2 RS485 ({self.port}:{self.baud_rate})..."
        )
        if not self.sensor.connect(self.port, self.baud_rate):
            raise RuntimeError("传感器连接失败，请检查串口路径、权限和物理连接")

        if self.sensor.clear_zero():
            self.get_logger().info("传感器软件清零/去皮成功")
        else:
            self.get_logger().warning("传感器软件清零失败，将继续读取未去皮数据")
            self.sensor.use_software_tare = False

        self.publisher = self.create_publisher(
            WrenchStamped, self.topic_name, 10
        )
        self.timer = self.create_timer(0.001, self._publish_available)
        self.get_logger().info(
            f"节点已就绪，按设备实际上传频率发布，话题: {self.topic_name}"
        )

    def _publish_available(self):
        if self._shutting_down or not rclpy.ok():
            return

        for values in self.sensor.read_available():
            message = WrenchStamped()
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = self.frame_id
            message.wrench.force.x = values[0]
            message.wrench.force.y = values[1]
            message.wrench.force.z = values[2]
            message.wrench.torque.x = values[3]
            message.wrench.torque.y = values[4]
            message.wrench.torque.z = values[5]
            self.publisher.publish(message)

    def destroy_node(self):
        self._shutting_down = True
        if hasattr(self, "timer"):
            self.timer.cancel()
        self.sensor.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ForceSensorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception as exc:
        if rclpy.ok():
            print(f"节点异常退出: {exc}")
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
