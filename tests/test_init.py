"""Setup, entities and the BLE session (with a fake GATT client)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.allpowers import device as device_module
from custom_components.allpowers.const import CONF_UPDATE_INTERVAL, DOMAIN, NOTIFY_UUID, WRITE_UUID
from custom_components.allpowers.diagnostics import async_get_config_entry_diagnostics
from custom_components.allpowers.protocol import STATUS_REQUEST

from .helpers import P300_ADDRESS, P300_NAME, P300_SETTINGS, frame, service_info, status_frame


def _entry(hass: HomeAssistant, update_interval: int | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=P300_NAME,
        unique_id=P300_ADDRESS,
        data={CONF_ADDRESS: P300_ADDRESS, CONF_NAME: P300_NAME},
        options={} if update_interval is None else {CONF_UPDATE_INTERVAL: update_interval},
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
    # The second frame arrived within the update interval: published when it ends.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=16))
    await hass.async_block_till_done()

    assert hass.states.get(battery).state == "87"
    assert hass.states.get(_eid(hass, "sensor", "input_power")).state == "0"
    assert hass.states.get(_eid(hass, "sensor", "output_power")).state == "45"
    assert float(hass.states.get(_eid(hass, "sensor", "remaining_time")).state) == 5.0  # 300 min
    assert hass.states.get(_eid(hass, "select", "work_mode")).state == "standard"
    assert hass.states.get(_eid(hass, "sensor", "charge_time")).state == "unknown"  # not charging
    device.handle_notification(None, bytearray.fromhex("a565b1000106030201000a10107c"))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=32))
    await hass.async_block_till_done()
    assert hass.states.get(_eid(hass, "sensor", "charge_time")).state == "10"
    assert hass.states.get(_eid(hass, "select", "eco_shutdown")).state == "1"
    assert hass.states.get(_eid(hass, "switch", "ac_output")).state == STATE_ON
    assert hass.states.get(_eid(hass, "switch", "dc_output")).state == STATE_ON
    assert hass.states.get(_eid(hass, "switch", "eco_mode")).state == STATE_OFF
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
    entry = _entry(hass, update_interval=0)
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


async def test_updates_are_throttled(hass: HomeAssistant):
    """The station notifies about twice a second; entities change at most every 15 s (default)."""
    entry = _entry(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    device = entry.runtime_data
    device._set_connected(True)
    output = _eid(hass, "sensor", "output_power")
    changes: list[str] = []
    hass.bus.async_listen(
        "state_changed",
        lambda event: (
            changes.append(event.data["new_state"].state) if event.data["entity_id"] == output else None
        ),
    )
    device._last_publish = 0  # the last publish (connection) was long ago
    for watts in (4, 6, 5, 7, 19):
        device.handle_notification(None, bytearray(status_frame(output_w=watts)))
    await hass.async_block_till_done()
    assert changes == ["4"]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=16))
    await hass.async_block_till_done()
    assert changes == ["4", "19"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_remaining_time_is_a_rolling_median(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    """The station's estimate swings with the load: publish the median of the last 10 min."""
    clock = [1000.0]
    monkeypatch.setattr(device_module.time, "monotonic", lambda: clock[0])
    entry = _entry(hass, update_interval=0)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    device = entry.runtime_data
    device._set_connected(True)
    remaining = _eid(hass, "sensor", "remaining_time")
    assert hass.states.get(remaining).attributes["unit_of_measurement"] == "h"  # new install

    def send(minutes: int, input_w: int = 0) -> None:
        clock[0] += 15
        device.handle_notification(None, bytearray(status_frame(minutes=minutes, input_w=input_w)))

    for minutes in (1950, 1476, 1990, 2010, 2151, 1980, 1700):
        send(minutes)
    await hass.async_block_till_done()
    assert device.remaining_minutes == 1980
    assert float(hass.states.get(remaining).state) == pytest.approx(1980 / 60)

    # Readings older than the window drop out.
    clock[0] += 600
    send(1800)
    assert device.remaining_minutes == 1800

    # A publish with no new status (connection change) keeps the last value.
    device._set_connected(False)
    device._set_connected(True)
    assert device.remaining_minutes == 1800

    # Charging: the station has no estimate (5994) -> unknown, not 99.9 h.
    send(5994, input_w=112)
    await hass.async_block_till_done()
    assert device.remaining_minutes is None
    assert hass.states.get(remaining).state == "unknown"
    # Discharging again: a new window, without readings from before the charge.
    send(1500)
    send(1600)
    assert device.remaining_minutes == 1550
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_update_interval_option_applies_live(hass: HomeAssistant):
    entry = _entry(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == 15
    hass.config_entries.async_update_entry(entry, options={CONF_UPDATE_INTERVAL: 60})
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == 60
    assert await hass.config_entries.async_unload(entry.entry_id)


class StationClient(FakeClient):
    """Simulates the station: applies output/settings commands and notifies the new state."""

    def __init__(self, *, confirm: bool = True) -> None:
        super().__init__([])
        self.confirm = confirm
        self.flags = 0x01  # DC on
        self.settings = bytearray(P300_SETTINGS)

    async def write_gatt_char(self, uuid, data, response=None):
        data = bytes(data)
        self.writes.append((uuid, data))
        if self.confirm and data[:5] == bytes.fromhex("a56500b101") and data[6] == 0x00:
            ss = data[7]
            self.flags = (ss & 0x03) | (0x10 if ss & 0x20 else 0)
        if self.confirm and data[:5] == bytes.fromhex("a56500b101") and data[6] == 0x02:
            body = self.settings[:7] + data[7:9] + self.settings[9:13]
            self.settings = bytearray(frame(0x03, bytes(body[7:13])))
        self.handler(None, bytearray(status_frame(flags=self.flags)))
        self.handler(None, bytearray(self.settings))


async def _connected(hass: HomeAssistant, client: FakeClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(device_module, "KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(device_module, "COMMAND_TIMEOUT_SECONDS", 0.2)
    entry = _entry(hass, update_interval=0)
    ble = BLEDevice(P300_ADDRESS, P300_NAME, {})
    patches = (
        patch.object(device_module.bluetooth, "async_ble_device_from_address", return_value=ble),
        patch.object(device_module, "establish_connection", AsyncMock(return_value=client)),
    )
    for p in patches:
        p.start()
    assert await hass.config_entries.async_setup(entry.entry_id)
    for _ in range(200):
        await asyncio.sleep(0.01)
        if entry.runtime_data.available and entry.runtime_data.settings:
            break
    await hass.async_block_till_done()
    return entry, patches


async def test_switch_commands_are_confirmed(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    client = StationClient()
    entry, patches = await _connected(hass, client, monkeypatch)
    ac = _eid(hass, "switch", "ac_output")
    assert hass.states.get(ac).state == STATE_OFF
    await hass.services.async_call("switch", "turn_on", {"entity_id": ac}, blocking=True)
    assert hass.states.get(ac).state == STATE_ON
    assert (WRITE_UUID, bytes.fromhex("a56500b10101000372")) in client.writes  # AC + DC kept on

    # The P300 has no light switch; the command itself still uses the control bit 5.
    await entry.runtime_data.async_set_outputs(light=True)
    assert entry.runtime_data.status.light_on
    assert client.writes[-1][1][7] == 0x23

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _eid(hass, "select", "work_mode"), "option": "fast"},
        blocking=True,
    )
    assert hass.states.get(_eid(hass, "select", "work_mode")).state == "fast"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _eid(hass, "select", "eco_shutdown"), "option": "4"},
        blocking=True,
    )
    assert hass.states.get(_eid(hass, "select", "eco_shutdown")).state == "4"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": _eid(hass, "switch", "eco_mode")}, blocking=True
    )
    assert hass.states.get(_eid(hass, "switch", "eco_mode")).state == STATE_ON
    assert entry.runtime_data.settings.work_mode == "fast"  # earlier change kept

    assert await hass.config_entries.async_unload(entry.entry_id)
    for p in patches:
        p.stop()


