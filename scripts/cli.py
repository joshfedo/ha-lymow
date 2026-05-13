"""CLI to test Lymow auth and API responses.

Credentials are read from environment variables LYMOW_USER / LYMOW_PASS.
Create a .env file (see .env.example) in the scripts/ directory or repo root
and it will be loaded automatically — no need to export variables each time.

Usage:
    uv run python scripts/cli.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys


def _load_dotenv() -> None:
    """Load key=value pairs from .env into os.environ (does not override existing vars)."""
    candidates = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


def _load(module_name: str, path: str) -> None:
    if module_name in sys.modules:
        return
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]


_load_dotenv()

_base = os.path.join(os.path.dirname(__file__), "..", "custom_components", "lymow")
_load("lymow.const", os.path.join(_base, "const.py"))
_load("lymow.auth", os.path.join(_base, "auth.py"))
_load("lymow.api", os.path.join(_base, "api.py"))

import aiohttp  # noqa: E402

from lymow.auth import LymowAuth  # noqa: E402
from lymow.api import LymowApiClient  # noqa: E402


async def main() -> None:
    username = os.environ.get("LYMOW_USER")
    password = os.environ.get("LYMOW_PASS")

    if not username or not password:
        print("Set LYMOW_USER and LYMOW_PASS in a .env file (see scripts/.env.example) or as env vars")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        print("--- Logging in ---")
        auth = LymowAuth(session)
        tokens = await auth.login(username, password)
        print(f"Region:  {tokens['region']}")
        print(f"Expires: {tokens['ExpiresIn']}s")

        print("\n--- Getting AWS credentials ---")
        creds_data = await auth.get_aws_credentials(tokens["IdToken"], tokens["region"])
        print(f"Identity ID: {creds_data['identity_id']}")

        client = LymowApiClient(
            session=session,
            access_token=tokens["AccessToken"],
            region=tokens["region"],
            identity_id=creds_data["identity_id"],
        )

        print("\n--- Device list ---")
        devices = await client.get_devices()
        print(json.dumps(devices, indent=2))

        for device in (devices if isinstance(devices, list) else []):
            thing = device.get("deviceThingName") or device.get("thingName") or list(device.values())[0]
            print(f"\n--- Device info: {thing} ---")
            info = await client.get_device_info(thing)
            print(json.dumps(info, indent=2))

            print(f"\n--- Device feature: {thing} ---")
            feature = await client.get_device_feature(thing)
            print(json.dumps(feature, indent=2))


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
