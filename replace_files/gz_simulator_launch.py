import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_nodes(context):
    share = Path(get_package_share_directory('lesson_urdf'))
    urdf = Path(LaunchConfiguration('urdf_file').perform(context))
    sdf = Path(LaunchConfiguration('sdf_file').perform(context))
    world = LaunchConfiguration('world_file').perform(context)
    description = ParameterValue(urdf.read_text(encoding='utf-8'), value_type=str)
    resources = [str(share), str(share.parent), str(share / 'urdf')]
    existing = os.environ.get('GZ_SIM_RESOURCE_PATH')
    if existing:
        resources.append(existing)
    return [
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.pathsep.join(resources)),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(Path(get_package_share_directory('ros_gz_sim')) / 'launch/gz_sim.launch.py')),
            launch_arguments={'gz_args': '-r -v 4 "' + world + '"'}.items()),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': description, 'use_sim_time': True}]),
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             parameters=[{'config_file': str(share / 'config/gz_bridge.yaml')}]),
        Node(package='ros_gz_sim', executable='create',
             arguments=['-name', 'lesson_urdf', '-file', str(sdf), '-z', '2.0']),
    ]


def generate_launch_description():
    share = Path(get_package_share_directory('lesson_urdf'))
    return LaunchDescription([
        DeclareLaunchArgument('urdf_file', default_value=str(share / 'urdf/planar_3dof.urdf')),
        DeclareLaunchArgument('sdf_file', default_value=str(share / 'urdf/robot.sdf')),
        DeclareLaunchArgument('world_file', default_value=str(share / 'world/depot.sdf')),
        OpaqueFunction(function=launch_nodes),
    ])
