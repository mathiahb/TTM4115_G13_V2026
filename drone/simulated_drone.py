import logging
import math
import stmpy

logger = logging.getLogger(__name__)


class SimulatedDrone:
    """A simulated drone that uses stmpy timers to move on a 2D map."""

    def __init__(self, config=None):
        self.config = config or {}
        self.at_warehouse = True
        self.battery_level = 100.0
        self.has_package = False
        self.stm = None

        self.position_x = 0.0
        self.position_y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0

        self.customer_x = None
        self.customer_y = None

        # MQTT handler reference (set by main)
        self.mqtt_handler = None

        # Sense HAT display reference (set by main)
        self.display = None

        # Load movement configuration
        movement_cfg = self.config.get('movement', {})
        self.travel_speed = movement_cfg.get('travel_speed', 3.0)
        self.battery_drain_per_second = movement_cfg.get('battery_drain_per_second', 1.5)
        self.arrival_threshold = movement_cfg.get('arrival_threshold', 0.25)
        self.movement_update_interval = movement_cfg.get('movement_update_interval', 500)

    def create_state_machine(self):
        transitions = [
            {'source': 'initial', 'target': 'standby', 'effect': 'on_enter_standby'},

            {'trigger': 'assignment_received', 'source': 'standby', 'target': 'travel_to_warehouse', 'effect': 'on_enter_travel_to_warehouse'},
            {'trigger': 'battery_depleted', 'source': 'standby', 'target': 'charge', 'effect': 'battery_depleted'},

            {'trigger': 'travel_timer', 'source': 'travel_to_warehouse', 'target': 'travel_to_warehouse', 'effect': 'update_travel_position'},
            {'trigger': 'arrived_at_destination', 'source': 'travel_to_warehouse', 'target': 'order_pickup', 'effect': 'on_exit_travel_to_warehouse; on_enter_order_pickup'},
            {'trigger': 'battery_depleted', 'source': 'travel_to_warehouse', 'target': 'charge', 'effect': 'on_exit_travel_to_warehouse; battery_depleted'},

            {'trigger': 'package_loaded', 'source': 'order_pickup', 'target': 'travel_to_customer', 'effect': 'package_loaded; on_enter_travel_to_customer'},

            {'trigger': 'travel_timer', 'source': 'travel_to_customer', 'target': 'travel_to_customer', 'effect': 'update_travel_position'},
            {'trigger': 'arrived_at_destination', 'source': 'travel_to_customer', 'target': 'deliver', 'effect': 'on_exit_travel_to_customer; on_enter_deliver'},
            {'trigger': 'battery_depleted', 'source': 'travel_to_customer', 'target': 'charge', 'effect': 'on_exit_travel_to_customer; battery_depleted'},

            {'trigger': 'delivery_completed', 'source': 'deliver', 'target': 'travel_return', 'effect': 'delivery_completed; on_enter_travel_return'},

            {'trigger': 'travel_timer', 'source': 'travel_return', 'target': 'travel_return', 'effect': 'update_travel_position'},
            {'trigger': 'arrived_at_destination', 'source': 'travel_return', 'target': 'standby', 'effect': 'on_exit_travel_return; on_enter_standby'},
            {'trigger': 'battery_depleted', 'source': 'travel_return', 'target': 'charge', 'effect': 'on_exit_travel_return; battery_depleted'},

            {'trigger': 'fully_charged', 'source': 'charge', 'target': 'standby', 'effect': 'fully_charged; on_enter_standby'},
        ]

        self.stm = stmpy.Machine(name='drone_stm', transitions=transitions, obj=self)
        return self.stm

    def set_customer_target(self, x, y):
        self.customer_x = x
        self.customer_y = y
        logger.info(f"Customer target set to ({x:.2f}, {y:.2f})")

    def on_enter_standby(self):
        logger.info("Drone entering STANDBY state")
        if self.display:
            self.display.set_state('standby')

    def on_enter_charge(self):
        logger.info("Drone entering CHARGE state - drone is charging")
        if self.display:
            self.display.set_state('charge')

    def on_enter_travel_to_warehouse(self):
        logger.info("Drone entering TRAVEL TO WAREHOUSE state")
        self.at_warehouse = False
        self.target_x = 0.0
        self.target_y = 0.0
        self._start_travel_timer()
        if self.display:
            self.display.set_state('travel_to_warehouse')

        if self._has_arrived():
            self.stm.send('arrived_at_destination')

    def on_exit_travel_to_warehouse(self):
        self._stop_travel_timer()

    def on_enter_order_pickup(self):
        logger.info("Drone entering ORDER PICKUP state")
        self.at_warehouse = True
        if self.display:
            self.display.set_state('order_pickup')

    def on_enter_travel_to_customer(self):
        logger.info("Drone entering TRAVEL TO CUSTOMER state")
        if self.customer_x is None or self.customer_y is None:
            logger.warning("No customer target set before departing to customer")
            self.target_x = self.position_x
            self.target_y = self.position_y
        else:
            self.target_x = self.customer_x
            self.target_y = self.customer_y

        self._start_travel_timer()
        if self.display:
            self.display.set_state('travel_to_customer')

        if self._has_arrived():
            self.stm.send('arrived_at_destination')

    def on_exit_travel_to_customer(self):
        self._stop_travel_timer()

    def on_enter_deliver(self):
        logger.info("Drone entering DELIVER state")
        if self.display:
            self.display.set_state('deliver')

    def on_enter_travel_return(self):
        logger.info("Drone entering TRAVEL RETURN state")
        self.at_warehouse = False
        self.target_x = 0.0
        self.target_y = 0.0
        self._start_travel_timer()
        if self.display:
            self.display.set_state('travel_return')

        if self._has_arrived():
            self.stm.send('arrived_at_destination')

    def on_exit_travel_return(self):
        self._stop_travel_timer()

    def battery_depleted(self):
        logger.warning("Battery depleted! Transitioning to CHARGE state.")
        self.battery_level = 0.0
        if self.display:
            self.display.show_event('battery_depleted')
        if self.mqtt_handler:
            self.mqtt_handler.on_battery_depleted()

    def fully_charged(self):
        logger.info("Battery fully charged")
        self.battery_level = 100.0
        if self.display:
            self.display.show_event('fully_charged')
        if self.mqtt_handler:
            self.mqtt_handler.on_fully_charged()

    def arrived_at_destination(self):
        logger.info("Drone reached its destination")
        if self.target_x == 0.0 and self.target_y == 0.0:
            self.at_warehouse = True
        if self.display:
            self.display.show_event('arrived')
        if self.mqtt_handler:
            self.mqtt_handler.on_arrived_at_destination()

    def package_loaded(self):
        logger.info("Package loaded on drone")
        self.has_package = True
        if self.display:
            self.display.pulse()
        if self.mqtt_handler:
            self.mqtt_handler.on_package_loaded()

    def delivery_completed(self):
        logger.info("Delivery completed")
        self.has_package = False
        if self.display:
            self.display.show_event('delivery_completed')
        if self.mqtt_handler:
            self.mqtt_handler.on_delivery_completed()

    def _start_travel_timer(self):
        if self.stm is not None:
            self.stm.start_timer('travel_timer', self.movement_update_interval)

    def _stop_travel_timer(self):
        if self.stm is not None:
            self.stm.stop_timer('travel_timer')

    def _has_arrived(self):
        return self.get_distance_to_target() <= self.arrival_threshold

    def get_distance_to_target(self):
        return math.hypot(self.target_x - self.position_x, self.target_y - self.position_y)

    def update_travel_position(self):
        distance = self.get_distance_to_target()
        if distance <= self.arrival_threshold:
            self.position_x = self.target_x
            self.position_y = self.target_y
            logger.info("Drone is already at the current target")
            self.stm.send('arrived_at_destination')
            return

        time_step = self.movement_update_interval / 1000.0
        step_distance = self.travel_speed * time_step

        dx = self.target_x - self.position_x
        dy = self.target_y - self.position_y
        ratio = min(1.0, step_distance / distance)
        self.position_x += dx * ratio
        self.position_y += dy * ratio

        drain_amount = self.battery_drain_per_second * time_step
        self.battery_level = max(0.0, self.battery_level - drain_amount)

        logger.debug(
            "Drone move update: pos=(%.2f, %.2f), target=(%.2f, %.2f), dist=%.2f, battery=%.1f%%",
            self.position_x,
            self.position_y,
            self.target_x,
            self.target_y,
            self.get_distance_to_target(),
            self.battery_level,
        )

        if self.battery_level <= 0.0:
            self.stm.send('battery_depleted')
            return

        if self._has_arrived():
            self.position_x = self.target_x
            self.position_y = self.target_y
            self.stm.send('arrived_at_destination')
            return

        # Restart the one-shot travel timer for the next update cycle.
        self._start_travel_timer()

    def get_status(self):
        return {
            'position': (self.position_x, self.position_y),
            'target': (self.target_x, self.target_y),
            'distance': self.get_distance_to_target(),
            'battery_level': self.battery_level,
            'has_package': self.has_package,
            'at_warehouse': self.at_warehouse,
        }
