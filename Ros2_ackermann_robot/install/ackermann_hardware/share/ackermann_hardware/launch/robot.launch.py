from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os
import xacro


def generate_launch_description():

    # ==============================
    # Robot Description (Xacro → URDF)
    # ==============================
    description_pkg = get_package_share_directory('ackermann_description')
    xacro_file = os.path.join(
        description_pkg,
        'urdf',
        'robot.xacro'
    )

    robot_description_config = xacro.process_file(xacro_file)
    robot_description = {
        'robot_description': robot_description_config.toxml()
    }

    # ==============================
    # Robot State Publisher
    # ==============================
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description]
    )

    # ==============================
    # Ackermann → VESC Node
    # ==============================
    ackermann_node = Node(
        package='ackermann_hardware',
        executable='ackermann_to_vesc',
        name='ackermann_to_vesc',
        output='screen'
    )

    # ==============================
    # Joint State From VESC
    # ==============================
    joint_state_node = Node(
        package='ackermann_hardware',
        executable='joint_states',
        name='joint_states',
        output='screen'
    )

    # ==============================
    # Include VESC Driver Launch
    # ==============================
    vesc_pkg = get_package_share_directory('vesc')
    vesc_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(vesc_pkg, 'vesc_driver','launch', 'vesc_driver_node.launch.py')
        )
    )

    # ==============================
    # Keyboard Teleop
    # ==============================
    teleop_node = Node(
        package='ackermann_teleop',
        executable='keyboard_teleop',
        output='screen'
    )

    return LaunchDescription([
        rsp_node,
        vesc_launch,
        ackermann_node,
        joint_state_node,
    ])