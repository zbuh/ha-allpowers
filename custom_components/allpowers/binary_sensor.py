"""Binary sensor: the BLE link (outputs and ECO are switches)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AllpowersConfigEntry
from .device import AllpowersDevice
from .entity import AllpowersEntity


@dataclass(frozen=True, kw_only=True)
class AllpowersBinaryDescription(BinarySensorEntityDescription):
    value: Callable[[AllpowersDevice], bool | None]
    always_available: bool = False


BINARY_SENSORS: tuple[AllpowersBinaryDescription, ...] = (
    AllpowersBinaryDescription(
        key="connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.available,
        always_available=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllpowersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    unique_id = entry.unique_id or entry.data["address"]
    async_add_entities(
        AllpowersBinarySensor(device, unique_id, description) for description in BINARY_SENSORS
    )


class AllpowersBinarySensor(AllpowersEntity, BinarySensorEntity):
    entity_description: AllpowersBinaryDescription

    def __init__(
        self, device: AllpowersDevice, unique_id: str, description: AllpowersBinaryDescription
    ) -> None:
        super().__init__(device, unique_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.always_available:
            return True
        return super().available and self.entity_description.value(self.device) is not None

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value(self.device)
