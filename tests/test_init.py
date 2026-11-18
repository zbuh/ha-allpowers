"""Setup, entities and the BLE session (with a fake GATT client)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.allpowers import device as device_module
from custom_components.allpowers.const import DOMAIN, NOTIFY_UUID, WRITE_UUID
from custom_components.allpowers.diagnostics import async_get_config_entry_diagnostics
from custom_components.allpowers.protocol import STATUS_REQUEST

from .helpers import P300_ADDRESS, P300_NAME, P300_SETTINGS, service_info, status_frame


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=P300_NAME,
        unique_id=P300_ADDRESS,
        data={CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME},
    )
    entry.add_to_hass(hass)
    return entry


def _eid(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{P300_ADDRESS}_{key}")
    assert entity_id is not None, key
    return entity_id


class FakeClient:
    """GATT client: answers each status request with one status notification."""

    def __init__(self, frames: list[bytes]) -> None:
        self.frames = frames
        self.writes: list[tuple[str, bytes]] = []
        self.handler = None
        self.disconnect = AsyncMock()

    async def start_notify(self, uuid, handler):
        assert uuid == NOTIFY_UUID
        self.handler = handler

    async def write_gatt_char(self, uuid, data, response=None):
        self.writes.append((uuid, bytes(data)))
        if self.frames:
            data = self.frames.pop(0)
            # Split the notification in two, as some BLE stacks do.
            self.handler(None, bytearray(data[:6]))
            self.handler(None, bytearray(data[6:]))


async def test_entities_follow_notifications(hass: HomeAssistant):
    entry = _entry(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    battery = _eid(hass, "sensor", "battery")
    connection = _eid(hass, "binary_sensor", "connection")
    assert hass.states.get(battery).state == STATE_UNAVAILABLE
    assert hass.states.get(connection).state == STATE_OFF

    device = entry.runtime_data
    device._set_connected(True)
    device.handle_notification(None, bytearray(P300_SETTINGS))
    device.handle_notification(None, bytearray(status_frame(battery=87, input_w=0, output_w=45, minutes=300)))
    await hass.async_block_till_done()

    assert hass.states.get(battery).state == "87"
    assert hass.states.get(_eid(hass, "sensor", "input_power")).state == "0"
    assert hass.states.get(_eid(hass, "sensor", "output_power")).state == "45"
    assert hass.states.get(_eid(hass, "sensor", "remaining_time")).state == "300"
    assert hass.states.get(_eid(hass, "sensor", "work_mode")).state == "standard"
    assert hass.states.get(_eid(hass, "binary_sensor", "ac_output")).state == STATE_ON
    assert hass.states.get(_eid(hass, "binary_sensor", "dc_output")).state == STATE_ON
    assert hass.states.get(_eid(hass, "binary_sensor", "light")).state == STATE_OFF
    assert hass.states.get(_eid(hass, "binary_sensor", "eco_mode")).state == STATE_OFF
    assert hass.states.get(connection).state == STATE_ON

    [dev] = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert (dev.manufacturer, dev.sw_version, dev.hw_version) == ("ALLPOWERS", "1.0", "1.0")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["status"]["battery"] == 87
    assert diagnostics["recent_frames"][0]["hex"] == P300_SETTINGS.hex()

    device._set_connected(False)
    await hass.async_block_till_done()
    assert hass.states.get(battery).state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_session_requests_status_and_reconnects(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(device_module, "KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(device_module, "RETRY_MIN_SECONDS", 0.01)
    entry = _entry(hass)
    client = FakeClient([P300_SETTINGS, status_frame(battery=64)])
    ble = BLEDevice(P300_ADDRESS, P300_NAME, {})
    with (
        patch.object(device_module.bluetooth, "async_ble_device_from_address", return_value=ble),
        patch.object(device_module, "establish_connection", AsyncMock(return_value=client)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        device = entry.runtime_data
        for _ in range(200):
            await asyncio.sleep(0.01)
            if device.status is not None:
                break
        await hass.async_block_till_done()
        assert device.available
        assert hass.states.get(_eid(hass, "sensor", "battery")).state == "64"
        assert client.writes[0] == (WRITE_UUID, STATUS_REQUEST)

        assert await hass.config_entries.async_unload(entry.entry_id)
    assert not device.connected
    client.disconnect.assert_awaited()


async def test_watchdog_drops_silent_session(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(device_module, "KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(device_module, "WATCHDOG_SECONDS", 0.05)
    monkeypatch.setattr(device_module, "RETRY_MIN_SECONDS", 0.01)
    entry = _entry(hass)
    silent = FakeClient([])
    connect = AsyncMock(return_value=silent)
    with (
        patch.object(
            device_module.bluetooth,
            "async_ble_device_from_address",
            return_value=BLEDevice(P300_ADDRESS, P300_NAME, {}),
        ),
        patch.object(device_module, "establish_connection", connect),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        for _ in range(100):
            await asyncio.sleep(0.01)
            if connect.await_count >= 2:
                break
        assert connect.await_count >= 2  # reconnected after the watchdog fired
        assert "no data" in (entry.runtime_data.last_error or "")
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_follows_station_by_name_when_address_changes(hass: HomeAssistant):
    entry = _entry(hass)
    new = service_info(address="7A:00:00:00:00:01")
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    with (
        patch.object(device_module.bluetooth, "async_ble_device_from_address", return_value=None),
        patch.object(device_module.bluetooth, "async_discovered_service_info", return_value=[new]),
    ):
        ble = entry.runtime_data._find_ble_device()
    assert ble is new.device
    assert entry.data[CONF_ADDRESS] == "7A:00:00:00:00:01"
    assert entry.unique_id == P300_ADDRESS  # entities keep their IDs
    assert await hass.config_entries.async_unload(entry.entry_id)