async def test_unconfirmed_command_raises(hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch):
    client = StationClient(confirm=False)
    entry, patches = await _connected(hass, client, monkeypatch)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": _eid(hass, "switch", "ac_output")}, blocking=True
        )
    assert await hass.config_entries.async_unload(entry.entry_id)
    for p in patches:
        p.stop()


async def test_command_when_disconnected_raises(hass: HomeAssistant):
    entry = _entry(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError, match="not connected"):
        await entry.runtime_data.async_set_outputs(ac=False)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_p300_has_no_light_switch(hass: HomeAssistant):
    """The VOLIX P300 has no light: no switch, and one left by an older version is removed."""
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "switch", DOMAIN, f"{P300_ADDRESS}_light", suggested_object_id="old_light"
    )
    entry = _entry(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert registry.async_get(old.entity_id) is None
    assert registry.async_get_entity_id("switch", DOMAIN, f"{P300_ADDRESS}_ac_output") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_other_models_keep_the_light_switch(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AP S300",
        unique_id="AA:BB:CC:DD:EE:01",
        data={CONF_ADDRESS: "AA:BB:CC:DD:EE:01", CONF_NAME: "AP S300 1234"},
    )
    entry.add_to_hass(hass)
    with patch.object(device_module.AllpowersDevice, "start"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, "AA:BB:CC:DD:EE:01_light") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
