"""Lymow REST API client."""
from __future__ import annotations

from typing import Any

import aiohttp

from .const import REGION_CONFIG


def _api_url(region: str, gateway_key: str, path: str) -> str:
    gw_id = REGION_CONFIG[region][gateway_key]
    return f"https://{gw_id}.execute-api.{region}.amazonaws.com{path}"


class LymowApiClient:
    def __init__(self, session: aiohttp.ClientSession, id_token: str, region: str, identity_id: str) -> None:
        self._session = session
        self._id_token = id_token
        self._region = region
        self._identity_id = identity_id

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": self._id_token}

    def update_tokens(self, id_token: str) -> None:
        self._id_token = id_token

    async def get_devices(self) -> list[dict[str, Any]]:
        url = _api_url(self._region, "api_device_list", "/prod/device-list-query")
        params = {"p": "devices", "identityId": self._identity_id}
        async with self._session.get(url, headers=self._headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_device_info(self, thing_name: str) -> dict[str, Any]:
        url = _api_url(self._region, "api_device_info", "/prod/get-device-info")
        params = {"deviceThingName": thing_name}
        async with self._session.get(url, headers=self._headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_device_feature(self, thing_name: str) -> dict[str, Any]:
        url = _api_url(self._region, "api_device_info", "/prod/get-device-feature")
        params = {"deviceThingName": thing_name}
        async with self._session.get(url, headers=self._headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()
