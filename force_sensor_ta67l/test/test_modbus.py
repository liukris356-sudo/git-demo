import struct
import unittest

from force_sensor_ta67l.modbus import (
    ModbusProtocolError,
    TA67LModbusPoller,
    build_read_request,
    decode_read_response,
    decode_word_swapped_int32,
)
from force_sensor_ta67l.protocol import crc16_modbus


def make_response(address, value, status=0):
    unsigned = value & 0xFFFFFFFF
    big_endian = unsigned.to_bytes(4, "big")
    word_swapped = big_endian[2:4] + big_endian[0:2]
    body = bytes((address, 0x03, 0x06)) + word_swapped + status.to_bytes(2, "big")
    return body + crc16_modbus(body).to_bytes(2, "little")


class FakeSerial:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        pass

    def read(self, _size):
        return self.responses.pop(0)


class ModbusProtocolTest(unittest.TestCase):
    def test_request_matches_vendor_example(self):
        self.assertEqual(
            build_read_request(1),
            bytes.fromhex("01 03 00 00 00 03 05 cb"),
        )

    def test_word_swapped_signed_decode(self):
        self.assertEqual(decode_word_swapped_int32(bytes.fromhex("d9 7d ff ff")), -9859)
        self.assertEqual(decode_word_swapped_int32(bytes.fromhex("0e a2 00 00")), 3746)

    def test_response_value_and_status(self):
        response = make_response(3, -123456, 0x0018)
        self.assertEqual(decode_read_response(response, 3), (-123456, 0x0018))

    def test_rejects_bad_crc(self):
        response = bytearray(make_response(2, 100))
        response[-1] ^= 0xFF
        with self.assertRaisesRegex(ModbusProtocolError, "CRC"):
            decode_read_response(bytes(response), 2)

    def test_poller_combines_six_channels(self):
        raw = (-1000, 2000, -3000, 4000, -5000, 6000)
        statuses = (0, 1, 2, 3, 4, 5)
        serial_port = FakeSerial(
            [make_response(i + 1, raw[i], statuses[i]) for i in range(6)]
        )
        frame = TA67LModbusPoller().read_snapshot(serial_port)
        self.assertEqual(frame.raw_values, raw)
        self.assertEqual(frame.statuses, statuses)
        self.assertEqual(frame.values, (-1.0, 2.0, -3.0, 4.0, -5.0, 6.0))
        self.assertEqual(frame.crc_mode, "modbus_rtu")
        self.assertEqual(len(serial_port.writes), 6)


if __name__ == "__main__":
    unittest.main()
