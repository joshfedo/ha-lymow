"""Lymow sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LymowCoordinator


@dataclass(frozen=True, kw_only=True)
class LymowSensorDescription(SensorEntityDescription):
    value_key: str


SENSORS: tuple[LymowSensorDescription, ...] = (
    LymowSensorDescription(
        key="connectivity",
        name="Connectivity",
        value_key="deviceState",
        icon="mdi:wifi",
    ),
    LymowSensorDescription(
        key="firmware",
        name="Firmware version",
        value_key="softwareVersion",
        icon="mdi:tag",
    ),
    LymowSensorDescription(
        key="mcu_version",
        name="MCU version",
        value_key="mcuVersion",
        icon="mdi:chip",
        entity_registry_enabled_default=False,
    ),
    LymowSensorDescription(
        key="ip_address",
        name="IP address",
        value_key="ipAddress",
        icon="mdi:ip-network",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LymowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LymowSensor(coordinator, device, description)
        for device in coordinator.devices
        for description in SENSORS
    )


class LymowSensor(CoordinatorEntity[LymowCoordinator], SensorEntity):
    entity_description: LymowSensorDescription

    def __init__(self, coordinator: LymowCoordinator, device: dict, description: LymowSensorDescription) -> None:
        super().__init__(coordinator)
        self._thing_name = device["deviceThingName"]
        self.entity_description = description
        self._attr_unique_id = f"{self._thing_name}_{description.key}"
        device_label = device.get("deviceName") or device.get("sn") or self._thing_name
        self._attr_name = f"{device_label} {description.name}"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self._thing_name, {}).get(self.entity_description.value_key)
