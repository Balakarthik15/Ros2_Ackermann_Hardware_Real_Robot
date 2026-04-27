# 🤖 ROS 2 Ackermann Hardware — Real Robot Navigation

> **Autonomous navigation for a custom Ackermann-steered robot using ROS 2 Jazzy, Nav2, SMAC Hybrid-A\*, and MPPI on a Raspberry Pi 5.**

---

## 📋 Table of Contents

- [Overview](#overview)
- [Demo Videos](#demo-videos)
- [Hardware Platform](#hardware-platform)
- [Software Stack](#software-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [1. Launch the Robot (Hardware)](#1-launch-the-robot-hardware)
  - [2. Launch Navigation (Hardware)](#2-launch-navigation-hardware)
  - [3. Launch Simulation (Gazebo)](#3-launch-simulation-gazebo)
  - [4. Launch Navigation (Simulation)](#4-launch-navigation-simulation)
  - [5. Teleoperation (Manual Control)](#5-teleoperation-manual-control)
  - [6. Mapping Workflow](#6-mapping-workflow)
- [Package Descriptions](#package-descriptions)
- [Nav2 Configuration](#nav2-configuration)
- [Known Constraints](#known-constraints)
- [License](#license)

---

## Overview

This repository contains the full ROS 2 software stack for a custom **Ackermann-steered robot** capable of autonomous indoor navigation. The system runs on a **Raspberry Pi 5** (Ubuntu 24.04, ROS 2 Jazzy Jalisco) and integrates a VESC motor controller, RP LiDAR A1, IMU BNO055, and a complete Nav2 navigation pipeline tuned specifically for Ackermann kinematics.

The same navigation stack is available in **Gazebo Harmonic simulation** for development, testing, and algorithm tuning before hardware deployment.

Key design decisions that differ from standard Nav2 differential-drive setups:

- **SMAC Hybrid-A\*** global planner (instead of NavFn) — enforces the 0.407 m minimum turning radius in SE(2) state space with Reeds-Shepp motion primitives
- **MPPI controller** with Ackermann motion model and `AckermannConstraints` plugin — samples trajectories that respect the physical steering limit
- **Spin recovery removed** — Ackermann robots cannot rotate in place; only `BackUp` and `Wait` recoveries are used
- **EKF sensor fusion** (robot_localization) — fuses wheel odometry and IMU to eliminate yaw drift during SLAM mapping and AMCL localisation

---

## Demo Videos

### 🖥️ Simulation (Gazebo Harmonic)

> Autonomous navigation in Gazebo Harmonic with the full Nav2 stack — SMAC Hybrid-A\* global planner and MPPI controller.

[![Simulation Demo](https://img.shields.io/badge/▶_Watch-Simulation_Demo-blue?style=for-the-badge&logo=youtube)](https://drive.google.com/file/d/1kTVQZ0WgqA-dmCz_JOGqzDNLcPTHlDFI/view?usp=drive_link)

<!-- Replace YOUR_SIMULATION_VIDEO_URL_HERE with your actual YouTube/Drive link -->
<!-- To embed a YouTube thumbnail, use:
[![Simulation Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
-->

---

### 🤖 Real Robot (Raspberry Pi 5 + VESC)

> Autonomous navigation on the physical Ackermann robot in the robotics laboratory using the pre-built `robotics_lab` map.

[![Real Robot Demo](https://img.shields.io/badge/▶_Watch-Real_Robot_Demo-red?style=for-the-badge&logo=youtube)](YOUR_REAL_ROBOT_VIDEO_URL_HERE)

<!-- Replace YOUR_REAL_ROBOT_VIDEO_URL_HERE with your actual YouTube/Drive link -->
<!-- To embed a YouTube thumbnail, use:
[![Real Robot Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
-->

---

## Hardware Platform

| Component | Specification |
|-----------|--------------|
| Compute | Raspberry Pi 5 (4 GB RAM) |
| OS | Ubuntu 24.04 LTS |
| ROS Distribution | ROS 2 Jazzy Jalisco |
| Motor Controller | VESC 6 (open-source ESC) |
| LiDAR | RP LiDAR A1 (360°, single-layer) |
| IMU | BNO055 |
| Steering | Ackermann (servo-driven front axle) |
| Wheelbase | 0.285 m |
| Track Width | 0.280 m |
| Wheel Radius | 0.055 m |
| Body Dimensions | 460 × 210 × 110 mm |
| Total Mass | ~1.58 kg |
| Max Linear Velocity | 0.20 m/s |
| Max Steering Angle | 35° |
| Minimum Turning Radius | **0.407 m** (= wheelbase / tan(35°)) |
| Min Linear Velocity | ~0.193 m/s (ERPM floor constraint) |

> ⚠️ The robot has a **hard minimum velocity** of ~0.193 m/s due to the VESC ERPM threshold. Nav2 parameters are tuned accordingly — commands below this threshold are zeroed out by the velocity smoother's deadband.

---

## Software Stack

```
Sensor Input (LiDAR, IMU, VESC)
        │
        ▼
vesc_to_odom  ──► /odom
        │
        ▼
robot_localization (EKF)  ──► /odometry/filtered
        │
        ▼
slam_toolbox  ──► /map           AMCL  ──► /amcl_pose
        │                              │
        └──────────────────────────────┘
                        │
                        ▼
              BT Navigator Server
             (NavigateToPose BT)
              /         \
    Planner Server    Controller Server
   SMAC Hybrid-A*        MPPI
  (global path)    (local trajectory)
              \         /
           Velocity Smoother
                  │
                  ▼
         ackermann_to_vesc
                  │
          VESC Motor + Servo
```

| Layer | Node / Package | Topic |
|-------|---------------|-------|
| Sensor | RP LiDAR driver | `/scan` |
| Sensor | IMU BNO055 | `/imu/data` |
| Sensor | VESC driver | `/sensors/core` |
| Odometry | `vesc_to_odom` (custom) | `/odom` |
| Fusion | `robot_localization` EKF | `/odometry/filtered` |
| Mapping | `slam_toolbox` | `/map` |
| Localisation | Nav2 AMCL | `/amcl_pose` |
| Global Planner | Nav2 SMAC Hybrid-A\* | `/plan` |
| Local Controller | Nav2 MPPI | `/cmd_vel` |
| Smoother | `nav2_velocity_smoother` | `/cmd_vel` |
| Translator | `ackermann_to_vesc` (custom) | `/commands/motor/speed` |

---

## Repository Structure

```
Ros2_Ackermann_Hardware_Real_Robot/
├── src/
│   ├── ackermann_description/       # URDF / xacro robot model
│   │   └── urdf/
│   │       ├── robot.xacro
│   │       └── vehicle.urdf.xacro
│   │
│   ├── ackermann_gazebo/            # Gazebo Harmonic simulation
│   │   ├── config/
│   │   │   ├── nav2_params.yaml         # Simulation Nav2 params
│   │   │   ├── mapper_params_online_async.yaml
│   │   │   ├── robot_params.yaml
│   │   │   ├── ros_gz_bridge.yaml       # ROS↔Gazebo topic bridge
│   │   │   └── rviz_gazebo.rviz
│   │   ├── launch/
│   │   │   ├── robot_gazebo.launch.py   # Gazebo simulation bringup
│   │   │   └── navigation.launch.py     # Nav2 for simulation
│   │   ├── maps/
│   │   │   ├── map.pgm
│   │   │   ├── map.yaml
│   │   │   └── map.posegraph
│   │   ├── urdf/
│   │   │   └── robot_gazebo.xacro       # Gazebo-specific URDF (with plugins)
│   │   └── worlds/
│   │       └── lab.sdf                  # Simulation world
│   │
│   ├── ackermann_hardware/          # Core hardware package
│   │   ├── ackermann_hardware/
│   │   │   ├── ackermann_to_vesc.py     # cmd_vel → VESC ERPM + servo
│   │   │   ├── vesc_to_odom.py          # VESC ERPM → /odom
│   │   │   └── joint_states.py          # Steering joint state publisher
│   │   ├── config/
│   │   │   ├── nav2_params.yaml         # Hardware Nav2 params (fully tuned)
│   │   │   ├── ekf.yaml                 # EKF sensor fusion config
│   │   │   ├── bno055_params_i2c.yaml   # IMU driver config
│   │   │   ├── mapper_params_online_async.yaml
│   │   │   └── rviz_config.rviz
│   │   ├── launch/
│   │   │   ├── robot.launch.py          # Full hardware bringup
│   │   │   ├── navigation.launch.py     # Nav2 stack for hardware
│   │   │   └── rplidar.launch.py        # LiDAR standalone launch
│   │   └── map/
│   │       ├── robotics_lab.pgm         # Production lab map
│   │       ├── robotics_lab.yaml
│   │       ├── Test_map.pgm
│   │       └── Test_map.yaml
│   │
│   ├── ackermann_teleop/            # Keyboard / joystick teleoperation
│   │   ├── ackermann_teleop/
│   │   │   └── keyboard_teleop.py
│   │   └── config/
│   │       └── joystick.yaml
│   │
│   ├── bno055/                      # IMU BNO055 driver (submodule)
│   ├── nav2_config/                 # Nav2 behaviour tree XML files
│   └── vesc/                        # VESC driver (submodule)
│
├── ekf.yaml                         # EKF config (root-level copy)
├── mapper_params_online_async.yaml  # SLAM Toolbox config
└── README.md
```

---

## Prerequisites

- **OS:** Ubuntu 24.04 LTS on Raspberry Pi 5 (hardware) or development PC (simulation)
- **ROS 2:** [Jazzy Jalisco](https://docs.ros.org/en/jazzy/Installation.html) (full desktop or base)
- **Nav2:** `sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup`
- **robot_localization:** `sudo apt install ros-jazzy-robot-localization`
- **slam_toolbox:** `sudo apt install ros-jazzy-slam-toolbox`
- **RP LiDAR ROS 2:** `sudo apt install ros-jazzy-rplidar-ros`
- **Gazebo Harmonic** *(simulation only)*: `sudo apt install ros-jazzy-ros-gz`
- **ros_gz_bridge** *(simulation only)*: `sudo apt install ros-jazzy-ros-gz-bridge`
- **VESC submodule:** included via `vesc/` submodule
- **BNO055 submodule:** included via `bno055/` submodule

> 💡 **Note:** This stack targets **ROS 2 Jazzy** specifically because the Raspberry Pi 5 does not support Ubuntu 22.04 (required by Humble). Do **not** attempt to run this on Humble without significant changes.

---

## Installation

```bash
# 1. Create workspace
mkdir -p ~/robot_ws/src && cd ~/robot_ws/src

# 2. Clone with submodules
git clone --recurse-submodules https://github.com/Balakarthik15/Ros2_Ackermann_Hardware_Real_Robot.git

# 3. Install dependencies
cd ~/robot_ws
rosdep install --from-paths src --ignore-src -r -y

# 4. Build
colcon build --symlink-install

# 5. Source
source install/setup.bash
```

---

## Usage

### 1. Launch the Robot (Hardware)

Starts all hardware drivers, sensors, and EKF fusion:

```bash
ros2 launch ackermann_hardware robot.launch.py
```

| Node | Role |
|------|------|
| `robot_state_publisher` | Publishes URDF TF tree |
| `vesc_driver` | VESC motor controller interface |
| `ackermann_to_vesc` | Converts `/cmd_vel` → VESC ERPM + servo position |
| `joint_state_publisher` | Publishes wheel and steering joint states |
| `vesc_to_odom` | Computes `/odom` from VESC encoder + steering |
| `rplidar_node` | RP LiDAR A1 → `/scan` |
| `bno055_node` | IMU → `/imu/data` |
| `ekf_node` | EKF fusion → `/odometry/filtered` |

> Make sure VESC, LiDAR, and IMU are connected before launching. Check USB device ports in the launch file if using different assignments.

---

### 2. Launch Navigation (Hardware)

Requires the robot hardware to be running first (Step 1):

```bash
ros2 launch ackermann_hardware navigation.launch.py
```

Brings up the full Nav2 stack:
- `nav2_map_server` — serves `robotics_lab.yaml` static map
- `nav2_amcl` — particle filter localisation
- `nav2_controller_server` — MPPI local trajectory controller
- `nav2_planner_server` — SMAC Hybrid-A\* global planner
- `nav2_behavior_server` — BackUp and Wait recovery behaviours
- `nav2_bt_navigator` — Behaviour Tree execution (NavigateToPose)
- `nav2_velocity_smoother` — acceleration-limited `/cmd_vel` output
- `nav2_lifecycle_manager` — manages lifecycle of all Nav2 nodes

**Setting a navigation goal:**

```bash
# Via RViz2 — use the "Nav2 Goal" button in the toolbar
rviz2

# Or via CLI
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.5, z: 0.0}, orientation: {w: 1.0}}}}"
```

> ⚠️ Always set the **2D Pose Estimate** in RViz before sending a navigation goal. AMCL needs an initial pose to publish the `map → odom` transform.

---

### 3. Launch Simulation (Gazebo)

Starts the Gazebo Harmonic simulation with the robot and lab world:

```bash
ros2 launch ackermann_gazebo robot_gazebo.launch.py
```

This brings up:
- Gazebo Harmonic with `lab.sdf` world
- Robot model with Ackermann drive, LiDAR, and IMU plugins loaded via `robot_gazebo.xacro`
- `ros_gz_bridge` — bridges Gazebo topics to ROS 2 (`/scan`, `/imu/data`, `/odom`, `/cmd_vel`)
- `robot_state_publisher` — publishes TF from URDF

> For simulation, the `ros_gz_bridge.yaml` maps the Gazebo sensor topics to the same ROS 2 topic names as the hardware — no changes to the Nav2 config are needed.

---

### 4. Launch Navigation (Simulation)

Requires the simulation to be running first (Step 3):

```bash
ros2 launch ackermann_gazebo navigation.launch.py
```

Uses the simulation-specific `ackermann_gazebo/config/nav2_params.yaml` and the pre-built simulation map. The Nav2 stack is identical to the hardware version — SMAC Hybrid-A\* + MPPI with the same Ackermann constraints.

**Full simulation workflow:**

```bash
# Terminal 1 — Launch Gazebo
ros2 launch ackermann_gazebo robot_gazebo.launch.py

# Terminal 2 — Launch Nav2
ros2 launch ackermann_gazebo navigation.launch.py

# Terminal 3 — Open RViz
rviz2 -d src/ackermann_gazebo/config/rviz_gazebo.rviz
```

Then use the **2D Pose Estimate** to initialise AMCL, and the **Nav2 Goal** button to send navigation goals.

---

### 5. Teleoperation (Manual Control)

```bash
ros2 launch ackermann_teleop teleop.launch.py
```

Keyboard controls publish `geometry_msgs/Twist` on `/cmd_vel`. Works with both hardware and simulation. Useful for initial system checks, manual map building, and recovery.

> Minimum safe speed: ~0.193 m/s due to ERPM floor. Commands below this will not produce motion on the real robot.

---

### 6. Mapping Workflow

Build a new map using SLAM Toolbox and teleop:

```bash
# Terminal 1 — Hardware bringup
ros2 launch ackermann_hardware robot.launch.py

# Terminal 2 — SLAM Toolbox (online async)
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:=src/ackermann_hardware/config/mapper_params_online_async.yaml

# Terminal 3 — Teleop to drive and build map
ros2 launch ackermann_teleop teleop.launch.py

# Terminal 4 — Save map when satisfied
ros2 run nav2_map_server map_saver_cli -f ~/robot_ws/src/ackermann_hardware/map/robotics_lab
```

> Drive slowly and steadily. The minimum safe mapping speed is ~0.193 m/s. Make full loops to enable SLAM loop closure.

---

## Package Descriptions

### `ackermann_description`
URDF and xacro robot model. All link dimensions were measured manually from the physical robot. Inertia tensors are calculated analytically from solid primitive geometry. Used by `robot_state_publisher` for TF broadcasting in both hardware and simulation.

### `ackermann_gazebo`
Gazebo Harmonic simulation environment paired with ROS 2 Jazzy. Contains:
- **`lab.sdf`** — simulation world matching the physical robotics lab layout
- **`robot_gazebo.xacro`** — Gazebo-specific URDF with Ackermann drive, LiDAR, and IMU plugins
- **`ros_gz_bridge.yaml`** — bidirectional topic bridge between Gazebo and ROS 2
- **`navigation.launch.py`** — Nav2 stack configured for simulation (uses Gazebo clock, `use_sim_time: true`)
- **`nav2_params.yaml`** — simulation Nav2 params (same Ackermann constraints as hardware)

### `ackermann_hardware`
The core hardware package. Contains:
- **`ackermann_to_vesc.py`** — converts `geometry_msgs/TwistStamped` (`/cmd_vel`) into VESC ERPM commands and servo position commands using the Ackermann kinematic equations
- **`vesc_to_odom.py`** — converts VESC ERPM telemetry and servo position into `nav_msgs/Odometry` on `/odom`. Integrates `dyaw = vx × tan(δ) / wheelbase × dt`
- **`joint_states.py`** — publishes steering and wheel joint states for TF and RViz visualisation
- **`nav2_params.yaml`** — fully tuned Nav2 parameter file for Ackermann kinematics
- **`ekf.yaml`** — EKF configuration fusing `/odom` and `/imu/data` into `/odometry/filtered`
- **Launch files** — `robot.launch.py` and `navigation.launch.py`

### `ackermann_teleop`
Keyboard teleoperation adapted for Ackermann steering. Publishes `geometry_msgs/Twist` on `/cmd_vel`.

### `bno055` *(submodule)*
ROS 2 driver for the Bosch BNO055 IMU. Publishes `sensor_msgs/Imu` on `/imu/data`. Used by the EKF node for angular velocity fusion to reduce yaw drift.

### `nav2_config`
Nav2 behaviour tree XML files. The `NavigateToPose` behaviour tree is the standard Nav2 tree with the **Spin recovery removed** — Spin is physically impossible on an Ackermann platform.

### `vesc` *(submodule)*
Open-source VESC ROS 2 driver. Provides the low-level serial interface to the VESC 6 motor controller and publishes motor telemetry topics used by `vesc_to_odom`.

---

## Nav2 Configuration

All Nav2 parameters are in `ackermann_hardware/config/nav2_params.yaml` (hardware) and `ackermann_gazebo/config/nav2_params.yaml` (simulation).

Key Ackermann-specific settings:

| Parameter | Value | Reason |
|-----------|-------|--------|
| `motion_model_for_search` | `REEDS_SHEPP` | Allows forward and reverse arcs for tight spaces |
| `minimum_turning_radius` | `0.407 m` | `wheelbase / tan(35°)` — hard kinematic constraint |
| `motion_model` (MPPI) | `Ackermann` | Correct kinematic integration for non-holonomic steering |
| `wz_max` | `0.49 rad/s` | `tan(35°) × 0.20 / 0.285` — matches physical servo limit |
| `vx_min` | `0.0 m/s` | Robot cannot move slower than 0.193 m/s; reverse handled by behavior server |
| `deadband_velocity` | `[0.19, 0.0, 0.05]` | Below ERPM floor — motor stalls under this speed |
| `PathAngleCritic mode` | `2` | Correct bidirectional heading for reverse arc paths |
| `PathAlignCritic weight` | `10.0` | Reduced from 14.0 to allow MPPI to use tighter steering |
| Recovery behaviours | `BackUp`, `Wait` only | **Spin removed** — cannot rotate in place |
| `xy_goal_tolerance` | `0.15 m` | Realistic for Ackermann fine-positioning capability |
| `yaw_goal_tolerance` | `0.50 rad` | ~28° — avoids impossible terminal arc oscillation |

---

## Known Constraints

- **Minimum speed floor:** The robot cannot move slower than ~0.193 m/s. Commands below this velocity are zeroed by the velocity smoother deadband and will not produce motion.
- **No in-place rotation:** Ackermann geometry requires forward motion to change heading. Spin recovery and pure-rotation commands will not work.
- **Static map dependency:** The map must be updated if significant furniture or obstacles are moved. AMCL may delocalise if the live scan diverges significantly from the stored map.
- **Always set initial pose:** After launching navigation, always publish a **2D Pose Estimate** in RViz before sending a goal. AMCL requires this to initialise the `map → odom` transform.
- **ROS 2 Jazzy only:** Built and tested on Jazzy + Ubuntu 24.04 for Raspberry Pi 5. Not compatible with ROS 2 Humble without changes to message types and lifecycle API.

---

## License

This project is released for educational and research purposes. See `LICENSE` for details.

---

<div align="center">
  <sub>Built with ROS 2 Jazzy · Nav2 · SMAC Hybrid-A* · MPPI · Gazebo Harmonic · Raspberry Pi 5</sub>
</div>