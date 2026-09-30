import argparse
import time

from force_sensor_ta67l.driver import SERIAL_MODES, TA67LForceSensor
from force_sensor_ta67l.protocol import CRC_MODES


def main():
    parser = argparse.ArgumentParser(description="TA67L 六维力串口实时数据")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="USB-RS485 串口")
    parser.add_argument(
        "--mode", choices=SERIAL_MODES, default="modbus",
        help="modbus=115200轮询；continuous=460800连续输出",
    )
    parser.add_argument(
        "--baud", type=int, default=0,
        help="0=按模式自动选择115200或460800",
    )
    parser.add_argument(
        "--crc-mode", choices=CRC_MODES, default="auto",
        help="仅连续模式使用；正常运行不要使用none",
    )
    parser.add_argument("--force-scale", type=float, default=1000.0)
    parser.add_argument("--torque-scale", type=float, default=1000.0)
    parser.add_argument("--connect-timeout", type=float, default=35.0)
    parser.add_argument("--no-tare", action="store_true", help="关闭启动软件清零")
    args = parser.parse_args()

    baud = args.baud or (115200 if args.mode == "modbus" else 460800)
    sensor = TA67LForceSensor(
        force_counts_per_n=args.force_scale,
        torque_counts_per_nm=args.torque_scale,
        crc_mode=args.crc_mode,
        serial_mode=args.mode,
    )
    if args.mode == "modbus":
        print(f"正在连接 TA67L Modbus ({args.port}:{baud})，轮询地址1～6……")
    else:
        print(
            f"正在连接 TA67L 连续输出 ({args.port}:{baud})。"
            "刚上电时可能需要等待约30秒……"
        )
    if not sensor.connect(
        args.port,
        baud,
        stream_timeout_s=args.connect_timeout,
    ):
        raise SystemExit("连接失败，请检查串口、供电、A/B接线和通信模式")

    try:
        if not args.no_tare:
            if sensor.clear_zero():
                print("软件清零成功")
            else:
                sensor.use_software_tare = False
                print("软件清零失败，将继续读取未去皮数据")
        else:
            sensor.use_software_tare = False

        print(
            f"mode={args.mode}，CRC={sensor.detected_crc_mode}；"
            "实时输出Fx/Fy/Fz (N)与Mx/My/Mz (Nm)，按Ctrl+C停止"
        )
        while True:
            frames = sensor.read_available()
            if not frames:
                time.sleep(0.001)
                continue
            for frame in frames:
                fx, fy, fz, mx, my, mz = frame.values
                statuses = " ".join(f"{value:02X}" for value in frame.statuses)
                print(
                    f"Fx={fx:9.3f} N  Fy={fy:9.3f} N  Fz={fz:9.3f} N  "
                    f"Mx={mx:9.5f} Nm  My={my:9.5f} Nm  Mz={mz:9.5f} Nm  "
                    f"status=[{statuses}]",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        sensor.disconnect()


if __name__ == "__main__":
    main()
