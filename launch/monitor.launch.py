from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    port = LaunchConfiguration("port")
    baud_rate = LaunchConfiguration("baud_rate")
    topic_name = LaunchConfiguration("topic_name")
    frame_id = LaunchConfiguration("frame_id")
    window_seconds = LaunchConfiguration("window_seconds")
    print_rate_hz = LaunchConfiguration("print_rate_hz")
    plot_rate_hz = LaunchConfiguration("plot_rate_hz")
    output_dir = LaunchConfiguration("output_dir")

    return LaunchDescription(
        [
            DeclareLaunchArgument("port", default_value="/dev/ttyUSB0"),
            DeclareLaunchArgument("baud_rate", default_value="115200"),
            DeclareLaunchArgument(
                "topic_name", default_value="force_sensor/force"
            ),
            DeclareLaunchArgument("frame_id", default_value="force_sensor_link"),
            DeclareLaunchArgument("window_seconds", default_value="10.0"),
            DeclareLaunchArgument("print_rate_hz", default_value="5.0"),
            DeclareLaunchArgument("plot_rate_hz", default_value="20.0"),
            DeclareLaunchArgument(
                "output_dir", default_value="~/force_sensor_logs"
            ),
            Node(
                package="force_sensor_yl",
                executable="force_sensor_yl_node",
                name="force_sensor_yl_node",
                output="screen",
                parameters=[
                    {
                        "port": port,
                        "baud_rate": ParameterValue(baud_rate, value_type=int),
                        "topic_name": topic_name,
                        "frame_id": frame_id,
                    }
                ],
            ),
            Node(
                package="force_sensor_yl",
                executable="force_sensor_yl_monitor",
                name="force_sensor_yl_monitor",
                output="screen",
                parameters=[
                    {
                        "topic_name": topic_name,
                        "window_seconds": ParameterValue(
                            window_seconds, value_type=float
                        ),
                        "print_rate_hz": ParameterValue(
                            print_rate_hz, value_type=float
                        ),
                        "plot_rate_hz": ParameterValue(
                            plot_rate_hz, value_type=float
                        ),
                        "output_dir": output_dir,
                        "save_enabled": True,
                    }
                ],
            ),
        ]
    )
