import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Path Setup
    pkg_nav2_dir = get_package_share_directory('nav2_bringup')
    pkg_ackermann_bringup = get_package_share_directory("ackermann_hardware")
 
    # 2. Launch Configurations
    autostart = LaunchConfiguration('autostart', default='True')

    # 3. Include Nav2 Bringup
    # NOTE: bringup_launch.py usually includes amcl and map_server already.
    nav2_launch_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2_dir, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'False', # Ensure this is a string
            'autostart': autostart,
            'map': os.path.join(pkg_ackermann_bringup, 'map', 'robotics_lab_2804.yaml'),
            'params_file': os.path.join(pkg_ackermann_bringup, 'config', 'nav2_params.yaml'),
            'use_composition': 'True',
            'use_respawn': 'False',
        }.items()
    )

    # 4. Create Launch Description and add actions
    ld = LaunchDescription()
    ld.add_action(nav2_launch_cmd)

    return ld