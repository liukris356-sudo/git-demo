from dataclasses import dataclass
from typing import List, Tuple


FRAME_HEADER = b"\xaa\x55"
FRAME_SIZE = 14
FORCE_SCALE = 100.0
TORQUE_SCALE = 650.0


@dataclass(frozen=True)
class SRIFrame:
    raw_values: Tuple[int, int, int, int, int, int]
    values: Tuple[float, float, float, float, float, float]


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8C if crc & 1 else 0)
    return crc


def decode_sign_magnitude(value: int, width: int) -> int:
    sign_mask = 1 << (width - 1)
    magnitude = value & (sign_mask - 1)
    return -magnitude if value & sign_mask else magnitude


def decode_payload(payload: bytes) -> SRIFrame:
    if len(payload) != 11:
        raise ValueError("SRI RS485 payload must contain 11 bytes")

    encoded = (
        (payload[0] << 7) | (payload[1] >> 1),
        ((payload[1] & 0x01) << 14) | (payload[2] << 6) | (payload[3] >> 2),
        ((payload[3] & 0x03) << 13) | (payload[4] << 5) | (payload[5] >> 3),
        ((payload[5] & 0x07) << 11) | (payload[6] << 3) | (payload[7] >> 5),
        ((payload[7] & 0x1F) << 9) | (payload[8] << 1) | (payload[9] >> 7),
        ((payload[9] & 0x7F) << 7) | (payload[10] >> 1),
    )
    raw_values = tuple(
        decode_sign_magnitude(value, width)
        for value, width in zip(encoded, (15, 15, 15, 14, 14, 14))
    )
    values = tuple(
        value / scale
        for value, scale in zip(
            raw_values,
            (
                FORCE_SCALE,
                FORCE_SCALE,
                FORCE_SCALE,
                TORQUE_SCALE,
                TORQUE_SCALE,
                TORQUE_SCALE,
            ),
        )
    )
    return SRIFrame(raw_values, values)


class SRIFrameParser:
    def __init__(self):
        self._buffer = bytearray()
        self.checksum_errors = 0

    def reset(self):
        self._buffer.clear()
        self.checksum_errors = 0

    def feed(self, data: bytes) -> List[SRIFrame]:
        self._buffer.extend(data)
        frames = []

        while True:
            header_index = self._buffer.find(FRAME_HEADER)
            if header_index < 0:
                if self._buffer[-1:] == FRAME_HEADER[:1]:
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break

            if header_index:
                del self._buffer[:header_index]

            if len(self._buffer) < FRAME_SIZE:
                break

            frame = bytes(self._buffer[:FRAME_SIZE])
            payload = frame[2:13]
            if crc8(payload) != frame[13]:
                self.checksum_errors += 1
                del self._buffer[0]
                continue

            frames.append(decode_payload(payload))
            del self._buffer[:FRAME_SIZE]

        return frames
