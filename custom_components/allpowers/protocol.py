"""ALLPOWERS BLE protocol: frame validation and decoding (no I/O).

Frame layout (notifications on FFF1)::

    A5 65 .. .. .. LL CC [LL payload bytes] XX

- ``LL`` (byte 5) is the payload length, ``CC`` (byte 6) the command.
- The frame is ``8 + LL`` bytes long and ``XX`` is the XOR of all previous bytes,
  so the XOR of a whole valid frame is zero.

Offsets come from the public ``madninjaskillz/allpowers-ble`` library and the
``dedalodaelus/esphome-allpowers-ble`` protocol notes (both MIT). Verified on a
VOLIX P300 (settings frame ``a565b1000106030201176a10100b``).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce

HEADER = b"\xa5\x65"
MIN_FRAME = 8  # header(2) + 3 unknown + length + command + checksum

CMD_STATUS = 0x01
CMD_SETTINGS = 0x03

# Starts/refreshes the periodic status notifications. Sent verbatim (no checksum).
STATUS_REQUEST = bytes.fromhex("a565b10001060100000000 00".replace(" ", ""))

WORK_MODES = {0: "mute", 1: "standard", 2: "fast"}


def xor(data: bytes) -> int:
    return reduce(lambda acc, byte: acc ^ byte, data, 0)


@dataclass(frozen=True, slots=True)
class Frame:
    command: int
    raw: bytes

    @property
    def payload(self) -> bytes:
        return self.raw[7:-1]


@dataclass(frozen=True, slots=True)
class Status:
    """Command 0x01: live telemetry."""

    dc_on: bool
    ac_on: bool
    light_on: bool
    battery: int
    input_power: int
    output_power: int
    remaining_minutes: int


@dataclass(frozen=True, slots=True)
class Settings:
    """Command 0x03: configuration snapshot."""

    eco: bool
    work_mode: str | None
    car_charger: bool
    eco_shutdown_hours: int
    hardware_version: str
    firmware_version: str
    raw_flags: int


def parse_frame(data: bytes) -> Frame | None:
    """Return the frame if ``data`` is exactly one valid frame, else None."""
    if len(data) < MIN_FRAME or data[:2] != HEADER:
        return None
    if len(data) != MIN_FRAME + data[5] or xor(data) != 0:
        return None
    return Frame(command=data[6], raw=bytes(data))


def version(byte: int) -> str:
    """Hex digits read as a decimal version: 0x12 -> '1.2'; 0x1A -> '0x1A'."""
    text = f"{byte:02X}"
    if not text.isdigit():
        return f"0x{text}"
    return f"{int(text[:-1])}.{text[-1]}"


def decode_status(frame: Frame) -> Status | None:
    raw = frame.raw
    if frame.command != CMD_STATUS or len(raw) < 16:
        return None
    battery = raw[8]
    if battery > 100:
        return None
    flags = raw[7]
    return Status(
        dc_on=bool(flags & 0x01),
        ac_on=bool(flags & 0x02),
        light_on=bool(flags & 0x10),
        battery=battery,
        input_power=int.from_bytes(raw[9:11], "big"),
        output_power=int.from_bytes(raw[11:13], "big"),
        remaining_minutes=int.from_bytes(raw[13:15], "big"),
    )


def decode_settings(frame: Frame) -> Settings | None:
    raw = frame.raw
    if frame.command != CMD_SETTINGS or len(raw) < 14:
        return None
    flags = raw[7]
    return Settings(
        eco=bool(flags & 0x01),
        work_mode=WORK_MODES.get((flags >> 1) & 0x03),
        car_charger=bool(flags & 0x10),
        eco_shutdown_hours=raw[8],
        hardware_version=version(raw[11]),
        firmware_version=version(raw[12]),
        raw_flags=flags,
    )


class FrameBuffer:
    """Reassembles frames that a BLE stack may split or join across notifications."""

    MAX_BUFFER = 512

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self._buf += data
        frames: list[Frame] = []
        while True:
            start = self._buf.find(HEADER)
            if start < 0:
                # Keep a trailing 0xA5: it may be the first half of the next header.
                self._buf = self._buf[-1:] if self._buf[-1:] == HEADER[:1] else bytearray()
                return frames
            del self._buf[:start]
            if len(self._buf) < 6:
                return frames
            size = MIN_FRAME + self._buf[5]
            if len(self._buf) < size:
                if len(self._buf) > self.MAX_BUFFER:
                    self._buf.clear()
                return frames
            frame = parse_frame(bytes(self._buf[:size]))
            if frame is None:
                del self._buf[:2]  # not a frame here: resync on the next header
                continue
            frames.append(frame)
            del self._buf[:size]
