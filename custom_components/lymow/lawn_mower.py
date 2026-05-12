"""Lymow lawn mower entity."""
from __future__ import annotations

from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LymowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LymowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LymowMower(coordinator, device) for device in coordinator.devices
    )


class LymowMower(CoordinatorEntity[LymowCoordinator], LawnMowerEntity):
    # No control features until MQTT is implemented.
    _attr_supported_features = LawnMowerEntityFeature(0)

    def __init__(self, coordinator: LymowCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._thing_name = device["deviceThingName"]
        self._attr_unique_id = self._thing_name
        device_label = device.get("deviceName") or device.get("sn") or self._thing_name
        self._attr_name = device_label

    @property
    def _device_data(self) -> dict:
        return self.coordinator.data.get(self._thing_name, {})

    @property
    def activity(self) -> LawnMowerActivity:
        # Real mowing state comes via MQTT — for now reflect connectivity only.
        device_state = self._device_data.get("deviceState", "")
        if device_state == "online":
            return LawnMowerActivity.DOCKED
        return LawnMowerActivity.ERROR
