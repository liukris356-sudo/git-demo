# force_sensor_ta67l

TA67L 六通道测量模块的独立 ROS 2 串口驱动。此目录为新增包，不修改原有
`force_sensor_yl`（M3815CA2）驱动。

## 协议依据

依据《TA67L串口输出方式-带状态》及实机验证，本驱动支持两种模式：

- 默认 `modbus`：`115200 baud, 8N1`，依次轮询地址1～6；实机约29组/s。
- 可选 `continuous`：`460800 baud, 8N1`，接收 `AA 55` 连续帧。
- 通道顺序：`Fx, Fy, Fz, Mx, My, Mz`
- 力换算：`counts / 1000 = N`
- 力矩换算：`counts / 1000 = N·m`

Modbus模式一次读取每个地址的实时值和状态寄存器，已经在当前TA67L实机上验证。
连续模式的完整帧按文档定义为38字节：

```text
AA 55 | FF | 26 00 | 10 | 6×Int32 | 6×Status | CRC16
```

连续模式文档没有明确CRC覆盖范围，程序使用 `auto` 尝试完整报文和去掉
`AA 55` 帧头后的CRC-16/MODBUS。`crc_mode`仅影响连续模式；默认Modbus轮询
使用标准Modbus CRC。`none`只允许短时排障，不能用于正常控制。

## 接线

```text
传感器 RS485A ── USB-RS485 A/D+
传感器 RS485B ── USB-RS485 B/D-
传感器电源      ── 按铭牌和厂家线序单独供电
USB-RS485       ── 电脑 USB
```

不同厂商的 A/B 命名可能相反，必须优先采用厂家定义。不要将 A/B 接入普通
以太网口。建议使用支持 460800 baud 的隔离型 USB-RS485 转换器。

## 上电模式注意事项

当前实机默认工作在 `115200 baud` Modbus RTU模式，本驱动也默认使用该模式，
启动后会主动轮询1～6号地址，不需要等待30秒。协议另称无Modbus交互时可切换到
`460800 baud`连续输出；该模式保留为可选项，但尚未在当前实机验证成功。

## 构建

当前仓库根目录本身已经是 `force_sensor_yl` ROS 包，而新驱动位于其下方的独立
目录。`colcon` 默认发现根目录的 `package.xml` 后不会继续扫描嵌套目录，因此
**必须显式指定新包路径**：

```bash
cd /home/liu/projects/git-demo-admittance
source /opt/ros/jazzy/setup.bash
colcon build \
  --base-paths ./force_sensor_ta67l \
  --symlink-install \
  --packages-select force_sensor_ta67l
source install/setup.bash
```

如果遗漏 `--base-paths ./force_sensor_ta67l`，会出现：

```text
ignoring unknown package 'force_sensor_ta67l'
```

构建后可检查：

```bash
ros2 pkg executables force_sensor_ta67l
```

应看到 node、stream 和 monitor 三个可执行程序。

## 确认串口

```bash
ls -l /dev/serial/by-id/
```

建议使用稳定的 `/dev/serial/by-id/...` 路径。若用户没有串口权限，需要加入
`dialout` 组并重新登录。

## 先进行纯串口测试

机械臂不要上使能，传感器保持静止：

```bash
source install/setup.bash
ros2 run force_sensor_ta67l force_sensor_ta67l_stream \
  --port /dev/serial/by-id/你的转换器 \
  --mode modbus \
  --no-tare
```

终端将显示六维力和六个通道状态字节。第一次联调应依次沿各轴施加已知方向的
小载荷，核对轴顺序、正负方向和倍率。

## 启动 ROS 2 驱动

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run force_sensor_ta67l force_sensor_ta67l_node --ros-args \
  -p port:=/dev/serial/by-id/你的转换器 \
  -p serial_mode:=modbus \
  -p tare_on_start:=false
```

默认发布：

| 话题 | 类型 | 含义 |
|---|---|---|
| `/ta67l/wrench_raw` | `geometry_msgs/msg/WrenchStamped` | 软件清零后的六维力 |
| `/ta67l/channel_status` | `std_msgs/msg/UInt8MultiArray` | 六通道状态字节 |

查看话题：

```bash
ros2 topic hz /ta67l/wrench_raw
ros2 topic echo /ta67l/wrench_raw --once
ros2 topic echo /ta67l/channel_status
```

## 启动实时曲线和 CSV 记录界面

```bash
ros2 launch force_sensor_ta67l monitor.launch.py \
  port:=/dev/serial/by-id/你的转换器 \
  serial_mode:=modbus \
  tare_on_start:=true
```

监视器从新驱动订阅 `WrenchStamped`，提供实时曲线、限速终端打印、暂停显示和
按需保存 CSV。原来的 M3815CA2 监视代码已经复制到本包并改为 TA67L 名称；
原包文件未被覆盖。

## 接入现有导纳控制

现有控制配置默认订阅 `/m3815/wrench_raw`。在不修改旧配置的情况下，可让新
驱动直接使用该话题：

```bash
ros2 run force_sensor_ta67l force_sensor_ta67l_node --ros-args \
  -p port:=/dev/serial/by-id/你的转换器 \
  -p serial_mode:=modbus \
  -p topic_name:=/m3815/wrench_raw
```

也可以后续统一将控制配置改为 `/ta67l/wrench_raw`。

## ROS 参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `port` | `/dev/ttyUSB0` | USB-RS485 串口 |
| `serial_mode` | `modbus` | `modbus`轮询或`continuous`连续输出 |
| `baud_rate` | `0` | 自动：Modbus 115200，连续模式460800 |
| `poll_rate_hz` | `25.0` | Modbus目标发布频率；实测上限约29Hz |
| `frame_id` | `force_sensor_link` | 消息坐标系 |
| `topic_name` | `/ta67l/wrench_raw` | 六维力话题 |
| `status_topic_name` | `/ta67l/channel_status` | 状态字节话题 |
| `force_counts_per_n` | `1000.0` | 每 N 对应的原始计数 |
| `torque_counts_per_nm` | `1000.0` | 每 N·m 对应的原始计数 |
| `crc_mode` | `auto` | 仅连续模式：`modbus/modbus_body/auto/none` |
| `connect_timeout_s` | `35.0` | 连续模式等待数据超时；Modbus模式忽略 |
| `tare_on_start` | `true` | 启动时软件清零 |
| `tare_samples` | `100` | 软件清零采样数 |

## 安全要求

1. 首次联调只查看原始数据，不连接机械臂运动控制。
2. 清零时传感器必须静止且无外力。
3. 用已知小载荷分别验证六轴方向和倍率。
4. 检查状态字节没有断线、芯片故障、超载或清零失败。
5. 确认数据频率、丢帧和稳定性后，才允许接入 SHADOW 模式。
6. SHADOW 验证通过后，才能考虑 XB7 主动导纳控制。
