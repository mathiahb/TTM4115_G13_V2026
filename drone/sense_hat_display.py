import logging
from config_loader import get_display_colors, get_display_enabled

logger = logging.getLogger(__name__)


class SenseHATDisplay:
    """
    Handles LED matrix display on Raspberry Pi Sense HAT.
    Shows drone state through colors and patterns.
    """

    # Default color definitions (R, G, B)
    DEFAULT_COLORS = {
        'standby': (0, 255, 0),           # Green
        'charge': (255, 255, 0),          # Yellow
        'travel_to_warehouse': (0, 100, 255),  # Blue
        'order_pickup': (0, 255, 255),    # Cyan
        'travel_to_customer': (0, 100, 255),   # Blue
        'deliver': (255, 0, 0),           # Red
        'travel_return': (200, 0, 200),   # Purple
        'off': (0, 0, 0),                 # Off
    }

    def __init__(self, config=None):
        self.config = config or {}
        self.sense = None
        self.enabled = False
        self.current_state = None

        self.colors = get_display_colors(self.config) or self.DEFAULT_COLORS.copy()
        # Fill in any missing colors from defaults
        for state, color in self.DEFAULT_COLORS.items():
            if state not in self.colors:
                self.colors[state] = color
        self.enabled = get_display_enabled(self.config)

        if not self.enabled:
            logger.info("Sense HAT display disabled by configuration")
            return

        try:
            from sense_hat import SenseHat
            self.sense = SenseHat()
            logger.info("Sense HAT initialized successfully")
        except ImportError:
            logger.warning("Sense HAT library not available - LED display disabled")
            self.enabled = False
        except Exception as e:
            logger.warning(f"Failed to initialize Sense HAT: {e} - LED display disabled")
            self.enabled = False

    def set_state(self, state):
        if not self.enabled or not self.sense:
            return

        self.current_state = state
        color = self.colors.get(state, self.colors['off'])

        try:
            self.sense.set_pixel(0, 0, color)
            logger.debug(f"Display updated for state: {state}, color: {color}")
        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def pulse(self, color=None):
        if not self.enabled or not self.sense:
            return

        target_color = color if color else self.colors.get(self.current_state, self.colors['standby'])

        try:
            steps = 5
            for brightness in range(steps):
                intensity = (brightness + 1) / steps
                pulse_color = tuple(int(c * intensity) for c in target_color)
                self.sense.set_pixel(0, 0, pulse_color)

            for brightness in range(steps - 1, -1, -1):
                intensity = (brightness + 1) / steps
                pulse_color = tuple(int(c * intensity) for c in target_color)
                self.sense.set_pixel(0, 0, pulse_color)

            self.sense.set_pixel(0, 0, target_color)
        except Exception as e:
            logger.error(f"Error during pulse animation: {e}")

    def show_event(self, event_type):
        """Display a special pattern for important events."""
        if not self.enabled or not self.sense:
            return

        event_colors = {
            'battery_depleted': (255, 0, 0),      # Red flash
            'fully_charged': (0, 255, 0),         # Green flash
            'arrived': (0, 255, 255),             # Cyan flash
            'delivery_completed': (0, 255, 0),   # Green flash
        }

        color = event_colors.get(event_type, (255, 255, 255))

        try:
            for _ in range(3):
                self.sense.set_pixel(0, 0, color)
                self.sense.set_pixel(0, 0, (0, 0, 0))
        except Exception as e:
            logger.error(f"Error showing event: {e}")

    def clear(self):
        """Clear the display."""
        if not self.enabled or not self.sense:
            return

        try:
            self.sense.set_pixel(0, 0, (0, 0, 0))
            self.current_state = None
        except Exception as e:
            logger.error(f"Error clearing display: {e}")

    def is_available(self):
        """Check if Sense HAT is available."""
        return self.enabled and self.sense is not None
