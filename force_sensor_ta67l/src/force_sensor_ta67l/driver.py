"""Serial transport for the TA67L six-channel measurement module."""

from collections import deque
from dataclasses import replace
import logging
import threading
import time
from typing import List, Optional

from force_sensor_ta67l.modbus import ModbusProtocolError, TA67LModbusPoller
from force_sensor_ta67l.protocol import TA67LFrame, TA67LFrameParser


logger = logging.getLogger("TA67LForceSensor")
SERIAL_MODES = ("modbus", "continuous")


class TA67LForceSensor:
    def __init__(
        self,
        force_counts_per_n: float = 1000.0,
        torque_counts_per_nm: float = 1000.0,
        crc_mode: str = "auto",
        serial_mode: str = "modbus",
    ):
        if serial_mode not in SERIAL_MODES:
            raise ValueError(f"unsupported serial mode: {serial_mode}")
        self.serial_mode = serial_mode
        self.connected = False
        self._closed = False
        self._lock = threading.RLock()
        self.ser = None
        self.zero_offsets = [0.0] * 6
        self.use_software_tare = True
        self._parser = TA67LFrameParser(
            force_counts_per_n=force_counts_per_n,
            torque_counts_per_nm=torque_counts_per_nm,
            crc_mode=crc_mode,
        )
        self._modbus = TA67LModbusPoller(
            force_counts_per_n=force_counts_per_n,
            torque_counts_per_nm=torque_counts_per_nm,
        )
        self._frames = deque()

    @property
    def crc_errors(self) -> int:
        if self.serial_mode == "modbus":
            return self._modbus.crc_errors
        return self._parser.crc_errors

    @property
    def format_errors(self) -> int:
        if self.serial_mode == "modbus":
            return self._modbus.format_errors
        return self._parser.format_errors

    @property
    def detected_crc_mode(self) -> Optional[str]:
        if self.serial_mode == "modbus":
            return "modbus_rtu"
        return self._parser.last_crc_mode

    def connect(
        self,
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        serial_timeout_s: float = 0.10,
        stream_timeout_s: float = 35.0,
    ) -> bool:
        """Open the port and verify the configured TA67L serial mode."""
        with self._lock:
            if self.connected:
                self.disconnect()

            try:
                import serial

                self._closed = False
                self._parser.reset()
                self._frames.clear()
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baud_rate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=serial_timeout_s,
                )
                self.ser.reset_input_buffer()

                if self.serial_mode == "modbus":
                    self._frames.append(self._modbus.read_snapshot(self.ser))
                elif not self._wait_for_stream(timeout=stream_timeout_s):
                    raise RuntimeError(
                        "未收到有效 TA67L 连续输出帧；请检查供电、A/B 接线、"
                        "460800 波特率，并在传感器上电后等待约 30 秒"
                    )

                self.connected = True
                logger.info(
                    "TA67L RS485 已连接: %s, %d baud, mode=%s, CRC=%s",
                    port,
                    baud_rate,
                    self.serial_mode,
                    self.detected_crc_mode,
                )
                return True
            except Exception as exc:
                logger.error("连接或识别 TA67L 失败: %s", exc)
                self._close_serial()
                return False

    def _wait_for_stream(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._read_continuous_frames()
            if self._frames:
                return True
            time.sleep(0.002)
        return False

    def _read_continuous_frames(self) -> None:
        if self.ser is None or not self.ser.is_open:
            return
        waiting = self.ser.in_waiting
        if waiting > 0:
            self._frames.extend(self._parser.feed(self.ser.read(waiting)))

    def _acquire_one(self) -> Optional[TA67LFrame]:
        if self.ser is None or not self.ser.is_open:
            return None
        if self.serial_mode == "modbus":
            return self._modbus.read_snapshot(self.ser)
        if not self._frames:
            self._read_continuous_frames()
        return self._frames.popleft() if self._frames else None

    def _apply_tare(self, frame: TA67LFrame, raw_only: bool) -> TA67LFrame:
        if raw_only or not self.use_software_tare:
            return frame
        corrected = tuple(
            value - offset for value, offset in zip(frame.values, self.zero_offsets)
        )
        return replace(frame, values=corrected)

    def read_available(self, raw_only: bool = False) -> List[TA67LFrame]:
        with self._lock:
            if not self.connected or self._closed:
                return []
            try:
                if self.serial_mode == "modbus":
                    frame = self._acquire_one()
                    return [] if frame is None else [self._apply_tare(frame, raw_only)]

                self._read_continuous_frames()
                frames = []
                while self._frames:
                    frames.append(self._apply_tare(self._frames.popleft(), raw_only))
                return frames
            except ModbusProtocolError as exc:
                logger.warning("TA67L Modbus轮询失败: %s", exc)
                return []
            except Exception as exc:
                logger.warning("读取 TA67L 数据失败: %s", exc)
                return []

    def get_frame(self, raw_only: bool = False) -> Optional[TA67LFrame]:
        with self._lock:
            if not self.connected or self._closed:
                return None
            try:
                frame = self._acquire_one()
                return None if frame is None else self._apply_tare(frame, raw_only)
            except Exception as exc:
                logger.warning("读取 TA67L 数据失败: %s", exc)
                return None

    def clear_zero(self, samples: int = 100, timeout: float = 6.0) -> bool:
        """Average stationary engineering-unit samples for a software tare."""
        with self._lock:
            if not self.connected or self._closed:
                return False

            collected = []
            deadline = time.monotonic() + timeout
            self._frames.clear()
            if self.ser is not None:
                self.ser.reset_input_buffer()

            while len(collected) < samples and time.monotonic() < deadline:
                frame = self.get_frame(raw_only=True)
                if frame is None:
                    time.sleep(0.001)
                    continue
                collected.append(frame.values)

            if len(collected) < 5:
                logger.warning("TA67L 软件清零失败，仅收到 %d 帧", len(collected))
                return False

            self.zero_offsets = [
                sum(values[axis] for values in collected) / len(collected)
                for axis in range(6)
            ]
            self.use_software_tare = True
            logger.info(
                "TA67L 软件清零成功 (%d 帧)，N/Nm 基线: %s",
                len(collected),
                [round(value, 6) for value in self.zero_offsets],
            )
            return True

    def _close_serial(self) -> None:
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.connected = False
        self._closed = True

    def disconnect(self) -> None:
        with self._lock:
            self._close_serial()
            logger.info("TA67L RS485 已断开")
