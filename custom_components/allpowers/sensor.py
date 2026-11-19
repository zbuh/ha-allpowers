"""Sensors: battery, input/output power, remaining time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AllpowersConfigEntry
from .device import AllpowersDevice
from .entity import AllpowersEntity


@dataclass(frozen=True, kw_only=True)
class AllpowersSensorDescription(SensorEntityDescription):
    value: Callable[[AllpowersDevice], int | str | None]
    # Data received (the value itself may be None: unknown, e.g. no remaining time while charging).
    has_data: Callable[[AllpowersDevice], bool] = lambda d: d.status is not None


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
        value=lambda d: d.status.charge_power if d.status else None,
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
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.remaining_minutes if d.status else None,
    ),
    AllpowersSensorDescription(
        key="charge_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.settings.charge_minutes if d.settings else None,
        has_data=lambda d: d.settings is not None,
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
        return super().available and self.entity_description.has_data(self.device)

    @property
    def native_value(self) -> int | str | None:
        return self.entity_description.value(self.device)
