from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    active_control = LaunchConfiguration("active_control")
    params_file = PathJoinSubstitution(
        [FindPackageShare("ar_admittance_control"), "config", "xb7_assembly_cartesian_6d_admittance.yaml"]
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("active_control", default_value="false"),
            Node(
                package="ar_admittance_control",
                executable="xb7_assembly_cartesian_6d_admittance_node",
                name="xb7_assembly_cartesian_6d_admittance_node",
                output="screen",
                emulate_tty=True,
                parameters=[params_file, {"active_control": active_control}],
            ),
        ]
    )
