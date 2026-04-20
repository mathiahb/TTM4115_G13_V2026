import logging

logger = logging.getLogger(__name__)


class SenseHATDisplay:
    """
    Handles LED matrix display on Raspberry Pi Sense HAT.
    Shows drone state through colors and patterns.
    """

    # Color definitions (R, G, B)
    COLORS = {
        'standby': (0, 255, 0),           # Green
        'charge': (255, 255, 0),          # Yellow
        'travel_to_warehouse': (0, 100, 255),  # Blue
        'order_pickup': (0, 255, 255),    # Cyan
        'travel_to_customer': (0, 100, 255),   # Blue
        'deliver': (255, 0, 0),           # Red
        'travel_return': (200, 0, 200),   # Purple
        'off': (0, 0, 0),                 # Off
    }

    def __init__(self):
        self.sense = None
        self.enabled = False
        self.current_state = None
        self.animation_frame = 0

        try:
            from sense_hat import SenseHat
            self.sense = SenseHat()
            self.enabled = True
            logger.info("Sense HAT initialized successfully")
        except ImportError:
            logger.warning("Sense HAT library not available - LED display disabled")
            self.enabled = False
        except Exception as e:
            logger.warning(f"Failed to initialize Sense HAT: {e} - LED display disabled")
            self.enabled = False

    def set_state(self, state):
        """Update display to reflect current drone state."""
        if not self.enabled or not self.sense:
            return

        self.current_state = state
        color = self.COLORS.get(state, self.COLORS['off'])

        try:
            # Fill entire matrix with state color
            if state in ['travel_to_warehouse', 'travel_to_customer', 'travel_return']:
                # Animated pattern for travel states
                self._display_travel_animation(color)
            else:
                # Solid color for non-travel states
                self._display_solid(color)

            logger.debug(f"Display updated for state: {state}, color: {color}")
        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def _display_solid(self, color):
        """Display a solid color on the entire matrix."""
        if not self.sense:
            return

        pixel_list = [color] * 64
        self.sense.set_pixels(pixel_list)
        self.animation_frame = 0

    def _display_travel_animation(self, color):
        """Display an animated pattern for travel states."""
        if not self.sense:
            return

        # Create a moving pattern - traveling dots
        pixel_list = [(0, 0, 0)] * 64

        # Create a diagonal moving pattern
        frame = self.animation_frame % 16
        positions = [
            frame,
            frame + 8,
            (frame + 16) % 64,
            (frame + 24) % 64,
        ]

        for pos in positions:
            if pos < 64:
                pixel_list[pos] = color

        self.sense.set_pixels(pixel_list)
        self.animation_frame += 1

    def pulse(self, color=None):
        """Pulse the display with a color (useful for important events)."""
        if not self.enabled or not self.sense:
            return

        target_color = color if color else self.COLORS.get(self.current_state, self.COLORS['standby'])

        try:
            # Pulse effect: fade in and out
            steps = 5
            for brightness in range(steps):
                intensity = (brightness + 1) / steps
                pulse_color = tuple(int(c * intensity) for c in target_color)
                pixel_list = [pulse_color] * 64
                self.sense.set_pixels(pixel_list)

            for brightness in range(steps - 1, -1, -1):
                intensity = (brightness + 1) / steps
                pulse_color = tuple(int(c * intensity) for c in target_color)
                pixel_list = [pulse_color] * 64
                self.sense.set_pixels(pixel_list)

            # Return to solid color
            self._display_solid(target_color)
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
            # Flash the event color
            for _ in range(3):
                pixel_list = [color] * 64
                self.sense.set_pixels(pixel_list)
                # In real implementation, would need threading to pause
                pixel_list = [(0, 0, 0)] * 64
                self.sense.set_pixels(pixel_list)
        except Exception as e:
            logger.error(f"Error showing event: {e}")

    def clear(self):
        """Clear the display."""
        if not self.enabled or not self.sense:
            return

        try:
            self.sense.set_pixels([(0, 0, 0)] * 64)
            self.current_state = None
        except Exception as e:
            logger.error(f"Error clearing display: {e}")

    def is_available(self):
        """Check if Sense HAT is available."""
        return self.enabled and self.sense is not None
