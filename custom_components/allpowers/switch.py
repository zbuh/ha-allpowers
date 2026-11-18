"""Switches: AC/DC outputs, light and ECO mode (each change is confirmed by the station)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AllpowersConfigEntry
from .device import AllpowersDevice
from .entity import AllpowersEntity


@dataclass(frozen=True, kw_only=True)
class AllpowersSwitchDescription(SwitchEntityDescription):
    value: Callable[[AllpowersDevice], bool | None]
    set: Callable[[AllpowersDevice, bool], Awaitable[None]]


SWITCHES: tuple[AllpowersSwitchDescription, ...] = (
    AllpowersSwitchDescription(
        key="ac_output",
        device_class=SwitchDeviceClass.OUTLET,
        value=lambda d: d.status.ac_on if d.status else None,
        set=lambda d, on: d.async_set_outputs(ac=on),
    ),
    AllpowersSwitchDescription(
        key="dc_output",
        device_class=SwitchDeviceClass.OUTLET,
        value=lambda d: d.status.dc_on if d.status else None,
        set=lambda d, on: d.async_set_outputs(dc=on),
    ),
    AllpowersSwitchDescription(
        key="light",
        value=lambda d: d.status.light_on if d.status else None,
        set=lambda d, on: d.async_set_outputs(light=on),
    ),
    AllpowersSwitchDescription(
        key="eco_mode",
        entity_category=EntityCategory.CONFIG,
        value=lambda d: d.settings.eco if d.settings else None,
        set=lambda d, on: d.async_set_settings(eco=on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllpowersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    unique_id = entry.unique_id or entry.data["address"]
    async_add_entities(AllpowersSwitch(device, unique_id, description) for description in SWITCHES)


class AllpowersSwitch(AllpowersEntity, SwitchEntity):
    entity_description: AllpowersSwitchDescription

    def __init__(
        self, device: AllpowersDevice, unique_id: str, description: AllpowersSwitchDescription
    ) -> None:
        super().__init__(device, unique_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.value(self.device) is not None

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set(self.device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set(self.device, False)
