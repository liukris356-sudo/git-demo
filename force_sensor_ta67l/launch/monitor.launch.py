from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    port = LaunchConfiguration("port")
    serial_mode = LaunchConfiguration("serial_mode")
    baud_rate = LaunchConfiguration("baud_rate")
    poll_rate_hz = LaunchConfiguration("poll_rate_hz")
    topic_name = LaunchConfiguration("topic_name")
    status_topic_name = LaunchConfiguration("status_topic_name")
    frame_id = LaunchConfiguration("frame_id")
    crc_mode = LaunchConfiguration("crc_mode")
    connect_timeout_s = LaunchConfiguration("connect_timeout_s")
    tare_on_start = LaunchConfiguration("tare_on_start")
    tare_samples = LaunchConfiguration("tare_samples")
    force_counts_per_n = LaunchConfiguration("force_counts_per_n")
    torque_counts_per_nm = LaunchConfiguration("torque_counts_per_nm")
    window_seconds = LaunchConfiguration("window_seconds")
    print_rate_hz = LaunchConfiguration("print_rate_hz")
    plot_rate_hz = LaunchConfiguration("plot_rate_hz")
    display_sample_rate_hz = LaunchConfiguration("display_sample_rate_hz")
    display_cutoff_hz = LaunchConfiguration("display_cutoff_hz")
    dominant_threshold_n = LaunchConfiguration("dominant_threshold_n")
    output_dir = LaunchConfiguration("output_dir")

    sensor_node = Node(
        package="force_sensor_ta67l",
        executable="force_sensor_ta67l_node",
        name="force_sensor_ta67l_node",
        output="screen",
        parameters=[
            {
                "port": port,
                "serial_mode": serial_mode,
                "baud_rate": ParameterValue(baud_rate, value_type=int),
                "poll_rate_hz": ParameterValue(poll_rate_hz, value_type=float),
                "topic_name": topic_name,
                "status_topic_name": status_topic_name,
                "frame_id": frame_id,
                "crc_mode": crc_mode,
                "connect_timeout_s": ParameterValue(
                    connect_timeout_s, value_type=float
                ),
                "tare_on_start": ParameterValue(tare_on_start, value_type=bool),
                "tare_samples": ParameterValue(tare_samples, value_type=int),
                "force_counts_per_n": ParameterValue(
                    force_counts_per_n, value_type=float
                ),
                "torque_counts_per_nm": ParameterValue(
                    torque_counts_per_nm, value_type=float
                ),
            }
        ],
    )
    monitor_node = Node(
        package="force_sensor_ta67l",
        executable="force_sensor_ta67l_monitor",
        name="force_sensor_ta67l_monitor",
        output="screen",
        parameters=[
            {
                "topic_name": topic_name,
                "window_seconds": ParameterValue(window_seconds, value_type=float),
                "print_rate_hz": ParameterValue(print_rate_hz, value_type=float),
                "plot_rate_hz": ParameterValue(plot_rate_hz, value_type=float),
                "display_sample_rate_hz": ParameterValue(
                    display_sample_rate_hz, value_type=float
                ),
                "display_cutoff_hz": ParameterValue(
                    display_cutoff_hz, value_type=float
                ),
                "dominant_threshold_n": ParameterValue(
                    dominant_threshold_n, value_type=float
                ),
                "output_dir": output_dir,
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("port", default_value="/dev/ttyUSB0"),
            DeclareLaunchArgument("serial_mode", default_value="modbus"),
            DeclareLaunchArgument("baud_rate", default_value="0"),
            DeclareLaunchArgument("poll_rate_hz", default_value="25.0"),
            DeclareLaunchArgument("topic_name", default_value="/ta67l/wrench_raw"),
            DeclareLaunchArgument(
                "status_topic_name", default_value="/ta67l/channel_status"
            ),
            DeclareLaunchArgument("frame_id", default_value="force_sensor_link"),
            DeclareLaunchArgument("crc_mode", default_value="auto"),
            DeclareLaunchArgument("connect_timeout_s", default_value="35.0"),
            DeclareLaunchArgument("tare_on_start", default_value="true"),
            DeclareLaunchArgument("tare_samples", default_value="100"),
            DeclareLaunchArgument("force_counts_per_n", default_value="1000.0"),
            DeclareLaunchArgument(
                "torque_counts_per_nm", default_value="1000.0"
            ),
            DeclareLaunchArgument("window_seconds", default_value="10.0"),
            DeclareLaunchArgument("print_rate_hz", default_value="5.0"),
            DeclareLaunchArgument("plot_rate_hz", default_value="20.0"),
            DeclareLaunchArgument(
                "display_sample_rate_hz", default_value="25.0"
            ),
            DeclareLaunchArgument("display_cutoff_hz", default_value="8.0"),
            DeclareLaunchArgument(
                "dominant_threshold_n", default_value="0.10"
            ),
            DeclareLaunchArgument(
                "output_dir", default_value="~/force_sensor_logs"
            ),
            sensor_node,
            monitor_node,
            RegisterEventHandler(
                OnProcessExit(
                    target_action=sensor_node,
                    on_exit=[
                        EmitEvent(event=Shutdown(reason="TA67L driver stopped"))
                    ],
                )
            ),
        ]
    )
