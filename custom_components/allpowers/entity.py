"""Common entity base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .device import AllpowersDevice


class AllpowersEntity(Entity):
    """Push entity, refreshed by the device session."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: AllpowersDevice, unique_id: str, key: str) -> None:
        self.device = device
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            connections={(CONNECTION_BLUETOOTH, device.address)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=device.name,
        )

    @property
    def available(self) -> bool:
        return self.device.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.device.async_add_listener(self._handle_update))

    def _handle_update(self) -> None:
        self.async_write_ha_state()
