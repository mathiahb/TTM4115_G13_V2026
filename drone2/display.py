import logging

from config_loader import get_display_config

logger = logging.getLogger(__name__)

DEFAULT_COLORS = {
    "standby": (0, 255, 0),
    "travel": (0, 100, 255),
    "pickup": (0, 255, 255),
    "delivery": (255, 0, 0),
    "charge": (255, 255, 0),
    "charging": (255, 255, 0),
    "takeoff": (0, 100, 255),
    "return": (200, 0, 200),
    "error": (255, 0, 0),
    "none": (100, 100, 100),
}

BATTERY_COLOR = (0, 255, 0)
PROGRESS_COLOR = (0, 150, 255)
OFF = (0, 0, 0)


class Display:
    def __init__(self, config: dict | None = None):
        self.sense = None
        self.enabled = False
        self.current_state = None

        display_cfg = get_display_config(config or {})
        colors_cfg = display_cfg.get("colors", {})

        self.colors = {**DEFAULT_COLORS}
        for key, val in colors_cfg.items():
            self.colors[key] = tuple(val)

        self.enabled = display_cfg.get("enabled", True)

        if not self.enabled:
            logger.info("Display disabled by config")
            return

        try:
            from sense_hat import SenseHat

            self.sense = SenseHat()
            logger.info("Sense HAT initialized")
        except Exception:
            logger.warning("Sense HAT not available, display disabled")
            self.sense = None
            self.enabled = False

    def update(self, state: str, battery_level: float, route_progress: float):
        if not self.enabled or not self.sense:
            return
        self.current_state = state
        color = self.colors.get(state, OFF)
        bat_count = int(battery_level / 100.0 * 16)
        progress_count = int(route_progress * 16)
        pixels = (
            [color] * 16
            + [OFF] * 8
            + [BATTERY_COLOR] * bat_count + [OFF] * (16 - bat_count)
            + [OFF] * 8
            + [PROGRESS_COLOR] * progress_count + [OFF] * (16 - progress_count)
        )
        try:
            self.sense.set_pixels(pixels)
        except Exception as e:
            logger.error("Display error: %s", e)

    def clear(self):
        if not self.enabled or not self.sense:
            return
        try:
            self.sense.clear()
            self.current_state = None
        except Exception as e:
            logger.error("Display error: %s", e)

    def is_available(self) -> bool:
        return self.enabled and self.sense is not None
