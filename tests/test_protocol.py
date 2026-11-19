"""Frame validation and decoding."""

from __future__ import annotations

import dataclasses

import pytest

from custom_components.allpowers.protocol import (
    CMD_SETTINGS,
    CMD_STATUS,
    STATUS_REQUEST,
    FrameBuffer,
    decode_settings,
    decode_status,
    outputs_command,
    parse_frame,
    settings_command,
    version,
    xor,
)

from .helpers import P300_SETTINGS, frame, status_frame


def test_real_p300_settings_frame():
    parsed = parse_frame(P300_SETTINGS)
    assert parsed is not None and parsed.command == CMD_SETTINGS
    settings = decode_settings(parsed)
    assert settings is not None
    assert settings.eco is False
    assert settings.work_mode == "standard"
    assert settings.car_charger is False
    assert settings.eco_shutdown_hours == 1
    assert settings.hardware_version == "1.0"
    assert settings.firmware_version == "1.0"
    assert settings.charge_minutes is None  # 0x176a = 5994: not charging
    assert decode_status(parsed) is None


def test_real_p300_frames_while_charging():
    """Read from a VOLIX P300 charging at 112 W, screen showing ~11 min to full (2026-11-19)."""
    settings = decode_settings(parse_frame(bytes.fromhex("a565b1000106030201000a10107c")))
    assert settings.charge_minutes == 10
    status = decode_status(parse_frame(bytes.fromhex("a565b100010801015e00700006176a2d")))
    assert (status.battery, status.input_power, status.output_power) == (94, 112, 6)
    assert status.remaining_minutes is None


def test_status_frame():
    parsed = parse_frame(status_frame(battery=87, input_w=120, output_w=45, minutes=300, flags=0x13))
    assert parsed is not None and parsed.command == CMD_STATUS
    status = decode_status(parsed)
    assert status is not None
    assert (status.dc_on, status.ac_on, status.light_on) == (True, True, True)
    assert status.battery == 87
    assert status.input_power == 120
    assert status.output_power == 45
    assert status.remaining_minutes == 300


def test_status_large_values_are_big_endian():
    status = decode_status(parse_frame(status_frame(input_w=0x0102, output_w=600, minutes=5993, flags=0)))
    assert status.input_power == 258
    assert status.output_power == 600
    assert status.remaining_minutes == 5993
    assert (status.dc_on, status.ac_on, status.light_on) == (False, False, False)


def test_rejects_bad_frames():
    good = status_frame()
    assert parse_frame(good[:-1] + bytes([good[-1] ^ 0xFF])) is None  # checksum
    assert parse_frame(good + b"\x00") is None  # length
    assert parse_frame(b"\x00" + good[1:]) is None  # header
    assert parse_frame(good[:7]) is None  # too short
    assert decode_status(parse_frame(status_frame(battery=101))) is None
    short = parse_frame(frame(0x01, b"\x00\x10"))
    assert short is not None and decode_status(short) is None


def test_status_request_is_verbatim():
    assert STATUS_REQUEST.hex() == "a565b10001060100000000" + "00"
    assert len(STATUS_REQUEST) == 12


def test_version():
    assert version(0x10) == "1.0"
    assert version(0x12) == "1.2"
    assert version(0x23) == "2.3"
    assert version(0x1A) == "0x1A"


def test_buffer_reassembles_split_and_joined_frames():
    buf = FrameBuffer()
    a, b = status_frame(battery=50), P300_SETTINGS
    assert buf.feed(a[:5]) == []
    assert [f.raw for f in buf.feed(a[5:] + b[:9])] == [a]
    assert [f.raw for f in buf.feed(b[9:])] == [b]


def test_buffer_skips_garbage_and_corrupt_frames():
    buf = FrameBuffer()
    corrupt = bytearray(status_frame())
    corrupt[8] ^= 0x01
    good = status_frame(battery=42)
    frames = buf.feed(b"\x01\x02" + bytes(corrupt) + b"\xff" + good)
    assert [f.raw for f in frames] == [good]


def test_buffer_keeps_half_header():
    buf = FrameBuffer()
    good = status_frame()
    assert buf.feed(b"\x00\x00" + good[:1]) == []
    assert [f.raw for f in buf.feed(good[1:])] == [good]


def test_outputs_command_matches_upstream_checksum():
    """Upstream computes the checksum as 113 - SS (+4 with AC); XOR gives the same bytes."""
    for ac in (False, True):
        for dc in (False, True):
            for light in (False, True):
                frame = outputs_command(ac=ac, dc=dc, light=light)
                ss = (0x02 if ac else 0) | (0x01 if dc else 0) | (0x20 if light else 0)
                upstream = (113 - ss + (4 if ac else 0)) & 0xFF
                assert frame == bytes([0xA5, 0x65, 0x00, 0xB1, 0x01, 0x01, 0x00, ss, upstream])


def test_settings_command_read_modify_write():
    current = decode_settings(parse_frame(P300_SETTINGS))  # flags 0x02 (standard), 1 h
    frame = settings_command(current, eco=True)
    assert frame[:7] == bytes.fromhex("a56500b1010202") and frame[7] == 0x03 and frame[8] == 1
    assert xor(frame) == 0
    assert settings_command(current, work_mode="fast")[7] == 0x04
    assert settings_command(current, work_mode="mute")[7] == 0x00
    assert settings_command(current, eco_shutdown_hours=6)[7:9] == bytes([0x02, 6])
    # Unknown/reserved bits are preserved.
    odd = dataclasses.replace(current, raw_flags=0b1101_0010)
    assert settings_command(odd, eco=True)[7] == 0b1101_0011
    with pytest.raises(ValueError):
        settings_command(current, eco_shutdown_hours=3)
