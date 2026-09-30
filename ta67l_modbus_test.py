#!/usr/bin/env /usr/bin/python3
"""Read TA67L channels 1..6 through Modbus RTU without changing settings."""

import argparse
import struct
import time
from typing import Tuple

import serial


DEFAULT_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
CHANNELS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_read_request(address: int) -> bytes:
    body = bytes((address, 0x03, 0x00, 0x00, 0x00, 0x02))
    return body + crc16_modbus(body).to_bytes(2, "little")


def decode_word_swapped_int32(data: bytes) -> int:
    """Decode vendor 3412 word order: 12 34 56 78 -> 0x56781234."""
    if len(data) != 4:
        raise ValueError("expected four data bytes")
    reordered = data[2:4] + data[0:2]
    return struct.unpack(">i", reordered)[0]


def read_channel(ser: serial.Serial, address: int, retries: int = 2) -> int:
    request = build_read_request(address)
    last_error = "no response"
    for _ in range(retries):
        ser.reset_input_buffer()
        ser.write(request)
        ser.flush()
        response = ser.read(9)
        if len(response) != 9:
            last_error = f"short response ({len(response)} bytes)"
            continue
        expected_crc = int.from_bytes(response[-2:], "little")
        if crc16_modbus(response[:-2]) != expected_crc:
            last_error = "CRC error"
            continue
        if response[0] != address:
            last_error = f"address mismatch ({response[0]})"
            continue
        if response[1] & 0x80:
            raise RuntimeError(
                f"Modbus exception from address {address}: code {response[2]}"
            )
        if response[1] != 0x03 or response[2] != 0x04:
            last_error = "unexpected function or byte count"
            continue
        return decode_word_swapped_int32(response[3:7])
    raise RuntimeError(f"address {address}: {last_error}")


def read_six_channels(ser: serial.Serial) -> Tuple[int, ...]:
    return tuple(read_channel(ser, address) for address in range(1, 7))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TA67L Modbus六通道只读测试（不写参数、不清零）"
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--rate", type=float, default=5.0, help="打印频率Hz")
    parser.add_argument("--once", action="store_true", help="只读取一组")
    parser.add_argument(
        "--scale", type=float, default=1000.0,
        help="原始计数除数，当前按1000换算N/Nm",
    )
    args = parser.parse_args()
    if args.rate <= 0.0 or args.scale <= 0.0:
        parser.error("rate和scale必须大于0")

    print(f"打开 {args.port}，{args.baud} baud，8N1 Modbus RTU")
    print("通道映射：1..6 = Fx,Fy,Fz,Mx,My,Mz；只读，不清零")
    with serial.Serial(
        args.port,
        args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.15,
    ) as ser:
        period = 1.0 / args.rate
        while True:
            started = time.monotonic()
            raw = read_six_channels(ser)
            values = tuple(value / args.scale for value in raw)
            print(
                "raw=[" + ", ".join(str(value) for value in raw) + "]  "
                f"Fx={values[0]:+.3f} N  Fy={values[1]:+.3f} N  "
                f"Fz={values[2]:+.3f} N  Mx={values[3]:+.4f} Nm  "
                f"My={values[4]:+.4f} Nm  Mz={values[5]:+.4f} Nm",
                flush=True,
            )
            if args.once:
                break
            remaining = period - (time.monotonic() - started)
            if remaining > 0.0:
                time.sleep(remaining)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止")
    except Exception as error:
        raise SystemExit(f"读取失败：{error}") from error
