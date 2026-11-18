"""ALLPOWERS power stations over Bluetooth LE (local push)."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, LOCAL_NAME, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
from .device import AllpowersDevice

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

type AllpowersConfigEntry = ConfigEntry[AllpowersDevice]


async def async_setup_entry(hass: HomeAssistant, entry: AllpowersConfigEntry) -> bool:
    """Start the BLE session; entities stay unavailable until the station answers."""

    @callback
    def _address_changed(address: str) -> None:
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_ADDRESS: address})

    device = AllpowersDevice(
        hass,
        entry.data[CONF_ADDRESS],
        entry.data[CONF_NAME],
        _address_changed,
        entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )
    entry.runtime_data = device

    @callback
    def _seen(_info: bluetooth.BluetoothServiceInfoBleak, _change: bluetooth.BluetoothChange) -> None:
        device.wake()

    for matcher in (
        BluetoothCallbackMatcher({ADDRESS: entry.data[CONF_ADDRESS], "connectable": True}),
        BluetoothCallbackMatcher({LOCAL_NAME: entry.data[CONF_NAME], "connectable": True}),
    ):
        entry.async_on_unload(
            bluetooth.async_register_callback(hass, _seen, matcher, bluetooth.BluetoothScanningMode.PASSIVE)
        )

    @callback
    def _update_versions() -> None:
        settings = device.settings
        if settings is None:
            return
        registry = dr.async_get(hass)
        for dev in dr.async_entries_for_config_entry(registry, entry.entry_id):
            if (dev.sw_version, dev.hw_version) != (settings.firmware_version, settings.hardware_version):
                registry.async_update_device(
                    dev.id, sw_version=settings.firmware_version, hw_version=settings.hardware_version
                )

    entry.async_on_unload(device.async_add_listener(_update_versions))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    device.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AllpowersConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.stop()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: AllpowersConfigEntry) -> None:
    entry.runtime_data.update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
