import struct
import unittest

from force_sensor_ta67l.protocol import (
    FRAME_ADDRESS,
    FRAME_COMMAND,
    FRAME_HEADER,
    FRAME_SIZE,
    TA67LFrameParser,
    crc16_modbus,
    decode_frame,
)


def make_frame(raw_values, statuses=(0, 0, 0, 0, 0, 0), crc_body=False):
    packet = bytearray(FRAME_HEADER)
    packet.append(FRAME_ADDRESS)
    packet.extend(FRAME_SIZE.to_bytes(2, "little"))
    packet.append(FRAME_COMMAND)
    packet.extend(struct.pack("<6i", *raw_values))
    packet.extend(statuses)
    crc_data = packet[2:] if crc_body else packet
    packet.extend(crc16_modbus(bytes(crc_data)).to_bytes(2, "little"))
    return bytes(packet)


class ProtocolTest(unittest.TestCase):
    def test_known_modbus_crc(self):
        self.assertEqual(crc16_modbus(b"123456789"), 0x4B37)

    def test_decode_scales_channels_and_statuses(self):
        raw = (1000, -2000, 3500, -4000, 500, 0)
        statuses = (0x04, 0x08, 0x10, 0x20, 0x01, 0x02)
        decoded = decode_frame(make_frame(raw, statuses))

        self.assertEqual(decoded.raw_values, raw)
        self.assertEqual(decoded.statuses, statuses)
        self.assertEqual(
            decoded.values,
            (1.0, -2.0, 3.5, -4.0, 0.5, 0.0),
        )
        self.assertEqual(decoded.crc_mode, "modbus")

    def test_parser_accepts_fragmented_stream_and_noise(self):
        frame = make_frame((1, 2, 3, 4, 5, 6))
        parser = TA67LFrameParser()

        self.assertEqual(parser.feed(b"noise" + frame[:11]), [])
        decoded = parser.feed(frame[11:])

        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0].raw_values, (1, 2, 3, 4, 5, 6))
        self.assertEqual(parser.discarded_bytes, 5)

    def test_parser_recovers_after_bad_crc(self):
        bad = bytearray(make_frame((10, 20, 30, 40, 50, 60)))
        bad[10] ^= 0x80
        good = make_frame((-1, -2, -3, -4, -5, -6))
        parser = TA67LFrameParser()

        decoded = parser.feed(bytes(bad) + good)

        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0].raw_values, (-1, -2, -3, -4, -5, -6))
        self.assertEqual(parser.crc_errors, 1)

    def test_auto_mode_detects_body_crc(self):
        frame = make_frame((11, 12, 13, 14, 15, 16), crc_body=True)
        decoded = decode_frame(frame, crc_mode="auto")
        self.assertEqual(decoded.crc_mode, "modbus_body")

    def test_rejects_wrong_reported_length(self):
        frame = bytearray(make_frame((1, 2, 3, 4, 5, 6)))
        frame[3:5] = (37).to_bytes(2, "little")
        with self.assertRaisesRegex(ValueError, "frame length"):
            decode_frame(bytes(frame), crc_mode="none")


if __name__ == "__main__":
    unittest.main()
