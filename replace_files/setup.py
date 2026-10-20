from pathlib import Path
from setuptools import setup

package_name = 'lesson_urdf'
data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
]
for directory in ('launch', 'urdf', 'world', 'rviz', 'meshes', 'textures', 'config'):
    for path in sorted(Path(directory).rglob('*')):
        if path.is_file():
            data_files.append(('share/' + package_name + '/' + path.parent.as_posix(),
                               [path.as_posix()]))
if Path('model.config').is_file():
    data_files.append(('share/' + package_name, ['model.config']))

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ros-industrial',
    maintainer_email='maintainer@example.com',
    description='Robot description package',
    license='TODO',
    entry_points={'console_scripts': []},
)
