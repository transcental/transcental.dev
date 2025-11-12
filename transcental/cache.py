from dataclasses import dataclass


@dataclass
class Cache:
    light_colour: str = "rgb(255,255,255)"
    light_brightness: int = 100
    light_temperature: int = 4000
    light_on: bool = True


cache = Cache()
