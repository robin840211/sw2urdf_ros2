from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_nodes(context):
    urdf = Path(LaunchConfiguration('urdf_file').perform(context))
    description = ParameterValue(urdf.read_text(encoding='utf-8'), value_type=str)
    return [
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': description}]),
        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui',
             condition=IfCondition(LaunchConfiguration('use_joint_state_pub'))),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', LaunchConfiguration('rviz_config_file')],
             condition=IfCondition(LaunchConfiguration('use_rviz'))),
    ]


def generate_launch_description():
    share = Path(get_package_share_directory('lesson_urdf'))
    return LaunchDescription([
        DeclareLaunchArgument('urdf_file', default_value=str(share / 'urdf/planar_3dof.urdf')),
        DeclareLaunchArgument('rviz_config_file', default_value=str(share / 'rviz/view.rviz')),
        DeclareLaunchArgument('use_joint_state_pub', default_value='true'),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        OpaqueFunction(function=launch_nodes),
    ])
