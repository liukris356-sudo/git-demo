import argparse
import time

from force_sensor_yl.driver import SRIForceSensor


def main():
    parser = argparse.ArgumentParser(
        description="M3815CA2 六轴力传感器实时数据"
    )
    parser.add_argument("--port", default="/dev/ttyUSB0", help="RS485 串口设备")
    parser.add_argument("--baud", type=int, default=115200, help="串口波特率")
    args = parser.parse_args()

    sensor = SRIForceSensor()
    print(f"正在连接 M3815CA2 RS485 ({args.port}:{args.baud})...")
    if not sensor.connect(args.port, args.baud):
        raise SystemExit("连接失败，请检查串口路径、权限和物理连接")

    try:
        if sensor.clear_zero():
            print("软件清零/去皮成功")
        else:
            sensor.use_software_tare = False
            print("软件清零失败，将继续读取未去皮数据")

        print("实时输出 Fx/Fy/Fz (N) 与 Mx/My/Mz (Nm)，按 Ctrl+C 停止")
        while True:
            available = sensor.read_available()
            if not available:
                time.sleep(0.001)
                continue
            for fx, fy, fz, mx, my, mz in available:
                print(
                    f"Fx={fx:9.3f} N  Fy={fy:9.3f} N  Fz={fz:9.3f} N  "
                    f"Mx={mx:9.5f} Nm  My={my:9.5f} Nm  Mz={mz:9.5f} Nm",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        sensor.disconnect()


if __name__ == "__main__":
    main()
