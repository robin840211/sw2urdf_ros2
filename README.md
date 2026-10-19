# sw2urdf_ros2

The current solidworks sw2urdf plugin can only be used in ros1, which is obviously unfriendly to the current learning
environment.So I made this tool to convert files to ros2 for use. At this stage, the tool has only been successfully tested in rviz2.

### Table of contents

1. [Environment](#1-environment)
2. [Getting tool](#2-getting-tool)
3. [Getting started](#3-getting-started)
4. [Converting files](#4-converting-files)
5. [Running launch file](#5-running-launch-file)
6. [Video of the tool working](#6-video-of-the-tool-working)
7. [Reference](#7-reference)

### 1. Environment

- Solidworks 2019
- Ubuntu 20.04
- Ros2 foxy
- Python == 3.8

### 2. Getting tool

We download the tool from github

~~~ bash
git clone https://github.com/robin840211/sw2urdf_ros2.git
cd sw2urdf_ros2
pip3 install -r requirements.txt
~~~

### 3. Getting started

We should have an urdf folder that outputs from solidworks.Let's say the name of the folder is test_urdf(I had put this folder in the project as a demo file).

Let's create a workspace called test_urdf_tool_ws and a ROS package called test_urdf_tool

~~~ bash
mkdir test_urdf_tool_ws && mkdir test_urdf_tool_ws/src
cd test_urdf_tool_ws && colcon build
cd src && ros2 pkg create test_urdf_tool --build-type ament_python
~~~

### 4. Converting files

Run the python file in a new terminal.

```bash
cd <Path_to_tool>/sw2urdf_ros2
chmod +x conversion_urdf_ros_2_ros2.py
python3 conversion_urdf_ros_2_ros2.py
```

1. Click **Select Source Folder** and select the folder generated from SolidWorks, containing the `urdf` and `meshes` folders.
2. Click **Select Target Folder** and select the ROS2 package folder, such as `test_urdf_tool_ws/src/test_urdf_tool`.
3. Click **Start Conversion**.

Then,We go into the workspace and build the code.
~~~ bash
cd <Path_to_workspace>/test_urdf_tool_ws && colcon build && source install/setup.bash
~~~

### 5. Running launch file
Finally，We run the launch files.
~~~ bash
ros2 launch test_urdf_tool launch.py
~~~

Don't forget to change the rviz configuration
![rviz](img/rviz.png)

### 6. Video of the tool working

[SW2URDF_Tool.webm](https://github.com/user-attachments/assets/d6172083-35f5-4059-8679-14d393f28a03)

### 7. Reference
Thanks for the links

[sw2urdf plugin](http://wiki.ros.org/sw_urdf_exporter)  
[lesson_urdf](https://github.com/olmerg/lesson_urdf)  
[Source of inspiration](https://zhuanlan.zhihu.com/p/465398486)

[sw2urdf_ros2 (forked source)](https://github.com/xiaoming-sun6/sw2urdf_ros2)
