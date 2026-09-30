"""TA67L six-channel Modbus RTU polling protocol."""

import struct
from typing import Tuple

from force_sensor_ta67l.protocol import TA67LFrame, crc16_modbus


MODBUS_FUNCTION_READ_HOLDING = 0x03
FIRST_VALUE_REGISTER = 0x0000
VALUE_AND_STATUS_REGISTERS = 3
CHANNEL_ADDRESSES = (1, 2, 3, 4, 5, 6)


class ModbusProtocolError(RuntimeError):
    pass


def build_read_request(address: int) -> bytes:
    if address not in CHANNEL_ADDRESSES:
        raise ValueError(f"invalid TA67L channel address: {address}")
    body = bytes(
        (
            address,
            MODBUS_FUNCTION_READ_HOLDING,
            0x00,
            FIRST_VALUE_REGISTER,
            0x00,
            VALUE_AND_STATUS_REGISTERS,
        )
    )
    return body + crc16_modbus(body).to_bytes(2, "little")


def decode_word_swapped_int32(data: bytes) -> int:
    """Decode documented 3412 order: 12 34 56 78 -> 0x56781234."""
    if len(data) != 4:
        raise ValueError("expected four value bytes")
    return struct.unpack(">i", data[2:4] + data[0:2])[0]


def decode_read_response(response: bytes, expected_address: int) -> Tuple[int, int]:
    if len(response) == 5 and response[1] & 0x80:
        expected_crc = int.from_bytes(response[-2:], "little")
        if crc16_modbus(response[:-2]) != expected_crc:
            raise ModbusProtocolError("CRC error in Modbus exception response")
        raise ModbusProtocolError(
            f"channel {expected_address} returned Modbus exception {response[2]}"
        )
    if len(response) != 11:
        raise ModbusProtocolError(
            f"channel {expected_address} returned {len(response)} bytes, expected 11"
        )
    expected_crc = int.from_bytes(response[-2:], "little")
    if crc16_modbus(response[:-2]) != expected_crc:
        raise ModbusProtocolError(f"channel {expected_address} CRC check failed")
    if response[0] != expected_address:
        raise ModbusProtocolError(
            f"channel address mismatch: got {response[0]}, expected {expected_address}"
        )
    if response[1] != MODBUS_FUNCTION_READ_HOLDING or response[2] != 6:
        raise ModbusProtocolError(
            f"channel {expected_address} returned unexpected function/length"
        )
    value = decode_word_swapped_int32(response[3:7])
    status = int.from_bytes(response[7:9], "big")
    return value, status


class TA67LModbusPoller:
    def __init__(
        self,
        force_counts_per_n: float = 1000.0,
        torque_counts_per_nm: float = 1000.0,
        retries: int = 2,
    ):
        if force_counts_per_n <= 0.0 or torque_counts_per_nm <= 0.0:
            raise ValueError("channel scale factors must be positive")
        if retries < 1:
            raise ValueError("retries must be at least one")
        self.force_counts_per_n = float(force_counts_per_n)
        self.torque_counts_per_nm = float(torque_counts_per_nm)
        self.retries = retries
        self.crc_errors = 0
        self.format_errors = 0

    def _read_channel(self, serial_port, address: int) -> Tuple[int, int]:
        request = build_read_request(address)
        last_error = "no response"
        for _ in range(self.retries):
            serial_port.reset_input_buffer()
            serial_port.write(request)
            serial_port.flush()
            response = serial_port.read(11)
            try:
                return decode_read_response(response, address)
            except ModbusProtocolError as error:
                last_error = str(error)
                if "CRC" in last_error:
                    self.crc_errors += 1
                else:
                    self.format_errors += 1
        raise ModbusProtocolError(last_error)

    def read_snapshot(self, serial_port) -> TA67LFrame:
        raw_values = []
        statuses = []
        for address in CHANNEL_ADDRESSES:
            value, status = self._read_channel(serial_port, address)
            raw_values.append(value)
            statuses.append(status & 0xFF)

        scales = (
            self.force_counts_per_n,
            self.force_counts_per_n,
            self.force_counts_per_n,
            self.torque_counts_per_nm,
            self.torque_counts_per_nm,
            self.torque_counts_per_nm,
        )
        values = tuple(value / scale for value, scale in zip(raw_values, scales))
        return TA67LFrame(
            tuple(raw_values), tuple(values), tuple(statuses), "modbus_rtu"
        )
