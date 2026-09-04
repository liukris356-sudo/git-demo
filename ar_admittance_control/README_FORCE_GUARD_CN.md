# 装配轨迹 30 N 力保护（阶段 2）

本节点把原来的 xCoreSDK 装配轨迹和外置 M3815 六维力数据放在同一进程中。
它只做保护，不做导纳，也不会在受力后自动向前纠偏。

## 两个话题

- 输入：`/m3815/wrench_raw`，类型 `geometry_msgs/msg/WrenchStamped`
- 输出：`/assembly/force_guard/status`，类型 `std_msgs/msg/String`

默认保护参数：滤波合力达到 27 N 并持续 30 ms 时暂停；原始合力达到
30 N、合力矩达到 1.25 Nm，或输入话题超过 50 ms 没有新数据时停止。
任何保护触发都会调用 `stop()`，随后调用 `moveReset()` 清空剩余轨迹；
本阶段不会自动恢复运动。

## 编译

```bash
cd ~/admittance_ws
source /opt/ros/jazzy/setup.bash

colcon build \
  --symlink-install \
  --base-paths ~/projects/git-demo-admittance/ar_admittance_control \
  --packages-select ar_admittance_control \
  --cmake-clean-cache \
  --cmake-args \
  -DXCORE_SDK_ROOT=$HOME/projects/AR5-R-flexible-assembly \
  -DCMAKE_BUILD_TYPE=Release

source ~/admittance_ws/install/setup.bash
ros2 pkg executables ar_admittance_control
```

应能看到 `ar_assembly_force_guard_node`。

## 运行前检查

```bash
ls -l /dev/ttyUSB*
ros2 node list
```

必须停止所有可能控制机械臂的 xCoreSDK、rokae_ros2、MoveIt 执行节点和旧导纳
ACTIVE 节点。传感器可视化程序可以同时运行，因为它只订阅数据。

## 推荐运行方式

终端 1 启动传感器：

```bash
source /opt/ros/jazzy/setup.bash
source ~/admittance_ws/install/setup.bash

ros2 run force_sensor_yl force_sensor_yl_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p topic_name:=/m3815/wrench_raw
```

终端 2 先检查两个话题：

```bash
source /opt/ros/jazzy/setup.bash
source ~/admittance_ws/install/setup.bash

ros2 topic hz /m3815/wrench_raw
ros2 topic echo /m3815/wrench_raw --once
```

终端 3 先做只读路径检查（不会运动）：

```bash
source /opt/ros/jazzy/setup.bash
source ~/admittance_ws/install/setup.bash

PARAMS=$(ros2 pkg prefix --share ar_admittance_control)/config/assembly_force_guard.yaml
POINTS=$HOME/projects/AR5-R-control-demos/records/assembly_points_leader_01.csv

ros2 run ar_admittance_control ar_assembly_force_guard_node \
  192.168.2.160 192.168.2.100 \
  g_tool_1 g_wobj_0 "$POINTS" \
  WIDE_PLAN 1.0 1.0 \
  --ros-args --params-file "$PARAMS"
```

实机一体运行（当前位置回 P_SAFE，再执行宽轨迹）：

```bash
ros2 run ar_admittance_control ar_assembly_force_guard_node \
  192.168.2.160 192.168.2.100 \
  g_tool_1 g_wobj_0 "$POINTS" \
  WIDE_AUTO 1.0 1.0 \
  --ros-args --params-file "$PARAMS"
```

看到提示后必须完整输入：

```text
ARM_GO_SAFE_AND_WIDE_RUN
```

另一个终端观察保护状态：

```bash
ros2 topic echo /assembly/force_guard/status
```

第一次实机保护测试不要装真主板。可以用手在低速运动时逐渐施力，验证约 27 N
时程序停止且不会继续执行剩余轨迹。硬件急停始终优先于软件保护。

## 调整阈值

编辑安装前的源码配置：

```bash
gedit ~/projects/git-demo-admittance/ar_admittance_control/config/assembly_force_guard.yaml
```

本阶段不要把 30 N 后的自动前插写进去。下一阶段应单独验证工件坐标系前插方向，
再实现“停止下降、每次前插 0.05--0.10 mm、总量不超过 0.30 mm、受力不下降就退出”。
