import logging

from homeassistant_api import WebsocketClient

from transcental.cache import cache


def update_light(ws_client: WebsocketClient, env):
    with ws_client as client:
        light = client.get_entity(entity_id="light.bedroom")
        if light:
            state = light.state
            attributes = state.attributes
            rgb = attributes.get("rgb_color", (255, 255, 255))
            brightness = attributes.get("brightness", 255)
            temperature = attributes.get("color_temp", 4000)
            is_on = state.state == "on"
            cache.light_colour = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
            cache.light_brightness = int((brightness / 255) * 100)
            cache.light_temperature = temperature
            cache.light_on = is_on

        with client.listen_events("state_changed") as events:
            for event in events:
                if event.data["entity_id"] == "light.bedroom":
                    logging.info("Light state changed event received")
                    rgb = (
                        event.data["new_state"]
                        .get("attributes", {})
                        .get("rgb_color", (255, 255, 255))
                    )
                    brightness = (
                        event.data["new_state"]
                        .get("attributes", {})
                        .get("brightness", 255)
                    )
                    temperature = (
                        event.data["new_state"]
                        .get("attributes", {})
                        .get("color_temp", 4000)
                    )
                    is_on = event.data["new_state"].get("state", "off") == "on"
                    cache.light_colour = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
                    cache.light_brightness = int((brightness / 255) * 100)
                    cache.light_temperature = temperature
                    cache.light_on = is_on
                    logging.info(f"Cache updated: {cache}")

                    try:
                        env.loop.call_soon_threadsafe(
                            env.update_queue.put_nowait, "light_update"
                        )
                    except Exception as e:
                        logging.error(f"Failed to put update in queue: {e}")
