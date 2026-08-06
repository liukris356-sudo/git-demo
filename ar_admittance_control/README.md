# AR5-R external-force admittance validation

This ROS 2 package couples the SRI M3815CA2 driver in `force_sensor_yl` to a
ROKAE AR5-R through xCoreSDK 0.7.1.ar_6.

The default is **SHADOW mode**. It subscribes to the six-axis wrench, computes
the virtual tool-Z displacement, and publishes diagnostics without connecting
to the robot. Live motion requires both `active_control:=true` and typing the
exact terminal confirmation `ARM_ADMITTANCE_Z`.

## Why this package does not command `rokae_ros2`

The available `rokae_ros2` hardware plugin is primarily wired for joint
position trajectory control. Its Cartesian force input and external-wrench
path are not a complete admittance loop. This package therefore uses ROS 2 for
the force topic, configuration and logging, while one process owns the robot
through `rokae::ArRobot` and the xCoreSDK real-time Cartesian-position loop.

Never run a `rokae_ros2` hardware/controller launch and this package's ACTIVE
mode at the same time. Two motion owners must not connect to the robot.

## Implemented control law

The first live stage is deliberately one-dimensional:

```text
sensor Fz -> deadband -> low-pass -> M*x_ddot + D*x_dot + K*x = Fz
                                             |
                                             +-> captured tool-Z position
```

The current TCP pose and AR elbow angle are captured at arm time. Orientation
and elbow are held. Only the translation along the captured tool Z axis changes.
This is position-based outer-loop admittance, not torque control and not the
xCoreSDK Cartesian-impedance mode.

Default limits are conservative: 10 mm displacement, 10 mm/s velocity, 20 N
total force, 3 Nm total torque, 50 ms wrench timeout, 8 degree joint watchdog,
5 degree elbow watchdog and 2 degree TCP-orientation watchdog. The program
also requires enabled joint soft limits and at least a 10 degree margin.

## Coordinate requirement

This first stage assumes the sensor Z axis is physically parallel to tool Z.
If pushing along positive tool Z reports negative Fz, set `force_sign: -1.0`.
Do not use ACTIVE mode if sensor Z and tool Z are not aligned. A later 6-D
controller needs the calibrated sensor-to-tool transform and the wrench
adjoint transform; guessing that transform can make the robot move in the
wrong direction.

## Build on Ubuntu

Use the directory that contains both ROS packages as the colcon workspace
source directory. For the layout supplied with this project:

```bash
mkdir -p ~/admittance_ws/src
cp -a ~/forces_sensor_yl-main/forces_sensor_yl ~/admittance_ws/src/
cp -a ~/forces_sensor_yl-main/ar_admittance_control ~/admittance_ws/src/

# Ubuntu 24.04 normally uses ROS 2 Jazzy. If your installed distro differs,
# replace "jazzy" with its name.
source /opt/ros/jazzy/setup.bash
cd ~/admittance_ws
colcon build --symlink-install \
  --packages-select force_sensor_yl ar_admittance_control \
  --cmake-args \
  -DXCORE_SDK_ROOT=$HOME/projects/AR5-R-flexible-assembly \
  -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

Adjust `XCORE_SDK_ROOT` if the SDK is elsewhere. Its root must contain
`include/rokae/robot.h` and `lib/Linux/x86_64/libxCoreSDK.a`.

## Stage 1: sensor only

Install serial permissions once, then log out and back in:

```bash
sudo usermod -aG dialout "$USER"
```

At the final robot pose, with the final tool attached and no contact on the
sensor, start the driver. The driver performs a software tare during startup:

```bash
source ~/admittance_ws/install/setup.bash
ros2 run force_sensor_yl force_sensor_yl_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p topic_name:=/m3815/wrench_raw
```

In another terminal:

```bash
source ~/admittance_ws/install/setup.bash
ros2 topic hz /m3815/wrench_raw
ros2 topic echo /m3815/wrench_raw --once
```

At rest, values should be close to zero and stable. Never tare while touching
the sensor or while the tool is supported by an external object.

## Stage 2: SHADOW mode

The launch file starts the sensor and the controller. It is safe by default:

```bash
source ~/admittance_ws/install/setup.bash
ros2 launch ar_admittance_control admittance_z.launch.py \
  port:=/dev/ttyUSB0
```

Push sensor Z gently. The log should show `dz` with the intended sign, remain
inside 10 mm, then return smoothly toward zero after release. The robot is not
connected in this mode. Useful outputs are:

```bash
ros2 topic echo /admittance/offset_tool
ros2 topic echo /admittance/velocity_tool
```

If the sign is wrong, edit `config/admittance_z.yaml` and change only
`force_sign` between `1.0` and `-1.0`.

## Stage 3: guarded ACTIVE mode

Before this stage, verify all of the following:

- sensor Z is aligned with tool Z and SHADOW direction is correct;
- active tool, TCP, payload and robot installation settings are correct;
- all joints are over 10 degrees from configured soft limits;
- no `rokae_ros2`, RCI motion program or other xCoreSDK motion program runs;
- workspace is clear, speed is reduced and the E-stop is reachable.

For ACTIVE mode use two terminals. Do not use `ros2 launch` here because a
launched node is not guaranteed to receive interactive terminal input.

Terminal 1 starts and tares the sensor:

```bash
source ~/admittance_ws/install/setup.bash
ros2 run force_sensor_yl force_sensor_yl_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p topic_name:=/m3815/wrench_raw
```

After the tare completes, terminal 2 starts the interactive controller:

```bash
source ~/admittance_ws/install/setup.bash
PARAMS=$(ros2 pkg prefix --share ar_admittance_control)/config/admittance_z.yaml
ros2 run ar_admittance_control ar_admittance_z_node --ros-args \
  --params-file "$PARAMS" \
  -p active_control:=true
```

Read the terminal warning and type `ARM_ADMITTANCE_Z`. The program captures the
actual TCP and elbow; it does not move to a hard-coded pose, does not modify
tool/load settings, and does not set a desired contact force. Gently press only
along tool Z. Release should make the virtual spring return to the captured pose.

## Initial tuning order

Do not tune all parameters at once.

1. Keep the hard limits unchanged.
2. Use SHADOW mode to set a deadband just above stationary noise.
3. Reduce `stiffness_n_m` for more static displacement, or increase it for less.
4. Increase `damping_n_s_m` if return is oscillatory; decrease slightly if the
   response is excessively sluggish.
5. Change `virtual_mass_kg` last; a smaller value reacts faster and is riskier.

With the defaults, 10 N after deadband would mathematically request roughly
10 mm at steady state, but the explicit 10 mm limit clamps it. These values are
for identification and direction validation, not insertion production.

## Path toward plug insertion

After tool-Z validation, implement and validate these stages separately:

1. Calibrate the fixed sensor-to-tool transform.
2. Compensate tool/gripper/workpiece gravity and sensor bias versus orientation.
3. Transform all six wrench components into the tool frame.
4. Add compliant tool X/Y first, while keeping rotations fixed.
5. Add slow commanded insertion along tool Z plus a target axial force.
6. Detect contact, search, insertion depth, jamming and successful seating with
   explicit state-machine transitions.
7. Add rotational compliance only if the fixture and task require it.

A production insertion controller should therefore be a state machine, not a
single always-on six-axis admittance equation.
