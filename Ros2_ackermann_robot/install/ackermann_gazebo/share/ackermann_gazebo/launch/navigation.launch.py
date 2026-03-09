import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_nav2_dir = get_package_share_directory('nav2_bringup')
    #package_name = "/home/karthik/Ros2_ackermann_robot/src/ackermann_gazebo"

    pkg_ackermann_bringup ="/home/karthik/Ros2_ackermann_robot/src/ackermann_gazebo"

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    autostart = LaunchConfiguration('autostart', default='True')

    nav2_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2_dir, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'map': os.path.join( pkg_ackermann_bringup, 'maps', 'map.yaml'),
            'params_file': os.path.join( pkg_ackermann_bringup, 'config', 'nav2_params.yaml'),
            'package_path':  pkg_ackermann_bringup, 
        }.items()
    )
    
    amcl_node = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[os.path.join(pkg_ackermann_bringup, 'config', 'amcl.yaml')],
    )

    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{'yaml_filename': os.path.join(pkg_ackermann_bringup, 'maps', 'my_map_1.yaml')}],
    )

    ld = LaunchDescription()

    ld.add_action(nav2_launch_cmd)
    #ld.add_action(amcl_node)
    #ld.add_action(map_server_node)
    #ld.add_action(static_transform_publisher_node)

    return ld