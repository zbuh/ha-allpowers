"""Test helpers: frame builder and fake Bluetooth service infos."""

from __future__ import annotations

import time
from functools import reduce

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

P300_ADDRESS = "72:21:6F:63:48:B3"
P300_NAME = "VOLIX P300"

# Real settings notification read from a VOLIX P300 with nRF Connect (2026-11-18).
P300_SETTINGS = bytes.fromhex("a565b1000106030201176a10100b")


def frame(command: int, payload: bytes, prefix: bytes = b"\xb1\x00\x01") -> bytes:
    body = b"\xa5\x65" + prefix + bytes([len(payload), command]) + payload
    return body + bytes([reduce(lambda a, b: a ^ b, body, 0)])


def status_frame(
    *, battery: int = 87, input_w: int = 120, output_w: int = 45, minutes: int = 300, flags: int = 0x03
) -> bytes:
    payload = (
        bytes([flags, battery])
        + input_w.to_bytes(2, "big")
        + output_w.to_bytes(2, "big")
        + minutes.to_bytes(2, "big")
    )
    return frame(0x01, payload)


def service_info(
    address: str = P300_ADDRESS, name: str = P300_NAME, connectable: bool = True
) -> BluetoothServiceInfoBleak:
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={1494: b"\x08\x00JLAISDK"},
        service_data={},
        service_uuids=[],
        tx_power=-127,
        rssi=-22,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-22,
        manufacturer_data=adv.manufacturer_data,
        service_data={},
        service_uuids=[],
        source="local",
        device=BLEDevice(address, name, {}),
        advertisement=adv,
        connectable=connectable,
        time=time.monotonic(),
        tx_power=-127,
    )
