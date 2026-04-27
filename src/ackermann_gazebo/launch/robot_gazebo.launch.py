import os
import xacro

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    package_name = "ackermann_gazebo"
    package_path = get_package_share_directory(package_name)

    robot_description_path = os.path.join(package_path, "urdf", "robot_gazebo.xacro")
    gz_bridge_params_path = os.path.join(package_path, "config", "ros_gz_bridge.yaml")

    nav2_params_file = os.path.join(package_path, "config", "nav2_params.yaml")
    map_file = os.path.join(package_path, "maps", "map.yaml")
    rviz_config_file = os.path.join(package_path, "config", "rviz_gazebo.rviz")

    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")

    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time",
        default_value="true",
        description="Use simulation clock"
    )

    declare_autostart = DeclareLaunchArgument(
        "autostart",
        default_value="true",
        description="Autostart Nav2 lifecycle nodes"
    )

    world_arg = DeclareLaunchArgument("world", default_value="lab.sdf")
    x_arg = DeclareLaunchArgument("x", default_value="0.0")
    y_arg = DeclareLaunchArgument("y", default_value="0.0")
    z_arg = DeclareLaunchArgument("z", default_value="0.2")
    yaw_arg = DeclareLaunchArgument("Y", default_value="0.0")

    world_file = os.path.join(package_path, "worlds", "lab.sdf")

    robot_description_content = ParameterValue(
        Command(["xacro ", robot_description_path]),
        value_type=str
    )

    cleanup_gz = ExecuteProcess(
        cmd=["pkill", "-9", "gz"],
        output="screen"
    )

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("ros_gz_sim"),
                "launch",
                "gz_sim.launch.py"
            )
        ),
        launch_arguments={
            "gz_args": ["-r -v 4 ", world_file],
            "on_exit_shutdown": "true",
        }.items()
    )

    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-topic", "robot_description",
            "-name", "bot_ackermann",
            "-x", LaunchConfiguration("x"),
            "-y", LaunchConfiguration("y"),
            "-z", LaunchConfiguration("z"),
            "-Y", LaunchConfiguration("Y"),
            "-allow_renaming", "false",
        ],
        output="screen",
    )

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        parameters=[{
            "robot_description": robot_description_content,
            "use_sim_time": use_sim_time,
        }],
        output="screen"
    )

    gz_bridge_node = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_bridge",
        arguments=[
            "--ros-args",
            "-p",
            f"config_file:={gz_bridge_params_path}"
        ],
        parameters=[{
            "use_sim_time": use_sim_time
        }],
        output="screen"
    )

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("nav2_bringup"),
                "launch",
                "bringup_launch.py"
            )
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "autostart": autostart,
            "map": map_file,
            "params_file": nav2_params_file,
        }.items()
    )

    delayed_nav2 = TimerAction(
        period=5.0,
        actions=[nav2_launch]
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        arguments=["-d", rviz_config_file],
        parameters=[{
            "use_sim_time": use_sim_time
        }],
        output="screen"
    )

    delayed_rviz = TimerAction(
        period=6.0,
        actions=[rviz_node]
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_autostart,
        world_arg,
        x_arg,
        y_arg,
        z_arg,
        yaw_arg,

        cleanup_gz,
        gazebo_launch,
        spawn_robot,
        robot_state_publisher_node,
        gz_bridge_node,

        delayed_nav2,
        delayed_rviz,
    ])