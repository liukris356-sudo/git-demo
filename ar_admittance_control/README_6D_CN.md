# AR5-R 六维导纳控制说明

本包保留原来的单轴 `ar_admittance_z_node`，另外新增两个互不冲突的程序：

- `ar_admittance_cartesian_6d_node`：六维笛卡尔导纳，输出工具坐标系下的 XYZ 和 Rx/Ry/Rz 偏移。
- `ar_admittance_joint_6d_node`：六维传感器力经过 `J(q)^T` 映射后，输出 J1～J7 的关节偏移。

二者都是“外层导纳算法 + xCoreSDK 实时位置内环”，不是直接发送裸关节力矩。默认均为 SHADOW，只计算、不连接机器人。

## 1. 控制关系

笛卡尔空间使用：

`M * x_ddot + D * x_dot + K * x = W_external`

其中 `x=[dx,dy,dz,dRx,dRy,dRz]`，偏移叠加在程序启动时捕获的工具位姿上。

关节空间先计算：

`tau_external = J(q)^T * W_external`

再对七个关节分别计算：

`Iq * q_ddot + Dq * q_dot + Kq * q_offset = tau_external`

## 2. 必须先确认的硬件参数

ACTIVE 前必须完成以下事项：

1. 六维传感器刚性安装在机器人末端；桌面上独立放置时只能使用 SHADOW。
2. 控制器内 TCP、工具质量、质心和惯量设置正确。
3. 笛卡尔程序填写 `tool_to_sensor_translation_m` 和 `tool_to_sensor_rpy_rad`。
4. 关节程序填写 `flange_to_sensor_translation_m` 和 `flange_to_sensor_rpy_rad`。
5. 在 SHADOW 中逐轴施力/施矩，确认 Fx/Fy/Fz/Mx/My/Mz 的方向和符号。
6. 传感器的值必须已经是 N 和 Nm。若驱动输出的是原始计数，禁止 ACTIVE。

安装变换的定义是“传感器原点在受控坐标系中的位姿”。RPY 使用 `Rz(yaw)*Ry(pitch)*Rx(roll)`。平移不能忽略，因为程序使用 `tau = R*tau_sensor + p×F` 修正力臂产生的力矩。

当前程序会在起始姿态做静态去零。若工具重力没有被传感器驱动补偿，改变机器人姿态后重力分量也会变化；因此生产使用前必须增加工具重力补偿，当前版本只适合起始姿态附近的小范围验证。

## 3. Ubuntu 编译

假设：

- ROS 2 Jazzy：`/opt/ros/jazzy`
- 工作空间：`~/admittance_ws`
- 包源码：`~/projects/git-demo-admittance`
- xCoreSDK：`~/projects/AR5-R-flexible-assembly`

```bash
cd ~/admittance_ws
source /opt/ros/jazzy/setup.bash

colcon build \
  --symlink-install \
  --base-paths ~/projects/git-demo-admittance \
  --packages-select force_sensor_yl ar_admittance_control \
  --cmake-clean-cache \
  --cmake-args \
  -DXCORE_SDK_ROOT=$HOME/projects/AR5-R-flexible-assembly \
  -DCMAKE_BUILD_TYPE=Release

source ~/admittance_ws/install/setup.bash
ros2 pkg executables ar_admittance_control
```

最后一条应列出三个程序，包括两个新的 `*_6d_node`。

## 4. 先运行传感器和 SHADOW

终端 1：

```bash
source /opt/ros/jazzy/setup.bash
source ~/admittance_ws/install/setup.bash
ros2 run force_sensor_yl force_sensor_yl_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p baud_rate:=115200 \
  -p topic_name:=/m3815/wrench_raw \
  -p frame_id:=force_sensor_link
```

终端 2 检查频率和一帧数据：

```bash
source /opt/ros/jazzy/setup.bash
source ~/admittance_ws/install/setup.bash
ros2 topic hz /m3815/wrench_raw
ros2 topic echo /m3815/wrench_raw --once
```

终端 2 运行笛卡尔 SHADOW：

