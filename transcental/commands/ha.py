from __future__ import annotations

import json
import logging
import re
from typing import Any
from typing import Dict
from typing import Optional

from slack_bolt.async_app import AsyncAck
from slack_bolt.async_app import AsyncRespond
from slack_sdk.web.async_client import AsyncWebClient

from transcental.config import config
from transcental.utils.logging import send_heartbeat

logger = logging.getLogger(__name__)


async def home_assistant_handler(
    ack: AsyncAck,
    client: AsyncWebClient,
    respond: AsyncRespond,
    performer: str,
    entity: str,
    action: str,
    value: Optional[str] = None,
) -> None:
    from transcental.env import env

    await ack()

    channel_info = await client.conversations_members(
        channel=config.slack.whitelist_channel
    )
    if performer not in channel_info.get("members", []):
        await respond("You are not authorized to use this command.")
        return

    domain = entity.split(".")[0]
    raw_value = value.strip() if value is not None else None

    service_data: Optional[Dict[str, Any]] = None
    service_name: Optional[str] = None

    async def call_service(
        svc: str, svc_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        try:
            if svc_data:
                await env.home.async_trigger_service(
                    domain, svc, entity_id=entity, **svc_data
                )
            else:
                await env.home.async_trigger_service(domain, svc, entity_id=entity)
            return None
        except Exception as exc:
            msg = f"Home Assistant service call failed: {exc!s}"
            logger.exception(msg)
            return msg

    act = action.lower()

    if act in ("toggle", "on", "off"):
        service_name = {
            "toggle": "toggle",
            "on": "turn_on",
            "off": "turn_off",
        }[act]
        err = await call_service(service_name)
        if err:
            await respond(err)
            return

    elif act == "brightness":
        if raw_value is None:
            await respond("Brightness command requires a value (0-100).")
            return
        try:
            pct = int(raw_value)
        except ValueError:
            await respond("Brightness must be an integer percentage (0-100).")
            return
        if not (0 <= pct <= 100):
            await respond("Brightness percent must be between 0 and 100.")
            return
        service_name = "turn_on"
        service_data = {"brightness_pct": pct}
        err = await call_service(service_name, service_data)
        if err:
            await respond(err)
            return

    elif act in ("temperature", "temp", "kelvin"):
        if raw_value is None:
            await respond("Temperature command requires a numeric kelvin value.")
            return
        try:
            kelvin = int(raw_value)
        except ValueError:
            await respond("Temperature must be an integer (kelvin).")
            return
        # Many integrations accept "kelvin" for color temperature. If your integration uses
        # a different key (color_temp, color_temp_kelvin), change this to match HA schema.
        service_name = "turn_on"
        service_data = {"kelvin": kelvin}
        err = await call_service(service_name, service_data)
        if err:
            await respond(err)
            return

    elif act in ("colour", "color"):
        if raw_value is None:
            await respond(
                "Colour command requires a value (e.g. #RRGGBB, rgb(255,0,0), rgbw(...), red)."
            )
            return

        ha_value: Optional[Dict[str, Any]] = None
        v = raw_value

        # Hex color like #RRGGBB (case-insensitive)
        if v.startswith("#") and len(v) == 7:
            try:
                r = int(v[1:3], 16)
                g = int(v[3:5], 16)
                b = int(v[5:7], 16)
                ha_value = {"rgb_color": [r, g, b]}
            except ValueError:
                await respond(f"Invalid hex color: {v}")
                return
        else:
            # Match forms: rgb(...), rgbw(...), rgbww(...)
            m = re.match(
                r"^(?P<name>rgbw?w?)\s*\(\s*(?P<body>.+)\s*\)\s*$", v, flags=re.I
            )
            if m:
                name = m.group("name").lower()
                parts = [p.strip() for p in m.group("body").split(",")]
                # Filter out any empty parts just in case
                parts = [p for p in parts if p != ""]
                try:
                    nums = [int(p) for p in parts]
                except ValueError:
                    await respond("RGB values must be integers.")
                    return

                if name == "rgb" and len(nums) == 3:
                    ha_value = {"rgb_color": nums}
                elif name == "rgbw" and len(nums) == 4:
                    ha_value = {"rgbw_color": nums}
                elif name == "rgbww" and len(nums) == 5:
                    ha_value = {"rgbww_color": nums}
                else:
                    await respond(
                        f"Invalid {name} format or wrong number of components: {v}"
                    )
                    return
            else:
                # Fallback to color name (string). Home Assistant accepts `color_name`.
                ha_value = {"color_name": v}

        service_name = "turn_on"
        service_data = ha_value
        err = await call_service(service_name, service_data)
        if err:
            await respond(err)
            return

    elif act == "raw":
        # Expect: "<service> <json-object>" or just "<service>" (no service_data)
        if raw_value is None:
            await respond(
                "Raw command requires a service name, optionally followed by JSON service_data."
            )
            return
        parts = raw_value.split(" ", 1)
        svc = parts[0]
        svc_data: Optional[Dict[str, Any]] = None
        if len(parts) > 1:
            await send_heartbeat(str(parts))
            payload = parts[1].strip()
            await send_heartbeat(payload)
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                await respond(f"Invalid JSON for raw service_data: {exc.msg}")
                return
            if not isinstance(parsed, dict):
                await respond("Raw service_data JSON must be an object/dictionary.")
                return
            svc_data = parsed

        service_name = svc
        service_data = svc_data or {}
        err = await call_service(service_name, service_data)
        if err:
            await respond(err)
            return

    else:
        await respond(f"Unknown action: {action}")
        return

    # Success response
    display_value = raw_value if raw_value is not None else ""
    msg = f"Performed {action} on {entity}{f' with `{display_value}`' if display_value else ''}"

    await respond(msg)
    await send_heartbeat(
        f"<@{performer}> {msg}", channel=config.slack.whitelist_channel
    )
