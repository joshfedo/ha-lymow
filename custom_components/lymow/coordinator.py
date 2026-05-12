"""Data update coordinator for Lymow."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LymowApiClient
from .const import DOMAIN, POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LymowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, client: LymowApiClient, devices: list[dict]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLLING_INTERVAL),
        )
        self._client = client
        self.devices = devices

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            result = {}
            for device in self.devices:
                thing_name = device["deviceThingName"]
                result[thing_name] = await self._client.get_device_info(thing_name)
            return result
        except Exception as err:
            raise UpdateFailed(f"Error fetching Lymow data: {err}") from err
