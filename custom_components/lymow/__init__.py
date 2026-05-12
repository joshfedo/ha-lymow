"""Lymow integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LymowApiClient
from .auth import LymowAuth
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import LymowCoordinator

PLATFORMS = [Platform.LAWN_MOWER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    auth = LymowAuth(session)

    tokens = await auth.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    region = tokens["region"]

    creds = await auth.get_aws_credentials(tokens["IdToken"], region)

    client = LymowApiClient(
        session=session,
        access_token=tokens["AccessToken"],
        region=region,
        identity_id=creds["identity_id"],
    )

    devices = await client.get_devices()

    coordinator = LymowCoordinator(hass, client, devices)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
