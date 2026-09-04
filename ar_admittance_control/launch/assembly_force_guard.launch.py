from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    package_share = get_package_share_directory("ar_admittance_control")
    params = os.path.join(package_share, "config", "assembly_force_guard.yaml")

    arguments = [
        DeclareLaunchArgument("port", default_value="/dev/ttyUSB0"),
        DeclareLaunchArgument("robot_ip", default_value="192.168.2.160"),
        DeclareLaunchArgument("local_ip", default_value="192.168.2.100"),
        DeclareLaunchArgument("tool", default_value="g_tool_1"),
        DeclareLaunchArgument("workobject", default_value="g_wobj_0"),
        DeclareLaunchArgument("points_csv"),
        DeclareLaunchArgument("motion_mode", default_value="WIDE_RUN"),
        DeclareLaunchArgument("linear_mm_s", default_value="1.0"),
        DeclareLaunchArgument("rotation_deg_s", default_value="1.0"),
    ]

    sensor = Node(
        package="force_sensor_yl",
        executable="force_sensor_yl_node",
        name="force_sensor_yl_node",
        output="screen",
        parameters=[{
            "port": LaunchConfiguration("port"),
            "topic_name": "/m3815/wrench_raw",
        }],
    )

    guard = Node(
        package="ar_admittance_control",
        executable="ar_assembly_force_guard_node",
        name="ar_assembly_force_guard_node",
        output="screen",
        emulate_tty=True,
        parameters=[params],
        arguments=[
            LaunchConfiguration("robot_ip"),
            LaunchConfiguration("local_ip"),
            LaunchConfiguration("tool"),
            LaunchConfiguration("workobject"),
            LaunchConfiguration("points_csv"),
            LaunchConfiguration("motion_mode"),
            LaunchConfiguration("linear_mm_s"),
            LaunchConfiguration("rotation_deg_s"),
        ],
    )

    return LaunchDescription(arguments + [sensor, guard])
