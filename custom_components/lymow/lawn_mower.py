"""Lymow lawn mower entity."""
from __future__ import annotations

from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LymowCoordinator

# Lymow status codes → HA LawnMowerActivity mapping (to be refined once
# get-device-info response schema is decoded)
_STATUS_MAP: dict[str, LawnMowerActivity] = {
    "mowing": LawnMowerActivity.MOWING,
    "docked": LawnMowerActivity.DOCKED,
    "charging": LawnMowerActivity.DOCKED,
    "paused": LawnMowerActivity.PAUSED,
    "error": LawnMowerActivity.ERROR,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: LymowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LymowMower(coordinator, device) for device in coordinator.devices
    )


class LymowMower(CoordinatorEntity[LymowCoordinator], LawnMowerEntity):
    _attr_supported_features = LawnMowerEntityFeature(0)  # expanded when MQTT is added

    def __init__(self, coordinator: LymowCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._thing_name = device["thingName"]
        self._attr_unique_id = self._thing_name
        self._attr_name = device.get("deviceName", self._thing_name)

    @property
    def _device_data(self) -> dict:
        return self.coordinator.data.get(self._thing_name, {})

    @property
    def activity(self) -> LawnMowerActivity:
        raw = self._device_data.get("status", "")
        return _STATUS_MAP.get(str(raw).lower(), LawnMowerActivity.ERROR)
