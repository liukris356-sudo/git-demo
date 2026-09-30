# XB7 点位记录与执行工具

这是从原 AR5 点位记录思路迁移出来的独立 XB7 工具，不覆盖 AR5 程序。

## 一键脚本（推荐）

工程根目录新增了可执行脚本：

```text
/home/liu/projects/git-demo-admittance/xb7_points.sh
```

它已经预设现场网络参数：电脑 `192.168.2.100`、XB7 `192.168.2.160`，并会
自动完成 CMake 构建。第一次打印/记录点位只需：

```bash
cd /home/liu/projects/git-demo-admittance
./xb7_points.sh record
```

脚本会自动创建带时间戳的 `xb7_records/xb7_points_*.csv`。进入记录器后输入
`CURRENT` 只打印当前位置，输入 `P_SAFE` 等点名则打印并保存。其他命令：

```bash
./xb7_points.sh config
./xb7_points.sh plan xb7_records/POINTS.csv
./xb7_points.sh go xb7_records/POINTS.csv P_SAFE
./xb7_points.sh run xb7_records/POINTS.csv 5 2
```

工具/工件默认是 `g_tool_1 / g_wobj_0`。若现场名称不同，可在单条命令中覆盖：

```bash
XB7_TOOL=g_tool_1 XB7_WOBJ=g_wobj_0 ./xb7_points.sh record
```

## 程序

- `xb7_point_recorder`：只读连接 XB7，打印并记录命名点位，不上电、不运动。
- `xb7_point_player PLAN`：离线检查 CSV，不连接机器人。
- `xb7_point_player GO`：低速 `MoveAbsJ` 移动到一个记录点。
- `xb7_point_player RUN`：要求 XB7 已位于第一个点，先执行 `checkPath`，再按 CSV
顺序执行精确停止的 `MoveL`。

XB7 是六轴工业机器人，记录格式不包含 AR5 的第七轴和 elbow。因此原来的 AR5
CSV 不能直接用于 XB7，必须重新示教记录。

## SDK

代码使用：

```cpp
rokae::StandardRobot
```

并使用 SDK 推荐的非实时运动指令：

```cpp
rokae::MoveAbsJCommand
rokae::MoveLCommand
```

`/home/liu/下载/xCoreSDK-CPP-main (2)` 中确认有 XB7h-R707 示例和头文件，
但当前目录缺少 `lib/Linux/...` 预编译库，因此不能单独链接。构建时应指定一套
包含匹配头文件和二进制库的完整 xCoreSDK 0.7.1 目录。

当前机器可用于编译验证的完整目录是：

```text
/home/liu/下载/xCoreSDK-v0.7.1.ar_6
```

正式连接 XB7 前，应向厂家确认这套库的授权和运行时支持包含 XB7；如厂家另行提供
XB7 完整 SDK，应优先改用厂家提供的目录。

## 构建

```bash
cd /home/liu/projects/git-demo-admittance
cmake -S xb7_point_control -B xb7_point_control/build \
  -DXCORE_SDK_ROOT="/home/liu/下载/xCoreSDK-v0.7.1.ar_6" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build xb7_point_control/build -j
```

输出程序：

```text
xb7_point_control/build/xb7_point_recorder
xb7_point_control/build/xb7_point_player
```

## 1. 记录并打印 XB7 点位

先在 RobotAssist 中配置并核对工具、工件坐标系。运行：

```bash
mkdir -p /home/liu/projects/git-demo-admittance/xb7_records

./xb7_point_control/build/xb7_point_recorder \
  192.168.0.160 \
  192.168.0.180 \
  g_tool_1 \
  g_wobj_0 \
  xb7_records/xb7_points_01.csv
```

请将两个 IP 和工具/工件名称替换为现场实际值。记录器不会上电或发送运动命令。

交互命令：

```text
CURRENT   只打印当前位置，不保存
P_SAFE    记录名为 P_SAFE 的点
P_PRE     记录名为 P_PRE 的点
LIST      查看已记录名称
UNDO      删除最后一个点
QUIT      退出
```

每次记录前：

1. 使用 RobotAssist 低速 Jog 将 XB7 移到目标位置；
2. 松开 Jog 并等待机器人完全停止；
3. 回到终端输入点名；
4. 程序比较 300 ms 前后的 TCP 和关节角，运动未稳定时拒绝记录；
5. 接受后立即原子写入 CSV。

CSV 同时保存：

- 当前工具 TCP 相对所选工件坐标系的六维位姿；
- 法兰相对机器人基座的六维位姿；
- XB7 的 J1～J6。

## 2. 离线检查点位

该命令不连接机器人，也不会运动：

```bash
./xb7_point_control/build/xb7_point_player \
  PLAN xb7_records/xb7_points_01.csv
```

## 3. 低速移动到单个记录点

推荐先移动到安全点：

```bash
./xb7_point_control/build/xb7_point_player \
  GO \
  192.168.0.160 \
  192.168.0.180 \
  xb7_records/xb7_points_01.csv \
  P_SAFE
```

默认行为：

- 关节速度比例 2%；
- 当前点与目标点任一关节相差超过 30°时拒绝运动；
- 要求控制器软限位已启用；
- 打印当前与目标关节角；
- 必须手工输入 `ARM_XB7_GO` 才会上电运动；
- 到位或异常后下电并切回手动模式。

可选指定速度比例和最大起始关节差：

```bash
./xb7_point_control/build/xb7_point_player \
  GO ROBOT_IP LOCAL_IP POINTS.csv P_SAFE 0.01 20
```

这里 `0.01` 是 1% 关节速度，`20` 是最大允许起始关节差 20°。

## 4. 按记录顺序执行点位

先使用 `GO` 到达 CSV 的第一个点，然后执行：

```bash
./xb7_point_control/build/xb7_point_player \
  RUN \
  192.168.0.160 \
  192.168.0.180 \
  xb7_records/xb7_points_01.csv \
  5 \
  2
```

最后两个参数分别为：

- 线速度：5 mm/s；
- 旋转速度：2 deg/s。

`RUN` 在运动前会：

1. 核对连接机器人和记录文件中的机型；
2. 使用 CSV 中记录的工具和工件坐标系；
3. 确认当前 TCP、姿态和关节角接近第一个点；
4. 检查所有记录关节角都在软限位内并留出 3°余量；
5. 调用控制器 `checkPath` 验证整条笛卡尔路径；
6. 显示计划并要求输入 `ARM_XB7_RUN`；
7. 使用 `MoveL`、`zone=0` 逐点精确停止执行。

## 安全顺序

1. 先运行 `PLAN`；
2. 首次只记录高于工装、无碰撞风险的测试点；
3. 使用 `GO` 到第一个安全点；
4. 在低速、空载、急停可触及的情况下运行 `RUN`；
5. 不得同时运行 RobotAssist 运动任务、其他 xCoreSDK 控制程序或 ROS 控制器；
6. 新机械臂必须重新示教，禁止把 AR5 七轴 CSV 转换后直接用于 XB7。

