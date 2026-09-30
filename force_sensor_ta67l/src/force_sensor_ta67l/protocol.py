"""TA67L six-channel continuous serial protocol.

Frame layout (38 bytes):
    AA 55 | FF | length:u16-le | 10 | 6 * int32-le | 6 * uint8 | crc16-le

The vendor document calls the checksum simply ``CRC``.  Its Modbus section
uses CRC-16/MODBUS, so that algorithm is the default.  ``modbus_body`` and
``none`` are provided as bring-up options if captured hardware frames show a
different checksum coverage.  Never use ``none`` for normal operation.
"""

from dataclasses import dataclass
import struct
from typing import List, Optional, Tuple


FRAME_HEADER = b"\xaa\x55"
FRAME_ADDRESS = 0xFF
FRAME_COMMAND = 0x10
CHANNEL_COUNT = 6
FRAME_SIZE = 38
CRC_MODES = ("modbus", "modbus_body", "auto", "none")

RawValues = Tuple[int, int, int, int, int, int]
Wrench = Tuple[float, float, float, float, float, float]
Statuses = Tuple[int, int, int, int, int, int]


@dataclass(frozen=True)
class TA67LFrame:
    raw_values: RawValues
    values: Wrench
    statuses: Statuses
    crc_mode: str


def crc16_modbus(data: bytes) -> int:
    """Return standard CRC-16/MODBUS (poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _matched_crc_mode(frame: bytes, mode: str) -> Optional[str]:
    if mode not in CRC_MODES:
        raise ValueError(f"unsupported CRC mode: {mode}")
    if mode == "none":
        return "none"

    expected = int.from_bytes(frame[-2:], byteorder="little", signed=False)
    candidates = []
    if mode in ("modbus", "auto"):
        candidates.append(("modbus", frame[:-2]))
    if mode in ("modbus_body", "auto"):
        candidates.append(("modbus_body", frame[2:-2]))

    for candidate, payload in candidates:
        if crc16_modbus(payload) == expected:
            return candidate
    return None


def decode_frame(
    frame: bytes,
    force_counts_per_n: float = 1000.0,
    torque_counts_per_nm: float = 1000.0,
    crc_mode: str = "auto",
) -> TA67LFrame:
    if len(frame) != FRAME_SIZE:
        raise ValueError(f"TA67L frame must contain {FRAME_SIZE} bytes")
    if frame[:2] != FRAME_HEADER:
        raise ValueError("invalid TA67L frame header")
    if frame[2] != FRAME_ADDRESS:
        raise ValueError(f"unexpected TA67L address: 0x{frame[2]:02X}")
    reported_length = int.from_bytes(frame[3:5], "little")
    if reported_length != FRAME_SIZE:
        raise ValueError(
            f"unexpected TA67L frame length {reported_length}, expected {FRAME_SIZE}"
        )
    if frame[5] != FRAME_COMMAND:
        raise ValueError(f"unexpected TA67L command: 0x{frame[5]:02X}")
    if force_counts_per_n <= 0.0 or torque_counts_per_nm <= 0.0:
        raise ValueError("channel scale factors must be positive")

    matched_mode = _matched_crc_mode(frame, crc_mode)
    if matched_mode is None:
        raise ValueError("TA67L CRC check failed")

    raw_values = struct.unpack_from("<6i", frame, 6)
    statuses = tuple(frame[30:36])
    values = tuple(
        raw / scale
        for raw, scale in zip(
            raw_values,
            (
                force_counts_per_n,
                force_counts_per_n,
                force_counts_per_n,
                torque_counts_per_nm,
                torque_counts_per_nm,
                torque_counts_per_nm,
            ),
        )
    )
    return TA67LFrame(raw_values, values, statuses, matched_mode)


class TA67LFrameParser:
    """Incremental parser with byte-stream resynchronization."""

    def __init__(
        self,
        force_counts_per_n: float = 1000.0,
        torque_counts_per_nm: float = 1000.0,
        crc_mode: str = "auto",
    ):
        if crc_mode not in CRC_MODES:
            raise ValueError(f"unsupported CRC mode: {crc_mode}")
        self.force_counts_per_n = float(force_counts_per_n)
        self.torque_counts_per_nm = float(torque_counts_per_nm)
        self.crc_mode = crc_mode
        self._buffer = bytearray()
        self.crc_errors = 0
        self.format_errors = 0
        self.discarded_bytes = 0
        self.last_crc_mode: Optional[str] = None

    def reset(self) -> None:
        self._buffer.clear()
        self.crc_errors = 0
        self.format_errors = 0
        self.discarded_bytes = 0
        self.last_crc_mode = None

    def feed(self, data: bytes) -> List[TA67LFrame]:
        self._buffer.extend(data)
        frames: List[TA67LFrame] = []

        while True:
            header_index = self._buffer.find(FRAME_HEADER)
            if header_index < 0:
                if self._buffer[-1:] == FRAME_HEADER[:1]:
                    self.discarded_bytes += max(0, len(self._buffer) - 1)
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self.discarded_bytes += len(self._buffer)
                    self._buffer.clear()
                break

            if header_index:
                self.discarded_bytes += header_index
                del self._buffer[:header_index]

            if len(self._buffer) < 5:
                break

            reported_length = int.from_bytes(self._buffer[3:5], "little")
            if reported_length != FRAME_SIZE:
                self.format_errors += 1
                self.discarded_bytes += 1
                del self._buffer[0]
                continue

            if len(self._buffer) < FRAME_SIZE:
                break

            candidate = bytes(self._buffer[:FRAME_SIZE])
            try:
                parsed = decode_frame(
                    candidate,
                    force_counts_per_n=self.force_counts_per_n,
                    torque_counts_per_nm=self.torque_counts_per_nm,
                    crc_mode=self.crc_mode,
                )
            except ValueError as exc:
                if "CRC" in str(exc):
                    self.crc_errors += 1
                else:
                    self.format_errors += 1
                self.discarded_bytes += 1
                del self._buffer[0]
                continue

            frames.append(parsed)
            self.last_crc_mode = parsed.crc_mode
            del self._buffer[:FRAME_SIZE]

        return frames
