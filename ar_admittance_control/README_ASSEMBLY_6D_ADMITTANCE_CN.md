# 手机主板装配：阶段感知六维笛卡尔导纳

## 这个节点做什么

`ar_assembly_cartesian_6d_admittance_node` 在原手机主板装配轨迹上叠加
六维笛卡尔导纳修正：

`名义轨迹 + 人工注入的六维误差 + 导纳纠偏量 = 最终指令位姿`

六维顺序固定为 `[X, Y, Z, Rx, Ry, Rz]`。平移单位为 m，转动单位为
rad；力为 N，力矩为 N·m。姿态修正用旋转向量左乘到工件坐标系中的
名义姿态，不直接把欧拉角相加。

## 为什么首版没有同时放开六个方向

求解器、传感器变换、限幅和日志都是六维的，但配置文件使用分阶段轴掩码。
第一版仅在接触阶段开放 X、Y、Rx、Ry；Z 和 Rz 默认关闭，因为现有三组
成功基线只建立了 Fx 随轨迹进度变化的包络，尚未建立完整的
Fy/Fz/Mx/My/Mz 阶段包络。直接开放 Z 可能改变正常下压力，直接开放 Rz
可能使主板在狭小空间扫碰。

## Ubuntu 编译

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
ros2 pkg executables ar_admittance_control | grep 6d
```

## 操作顺序

终端 1，启动力传感器和曲线：

```bash
export AR_FORCE_PORT=/dev/ttyUSB1  # 按 ls -l /dev/ttyUSB* 的结果修改
~/assembly.sh force
```

终端 2，先做只读 SHADOW：

```bash
~/assembly.sh 6d-admit-shadow
```

依次只施加一个方向的力/力矩，确认输出中的 Fx、Fy、Fz、Mx、My、Mz
名称、正负号和实际动作方向一致。SHADOW 不会给机械臂上电或发送运动指令。

实机运行前必须满足：机械臂已回到当前点文件的 P_SAFE；RobotAssist 中
TCP、负载、工具和工件坐标系正确；没有其他 xCoreSDK/rokae_ros2 控制节点；
工作空间清空且急停可达。

```bash
~/assembly.sh safe
~/assembly.sh 6d-admit-run
```

程序要求输入：

```text
ARM_PHASE_6D_ADMIT
```

## 第一次运行看什么

- 先用模拟件，速度和修正上限不要提高。
- 确认横向受力时修正方向是离开障碍，而不是继续顶入。
- 检查最终日志中的六维修正、`W_ref`、`W_excess`、阶段和停止原因。
- 出现硬力/力矩、TCP 跟踪、传感器超时或修正饱和时，程序会停止并下电。
- 结束后保存六维力 CSV，并与无偏移基线、X 单轴版本比较。

## 如何逐步开放 Z/Rz

不要一次修改多个轴。先收集至少 5～10 次成功装配的完整六维数据，建立
每个阶段的 Fz 和 Mz 正常中心/上下界。随后只在一个阶段把对应掩码从
`0.0` 改为 `1.0`，用模拟件验证方向、限幅和退出逻辑。未经这一步，不要把
所有 `phase_*_axes` 直接改成六个 `1.0`。
