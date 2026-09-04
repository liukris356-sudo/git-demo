from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    port = LaunchConfiguration("port")
    params_file = PathJoinSubstitution(
        [FindPackageShare("ar_admittance_control"), "config", "admittance_cartesian_6d.yaml"]
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("port", default_value="/dev/ttyUSB0"),
            Node(
                package="force_sensor_yl",
                executable="force_sensor_yl_node",
                name="force_sensor_yl_node",
                output="screen",
                parameters=[{
                    "port": port,
                    "baud_rate": 115200,
                    "frame_id": "force_sensor_link",
                    "topic_name": "/m3815/wrench_raw",
                }],
            ),
            Node(
                package="ar_admittance_control",
                executable="ar_admittance_cartesian_6d_node",
                name="ar_admittance_cartesian_6d_node",
                output="screen",
                emulate_tty=True,
                parameters=[params_file],
            ),
        ]
    )