```bash
PARAMS=$(ros2 pkg prefix --share ar_admittance_control)/config/admittance_cartesian_6d.yaml
ros2 run ar_admittance_control ar_admittance_cartesian_6d_node --ros-args \
  --params-file "$PARAMS" \
  -p duration_s:=30.0
```

运行关节程序的传感器/变换 SHADOW：

```bash
PARAMS=$(ros2 pkg prefix --share ar_admittance_control)/config/admittance_joint_6d.yaml
ros2 run ar_admittance_control ar_admittance_joint_6d_node --ros-args \
  --params-file "$PARAMS" \
  -p duration_s:=30.0
```

去零的两秒内不能触碰传感器。SHADOW 超过力/力矩上限也会退出，这是正常保护。

## 5. 单方向低风险实机调试

不要第一次就开启六个方向。先同时修改 `enabled_axes`（允许产生哪些笛卡尔偏移）和 `enabled_wrench_axes`（允许哪些传感器分量进入算法），例如只测 Fx→工具 X：

```yaml
enabled_axes: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
enabled_wrench_axes: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

先验证工具 X，再依次验证 Y、Z、Rx、Ry、Rz。平移方向应当是“向哪个方向推，机器人向哪个方向让开”；旋转也必须同向。反向时优先修正安装旋转，确认只是传感器电气极性问题后才改 `wrench_sign`。

实机笛卡尔命令：

```bash
PARAMS=$(ros2 pkg prefix --share ar_admittance_control)/config/admittance_cartesian_6d.yaml
ros2 run ar_admittance_control ar_admittance_cartesian_6d_node --ros-args \
  --params-file "$PARAMS" \
  -p active_control:=true \
  -p sensor_mounted_to_robot:=true \
  -p duration_s:=15.0
```

按提示输入 `ARM_CARTESIAN_6D`。关节版命令相同，只替换参数文件和程序名，确认文字为 `ARM_JOINT_6D`。

任何时刻按 Ctrl+C 都会要求控制循环结束并断电。运行任一 ACTIVE 时，不能同时运行厂家 HMI 的运动任务、`rokae_ros2` 实机控制器、另一个导纳节点或另一个 xCoreSDK 控制程序。

## 6. 与 OMPL/MoveIt 结合

OMPL 只负责无碰撞几何路径，导纳负责接触柔顺。不要让 MoveIt 的实机控制器和 xCoreSDK 导纳节点同时占用机器人。

推荐的数据流：

1. xCoreSDK 状态桥发布真实 `/joint_states`。
2. MoveIt `move_group` 使用 OMPL 规划，但设置 `allow_trajectory_execution=false`，不加载真实 `rokae_hardware_interface`。
3. 自定义规划客户端取得 `moveit_msgs/msg/RobotTrajectory`，不能从 RViz 的 `/display_planned_path` 直接执行。
4. 自定义 xCoreSDK 执行器检查关节名、起点误差、软限位、速度和加速度，再把轨迹插值到 1 ms。
5. 每周期平衡点由 `q_eq(t)=q_ompl(t)+q_admittance(t)` 组成；若使用笛卡尔导纳，则把轨迹点正解成 TCP 平衡位姿后再叠加六维柔顺偏移。
6. 接触力或跟踪误差增大时暂停轨迹时间；不能继续按墙上时钟推进轨迹，否则参考点会甩开机器人。

插拔装配应分阶段：

- OMPL：当前位置到插孔上方的预装配位姿，仅做无接触接近。
- 笛卡尔导纳：接触、搜索、对准和插入阶段。通常 XY/Rx/Ry 柔顺，Z 方向做限速进给或小期望力。
- 完成检测：插入深度、轴向力、横向力和力矩同时满足阈值后停止。
- OMPL：退出接触后再规划撤离。

关节导纳适合验证整机柔顺或绕开奇异姿态，不适合作为插孔方向和装配力的主要表达；插拔任务优先使用笛卡尔导纳。

在现有 MoveIt 配置里，先只在 RViz 的 fake hardware 中验证 OMPL。真实执行前必须确认 MoveIt 的 W4C1C5 模型与实机 W4C6C11 的几何、关节零位、限位和末端安装完全一致，否则禁止下发轨迹。
