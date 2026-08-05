# force_sensor_yl

宇立 SRI M3815CA2 六轴力传感器 ROS2 驱动，适用于内置采集卡的 RS485 连续上传模式。

## 功能

- 解析 `AA 55` 开头的 14 字节 RS485 数据帧
- CRC8 校验及错误帧重新同步
- 输出已解耦六轴数据 `Fx, Fy, Fz, Mx, My, Mz`
- 启动时自动采集 100 帧进行软件清零
- 支持 ROS2 发布和终端实时打印
- 支持六轴实时曲线、限速终端打印和 CSV 自动保存

| 数据 | 单位 |
| --- | --- |
| `Fx, Fy, Fz` | N |
| `Mx, My, Mz` | Nm |

## 环境与依赖

- Ubuntu 24.04 / Ubuntu 22.04
- ROS2 Jazzy / ROS2 Humble
- Python 3
- `python3-serial`
- `python3-matplotlib`（实时曲线需要）
- `python3-tk`（实时曲线窗口需要）

安装串口依赖：

```bash
sudo apt update
sudo apt install python3-serial python3-matplotlib python3-tk
```

如果当前用户没有串口权限：

```bash
sudo usermod -aG dialout "$USER"
```

重新登录后生效。

## 确认串口路径

推荐使用稳定的 `/dev/serial/by-id/` 路径，而不是可能随插拔变化的 `/dev/ttyUSB0`：

```bash
ls -l /dev/serial/by-id/
```

查看设备路径后，将串口保存为环境变量。以下示例使用当前设备的稳定路径：

```bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
```

如果设备名称不同，请将等号右侧替换为 `ls -l /dev/serial/by-id/` 查到的实际路径。

默认通信参数为 `115200 baud, 8N1`。

## 构建

在项目根目录执行：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

每次打开新终端后需要重新加载环境：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
```

## 启动方式一：ROS2 节点

首次下载源码，或项目中的 `install/` 目录不存在时，在项目根目录依次执行：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

ros2 run force_sensor_yl force_sensor_yl_node \
  --ros-args \
  -p port:="$SERIAL_PORT"
```

构建成功后，后续新终端不需要重复运行 `colcon build`，只需执行：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

ros2 run force_sensor_yl force_sensor_yl_node \
  --ros-args \
  -p port:="$SERIAL_PORT"
```

默认发布：

- 话题：`/force_sensor/force`
- 类型：`geometry_msgs/msg/WrenchStamped`
- 坐标系：`force_sensor_link`

查看数据：

```bash
ros2 topic echo /force_sensor/force
```

查看发布频率：

```bash
ros2 topic hz /force_sensor/force
```

ROS 参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `port` | `/dev/ttyUSB0` | RS485 串口设备 |
| `baud_rate` | `115200` | 串口波特率 |
| `frame_id` | `force_sensor_link` | 消息坐标系 |
| `topic_name` | `force_sensor/force` | 发布话题 |

完整参数示例：

```bash
ros2 run force_sensor_yl force_sensor_yl_node \
  --ros-args \
  -p port:="$SERIAL_PORT" \
  -p baud_rate:=115200 \
  -p frame_id:=force_sensor_link \
  -p topic_name:=force_sensor/force
```

## 启动方式二：直接流式打印

### 直接从源码运行（推荐）

该方式不需要 `colcon build`，在项目根目录执行：

```bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

PYTHONPATH=src /usr/bin/python3 -m force_sensor_yl.cli \
  --port "$SERIAL_PORT" \
  --baud 115200
```

这里固定使用 `/usr/bin/python3`，避免 Conda 环境影响 ROS2 Humble 的 Python 依赖。

### 通过 ROS2 安装入口运行

首次运行时需要先构建：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

ros2 run force_sensor_yl force_sensor_yl_stream \
  --port "$SERIAL_PORT" \
  --baud 115200
```

终端会持续显示：

```text
Fx=   -0.010 N  Fy=    0.020 N  Fz=   -0.030 N  Mx=  0.00154 Nm  My=  0.00000 Nm  Mz= -0.00154 Nm
```

按 `Ctrl+C` 停止。

## 启动方式三：实时曲线、终端打印和 CSV 自动保存

推荐使用一键启动方式，同时启动传感器驱动和实时监视器：

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export SERIAL_PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0

ros2 launch force_sensor_yl monitor.launch.py \
  port:="$SERIAL_PORT"
```

启动后会自动完成以下操作：

- 打开实时曲线窗口，上图显示 `Fx/Fy/Fz`，下图显示 `Mx/My/Mz`
- 曲线默认显示最近 10 秒数据
- 终端默认每秒打印 5 次六轴数据
- 全部收到的数据自动保存为 CSV，不受终端打印频率和曲线刷新频率影响
- CSV 默认保存到 `~/force_sensor_logs/`
- 文件名自动包含启动时间，例如 `m3815_20260803_173500.csv`

停止时在启动终端按 `Ctrl+C`，程序会刷新并关闭 CSV 文件。

常用启动参数：

```bash
ros2 launch force_sensor_yl monitor.launch.py \
  port:="$SERIAL_PORT" \
  window_seconds:=20.0 \
  print_rate_hz:=10.0 \
  plot_rate_hz:=20.0 \
  output_dir:="$HOME/force_sensor_logs"
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `window_seconds` | `10.0` | 曲线显示最近多少秒 |
| `print_rate_hz` | `5.0` | 终端每秒打印次数，设为 `0.0` 可关闭打印 |
| `plot_rate_hz` | `20.0` | 曲线每秒刷新次数 |
| `output_dir` | `~/force_sensor_logs` | CSV 保存目录 |

CSV 每行包含：系统时间、ROS 消息时间、启动后经过时间以及六轴力/力矩。单位直接写在列名中：力为 N，力矩为 Nm。

如果传感器 ROS2 节点已经单独运行，只启动监视器即可：

```bash
ros2 run force_sensor_yl force_sensor_yl_monitor
```

监视器订阅 `/force_sensor/force`，不会直接打开或占用串口。

## 使用注意事项

1. 节点或流式程序启动时会自动清零，清零期间请保持传感器静止且无外力。
2. 同一串口不能同时被 ROS2 节点和流式程序占用。
3. 传感器上电后自动连续上传数据，驱动不会发送 RS232 AT 指令。
4. 设备已在内部完成六轴解耦，驱动不会重复应用标定矩阵。
5. 当前设备实测上传频率约为 500 Hz，实际结果以 `ros2 topic hz` 为准。

## 项目结构

```text
force_sensor_yl/
├── resource/force_sensor_yl
├── src/force_sensor_yl/
│   ├── __init__.py
│   ├── cli.py
│   ├── driver.py
│   ├── node.py
│   └── protocol.py
├── .gitignore
├── LICENSE
├── package.xml
├── README.md
├── setup.cfg
└── setup.py
```

## 协议摘要

- 帧长：14 字节
- 帧头：`AA 55`
- 数据区：11 字节大端位流
- 数据宽度：Fx/Fy/Fz 各 15 bit，Mx/My/Mz 各 14 bit，另有 1 bit Reserved
- 符号格式：最高位为符号位，其余位为绝对值
- 比例：力除以 100，力矩除以 650
- 校验：数据区 CRC8，多项式 `0x8C`，初值 `0x00`

## 许可证

内部专有软件，详见 [LICENSE](LICENSE)。
