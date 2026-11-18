"""Selects: work mode and ECO shutdown time (read-modify-write of the settings)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AllpowersConfigEntry
from .device import AllpowersDevice
from .entity import AllpowersEntity
from .protocol import ECO_SHUTDOWN_HOURS, WORK_MODES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllpowersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    unique_id = entry.unique_id or entry.data["address"]
    async_add_entities([WorkModeSelect(device, unique_id), EcoShutdownSelect(device, unique_id)])


class WorkModeSelect(AllpowersEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(WORK_MODES.values())

    def __init__(self, device: AllpowersDevice, unique_id: str) -> None:
        super().__init__(device, unique_id, "work_mode")

    @property
    def available(self) -> bool:
        return super().available and self.device.settings is not None

    @property
    def current_option(self) -> str | None:
        return self.device.settings.work_mode if self.device.settings else None

    async def async_select_option(self, option: str) -> None:
        await self.device.async_set_settings(work_mode=option)


class EcoShutdownSelect(AllpowersEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = [str(hours) for hours in ECO_SHUTDOWN_HOURS]

    def __init__(self, device: AllpowersDevice, unique_id: str) -> None:
        super().__init__(device, unique_id, "eco_shutdown")

    @property
    def available(self) -> bool:
        return super().available and self.device.settings is not None

    @property
    def current_option(self) -> str | None:
        settings = self.device.settings
        if settings is None or settings.eco_shutdown_hours not in ECO_SHUTDOWN_HOURS:
            return None
        return str(settings.eco_shutdown_hours)

    async def async_select_option(self, option: str) -> None:
        await self.device.async_set_settings(eco_shutdown_hours=int(option))
