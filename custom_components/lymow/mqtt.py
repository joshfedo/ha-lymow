"""AWS IoT MQTT over WebSocket for Lymow devices.

Connects to the AWS IoT endpoint using a SigV4-presigned WebSocket URL built
from temporary Cognito Identity credentials. Publishes protobuf commands and
delivers decoded state updates via a callback.

All AWS endpoint details were determined from traffic capture of the Android
app — specifically the WebSocket upgrade request to the IoT MQTT endpoint.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import ssl
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

_LOGGER = logging.getLogger(__name__)

# Lazy import of paho to keep HA startup fast
try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# SigV4 presigned WebSocket URL
# ---------------------------------------------------------------------------

def _hmac_sha256(key: bytes, data: str) -> bytes:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_str: str, region: str, service: str) -> bytes:
    k_date    = _hmac_sha256(("AWS4" + secret_key).encode(), date_str)
    k_region  = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "aws4_request")


def build_presigned_ws_path(
    host: str,
    region: str,
    access_key: str,
    secret_key: str,
    session_token: str | None,
) -> str:
    """Return the /mqtt?... path for a SigV4-signed MQTT-over-WebSocket URL.

    Constructed to match the query-string format observed in traffic capture
    of the app connecting to the AWS IoT endpoint.
    """
    now = datetime.now(UTC)
    amz_date  = now.strftime("%Y%m%dT%H%M%SZ")
    date_str  = now.strftime("%Y%m%d")
    service   = "iotdevicegateway"
    method    = "GET"
    uri       = "/mqtt"

    credential_scope = f"{date_str}/{region}/{service}/aws4_request"
    credential       = f"{access_key}/{credential_scope}"

    signed_headers = "host"
    canonical_qs_parts: dict[str, str] = {
        "X-Amz-Algorithm":     "AWS4-HMAC-SHA256",
        "X-Amz-Credential":    credential,
        "X-Amz-Date":          amz_date,
        "X-Amz-SignedHeaders": signed_headers,
    }
    if session_token:
        canonical_qs_parts["X-Amz-Security-Token"] = session_token

    # Sort keys for canonical query string
    canonical_qs = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}"
        for k, v in sorted(canonical_qs_parts.items())
    )

    canonical_headers = f"host:{host}\n"
    payload_hash      = hashlib.sha256(b"").hexdigest()

    canonical_request = "\n".join([
        method, uri, canonical_qs,
        canonical_headers, signed_headers, payload_hash,
    ])

    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    sig = _signing_key(secret_key, date_str, region, service)
    signature = hmac.new(sig, string_to_sign.encode(), hashlib.sha256).hexdigest()

    final_qs = canonical_qs + f"&X-Amz-Signature={signature}"
    return f"{uri}?{final_qs}"


# ---------------------------------------------------------------------------
# MQTT client
# ---------------------------------------------------------------------------

StateCallback = Callable[[str, dict[str, Any]], None]   # (thing_name, state_patch)
OnlineCallback = Callable[[str, bool], None]            # (thing_name, is_online)


class LymowMqttClient:
    """Manages a single AWS IoT WebSocket MQTT connection for all devices."""

    def __init__(
        self,
        host: str,
        region: str,
        on_state: StateCallback,
        on_online: OnlineCallback,
    ) -> None:
        self._host      = host
        self._region    = region
        self._on_state  = on_state
        self._on_online = on_online

        self._client:     mqtt.Client | None = None
        self._loop:       asyncio.AbstractEventLoop | None = None
        self._things:     list[str] = []
        self._connected   = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(
        self,
        things: list[str],
        access_key: str,
        secret_key: str,
        session_token: str | None,
    ) -> None:
        """Connect to AWS IoT and subscribe to all device topics."""
        if mqtt is None:
            raise RuntimeError("paho-mqtt is not installed")

        self._things = things
        self._loop   = asyncio.get_running_loop()
        self._connected.clear()

        ws_path = build_presigned_ws_path(
            self._host, self._region, access_key, secret_key, session_token
        )

        client = mqtt.Client(
            client_id=f"lymow-ha-{uuid.uuid4().hex[:8]}",
            transport="websockets",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        ssl_ctx = ssl.create_default_context()
        client.tls_set_context(ssl_ctx)
        client.ws_set_options(path=ws_path, headers={"Host": self._host})

        client.on_connect    = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message    = self._on_message

        self._client = client

        await self._loop.run_in_executor(None, lambda: client.connect(self._host, 443, keepalive=30))
        client.loop_start()

        try:
            await asyncio.wait_for(self._connected.wait(), timeout=15)
        except asyncio.TimeoutError:
            _LOGGER.warning("MQTT connection timed out")

    async def reconnect(
        self,
        access_key: str,
        secret_key: str,
        session_token: str | None,
    ) -> None:
        """Reconnect with fresh credentials (called when AWS creds expire)."""
        await self.disconnect()
        await self.connect(self._things, access_key, secret_key, session_token)

    async def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            await asyncio.get_running_loop().run_in_executor(None, self._client.disconnect)
            self._client = None

    def publish_command(self, thing_name: str, pb_bytes: bytes) -> None:
        """Publish a protobuf command to the device's pbinput topic."""
        from .protocol import wrap_envelope
        if not self._client:
            _LOGGER.warning("MQTT not connected — command dropped")
            return
        topic   = f"/device/{thing_name}/pbinput"
        payload = wrap_envelope(pb_bytes)
        self._client.publish(topic, payload, qos=1)

    # ------------------------------------------------------------------
    # Internal paho callbacks (called from paho's thread)
    # ------------------------------------------------------------------

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc != 0:
            _LOGGER.error("MQTT connect failed: rc=%d", rc)
            return
        _LOGGER.debug("MQTT connected")
        for thing in self._things:
            client.subscribe(f"/device/{thing}/pboutput", qos=1)
            client.subscribe(f"/device/{thing}/notify-app", qos=1)
        if self._loop:
            self._loop.call_soon_threadsafe(self._connected.set)

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        _LOGGER.warning("MQTT disconnected: rc=%d", rc)
        if self._loop:
            self._loop.call_soon_threadsafe(self._connected.clear)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        topic   = msg.topic
        payload = msg.payload

        # Determine which thing this message belongs to
        thing_name: str | None = None
        for thing in self._things:
            if f"/device/{thing}/" in topic:
                thing_name = thing
                break
        if thing_name is None:
            return

        try:
            if topic.endswith("/pboutput"):
                self._handle_pboutput(thing_name, payload)
            elif topic.endswith("/notify-app"):
                self._handle_notify(thing_name, payload)
        except Exception:
            _LOGGER.exception("Error handling MQTT message on %s", topic)

    def _handle_pboutput(self, thing_name: str, payload: bytes) -> None:
        from .protocol import decode_pboutput, unwrap_envelope
        pb_bytes = unwrap_envelope(payload)
        state    = decode_pboutput(pb_bytes)
        if self._loop:
            self._loop.call_soon_threadsafe(self._on_state, thing_name, state)

    def _handle_notify(self, thing_name: str, payload: bytes) -> None:
        import json
        try:
            data      = json.loads(payload)
            is_online = str(data.get("robotState", "")).lower() == "online"
        except Exception:
            return
        if self._loop:
            self._loop.call_soon_threadsafe(self._on_online, thing_name, is_online)
