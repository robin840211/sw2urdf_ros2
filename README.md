# sw2urdf_ros2

Convert a SolidWorks sw2urdf export into a ROS 2 package, with a desktop interface and command line. The generated package includes URDF, meshes, textures, RViz configuration, and launch files. SDF conversion adds a Gazebo model and a `ros_gz` launch file.

## Install

```bash
git clone https://github.com/robin840211/sw2urdf_ros2.git
cd sw2urdf_ros2
conda env create -f environment.yml
conda activate sw2urdf
```

This environment provides Python 3.12, Tk, and native SDFormat 15.3.0 bindings. Conversion runs locally; ROS 2 is needed when launching the generated package.

URDF-only conversion also works with Python 3.8+ and its standard library. The desktop interface uses Tkinter, available through the Python installer or your operating system's Tk package.

## Desktop interface

```bash
python conversion_urdf_ros_2_ros2.py
```

1. Set **Source Folder** to the SolidWorks export folder containing `urdf/` and `meshes/`. The included `test_urdf` folder is an example.
2. Set **Output Folder** to a new package folder, such as `robot_ws/src/my_robot`.
3. Set **Package Name**, or leave it empty to use the output folder name. Use lowercase letters, digits, and underscores, starting with a letter.
4. Choose **URDF File** when the source contains several models.
5. Keep **Generate SDF** selected to create a Gazebo model, or clear it for URDF-only output.
6. Click **Start Conversion**. The completed message displays the package folder.

Folder, URDF, and Python fields accept typed or pasted paths, including quoted Windows paths. **SDF Converter** defaults to `auto`, which tries native Python bindings, `gz sdf`, then `ign sdf`. Select `python` to use native bindings explicitly. **SDF Python** selects another Python installation containing the bindings; leave it empty to use the current runtime.

## Command line

Generate a ROS 2 package and SDF:

```bash
python conversion_urdf_ros_2_ros2.py test_urdf robot_ws/src/my_robot --package-name my_robot
```

Generate URDF only:

```bash
python conversion_urdf_ros_2_ros2.py test_urdf robot_ws/src/my_robot --urdf-only
```

Select a URDF and another native SDFormat environment:

```bash
python conversion_urdf_ros_2_ros2.py "path/to/export" "robot_ws/src/my_robot" --urdf robot.urdf --sdf-backend python --sdf-python "path/to/environment/python"
```

`--urdf` accepts a filename inside the source `urdf/` folder or its full path. On Windows, the Python executable is typically `path/to/environment/python.exe`.

| Option | Purpose |
| --- | --- |
| `--package-name NAME` | Set the generated ROS 2 package name |
| `--urdf FILE` | Select the source URDF |
| `--urdf-only` | Generate URDF and RViz files |
| `--sdf-backend auto\|python\|gz\|ign` | Select the SDF converter |
| `--sdf-python EXE` | Use another Python executable for native SDF conversion |

## Use the package

The output folder is a complete `ament_python` package. Put it under a ROS 2 workspace's `src/` folder, then build and source the workspace:

```bash
cd robot_ws
colcon build
source install/setup.bash
ros2 launch my_robot launch.py
```

The RViz launch uses `robot_state_publisher`, `joint_state_publisher_gui`, and `rviz2`.

For SDF output, install the `ros_gz_sim` and `ros_gz_bridge` packages for your ROS 2 distribution, then run:

```bash
ros2 launch my_robot gz_simulator_launch.py
```

The Gazebo model is stored in `urdf/robot.sdf`, with `model.config` in the package root. Mesh paths remain relative to the generated model.

## Build a desktop application

Activate the native SDFormat environment on the operating system where the application will run:

```bash
python -m pip install pyinstaller
python scripts/build.py
```

Copy the complete `dist/sw2urdf_ros2` folder to the destination computer. Open `sw2urdf_ros2.exe` on Windows or `sw2urdf_ros2` on Linux/macOS to show the interface. The executable accepts the same command-line arguments as the Python script. Use `--output PATH` to choose another distribution folder.

The application includes Tk, native SDFormat libraries, XML schemas, and conversion templates. Build separately on each target operating system and architecture.

## Video

[SW2URDF_Tool.webm](https://github.com/user-attachments/assets/d6172083-35f5-4059-8679-14d393f28a03)

## References

- [sw2urdf plugin](http://wiki.ros.org/sw_urdf_exporter)
- [lesson_urdf](https://github.com/olmerg/lesson_urdf)
- [Source of inspiration](https://zhuanlan.zhihu.com/p/465398486)
- [sw2urdf_ros2 (forked source)](https://github.com/xiaoming-sun6/sw2urdf_ros2)
