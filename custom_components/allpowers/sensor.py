"""Sensors: battery, input/output power, remaining time, work mode."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AllpowersConfigEntry
from .device import AllpowersDevice
from .entity import AllpowersEntity
from .protocol import WORK_MODES


@dataclass(frozen=True, kw_only=True)
class AllpowersSensorDescription(SensorEntityDescription):
    value: Callable[[AllpowersDevice], int | str | None]


SENSORS: tuple[AllpowersSensorDescription, ...] = (
    AllpowersSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.status.battery if d.status else None,
    ),
    AllpowersSensorDescription(
        key="input_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.status.input_power if d.status else None,
    ),
    AllpowersSensorDescription(
        key="output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.status.output_power if d.status else None,
    ),
    AllpowersSensorDescription(
        key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.status.remaining_minutes if d.status else None,
    ),
    AllpowersSensorDescription(
        key="work_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(WORK_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.settings.work_mode if d.settings else None,
    ),
    AllpowersSensorDescription(
        key="eco_shutdown",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.settings.eco_shutdown_hours if d.settings else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllpowersConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    device = entry.runtime_data
    unique_id = entry.unique_id or entry.data["address"]
    async_add_entities(AllpowersSensor(device, unique_id, description) for description in SENSORS)


class AllpowersSensor(AllpowersEntity, SensorEntity):
    entity_description: AllpowersSensorDescription

    def __init__(
        self, device: AllpowersDevice, unique_id: str, description: AllpowersSensorDescription
    ) -> None:
        super().__init__(device, unique_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.value(self.device) is not None

    @property
    def native_value(self) -> int | str | None:
        return self.entity_description.value(self.device)
