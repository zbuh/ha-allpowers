"""Config flow: Bluetooth discovery or pick a station seen nearby."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    is_supported_name,
)


class AllpowersConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AllpowersOptionsFlow()

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._devices: dict[str, BluetoothServiceInfoBleak] = {}

    def _same_station_configured(self, info: BluetoothServiceInfoBleak) -> bool:
        """A configured station that is not connected and has the same name.

        Stations with a random BLE address reappear under a new address after a
        reboot; the running entry follows them by name, so do not offer a duplicate.
        A station that is connected does not advertise, so a same-name advertisement
        while the entry is connected is a second station.
        """
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data.get(CONF_NAME) != info.name:
                continue
            device = getattr(entry, "runtime_data", None)
            if device is None or not device.connected:
                return True
        return False

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if self._same_station_configured(discovery_info):
            return self.async_abort(reason="already_configured")
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self._create(self._discovery)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery.name, "address": self._discovery.address},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            info = self._devices[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self._create(info)

        configured = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if (
                info.address in configured
                or not is_supported_name(info.name)
                or self._same_station_configured(info)
            ):
                continue
            self._devices[info.address] = info
        if not self._devices:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {address: f"{info.name} ({address})" for address, info in self._devices.items()}
                    )
                }
            ),
        )

    def _create(self, info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        return self.async_create_entry(
            title=info.name,
            data={CONF_ADDRESS: info.address, CONF_NAME: info.name},
        )


class AllpowersOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                    )
                }
            ),
        )
