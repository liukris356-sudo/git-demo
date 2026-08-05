import logging
import threading
import time
from collections import deque
from typing import List, Optional, Tuple

from force_sensor_yl.protocol import SRIFrameParser


logger = logging.getLogger("SRIForceSensor")
Wrench = Tuple[float, float, float, float, float, float]


class SRIForceSensor:
    def __init__(self):
        self.connected = False
        self._closed = False
        self._lock = threading.RLock()
        self.ser = None
        self.zero_offsets = [0.0] * 6
        self.use_software_tare = True
        self._parser = SRIFrameParser()
        self._frames = deque()

    @property
    def checksum_errors(self) -> int:
        return self._parser.checksum_errors

    def connect(
        self,
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        timeout: float = 1.0,
    ) -> bool:
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
                    timeout=timeout,
                )
                self.ser.reset_input_buffer()

                if not self._wait_for_stream(timeout=1.0):
                    raise RuntimeError("未收到 CRC 校验有效的 M3815CA2 RS485 数据帧")

                self.connected = True
                logger.info("M3815CA2 RS485 已连接: %s, %d baud", port, baud_rate)
                return True
            except Exception as exc:
                logger.error("连接或识别传感器失败: %s", exc)
                self._close_serial()
                return False

    def _wait_for_stream(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._read_available_frames()
            if self._frames:
                return True
            time.sleep(0.001)
        return False

    def _read_available_frames(self):
        if self.ser is None or not self.ser.is_open:
            return
        waiting = self.ser.in_waiting
        if waiting > 0:
            self._frames.extend(self._parser.feed(self.ser.read(waiting)))

    def read_available(self, raw_only: bool = False) -> List[Wrench]:
        with self._lock:
            if not self.connected or self._closed:
                return []
            try:
                self._read_available_frames()
                values = []
                while self._frames:
                    frame_values = self._frames.popleft().values
                    if raw_only or not self.use_software_tare:
                        values.append(frame_values)
                    else:
                        values.append(
                            tuple(
                                value - offset
                                for value, offset in zip(
                                    frame_values, self.zero_offsets
                                )
                            )
                        )
                return values
            except Exception as exc:
                logger.warning("读取传感器数据失败: %s", exc)
                return []

    def get_force(self, raw_only: bool = False) -> Optional[Wrench]:
        with self._lock:
            if not self.connected or self._closed:
                return None
            try:
                if not self._frames:
                    self._read_available_frames()
                if not self._frames:
                    return None

                values = self._frames.popleft().values
                if raw_only or not self.use_software_tare:
                    return values
                return tuple(
                    value - offset
                    for value, offset in zip(values, self.zero_offsets)
                )
            except Exception as exc:
                logger.warning("读取传感器数据失败: %s", exc)
                return None

    def clear_zero(self, samples: int = 100, timeout: float = 3.0) -> bool:
        with self._lock:
            if not self.connected or self._closed:
                return False

            collected = []
            deadline = time.monotonic() + timeout
            self._frames.clear()
            self._parser.reset()
            self.ser.reset_input_buffer()
            while len(collected) < samples and time.monotonic() < deadline:
                values = self.get_force(raw_only=True)
                if values is None:
                    time.sleep(0.001)
                    continue
                collected.append(values)

            if len(collected) < 5:
                logger.warning("软件清零失败，仅收到 %d 帧有效数据", len(collected))
                return False

            self.zero_offsets = [
                sum(values[axis] for values in collected) / len(collected)
                for axis in range(6)
            ]
            self.use_software_tare = True
            logger.info(
                "软件清零成功 (%d 帧)，N/Nm 基线: %s",
                len(collected),
                [round(value, 6) for value in self.zero_offsets],
            )
            return True

    def _close_serial(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.connected = False
        self._closed = True

    def disconnect(self):
        with self._lock:
            self._close_serial()
            logger.info("M3815CA2 RS485 已断开")
