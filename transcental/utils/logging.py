from typing import Optional

from slack_sdk.web.async_client import AsyncWebClient

from transcental.config import config


async def send_heartbeat(
    heartbeat: str,
    messages: Optional[list[str]] = None,
    client: AsyncWebClient | None = None,
    channel: Optional[str] = None,
):
    # Avoid using a mutable default argument. Normalize to an empty list if None.
    if messages is None:
        messages = []
    if not client:
        from transcental.env import env

        client = env.slack_client
    if config.slack.heartbeat_channel:
        if not channel:
            channel = config.slack.heartbeat_channel
        msg = await client.chat_postMessage(channel=channel, text=heartbeat)
        if messages:
            for message in messages:
                await client.chat_postMessage(
                    channel=channel,
                    text=message,
                    thread_ts=msg["ts"],
                )
