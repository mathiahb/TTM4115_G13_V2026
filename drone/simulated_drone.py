import logging
import math

import stmpy

from config_loader import (
    get_battery_config,
    get_charging_config,
    get_initial_battery,
    get_initial_location,
    get_max_payload,
    get_simulation_config,
)

logger = logging.getLogger(__name__)

SIM_TICK_MS = 500
PICKUP_TIME_MS = 2000


class SimulatedDrone:
    """Simulated drone using stmpy state machine with timer-driven movement."""

    def __init__(self, config=None, mqtt_handler=None, display=None):
        self.config = config or {}
        self.mqtt_handler = mqtt_handler
        self.display = display
        self.stm = None
        self.driver = None

        self.location = get_initial_location(self.config)
        self.home_location = dict(self.location)
        self.battery_level = get_initial_battery(self.config)
        self.max_payload = get_max_payload(self.config)
        self.state = "standby"

        self.route = []
        self.route_step = 0
        self.order_id = None
        self.resume_target = "standby"

        sim_cfg = get_simulation_config(self.config)
        self.battery_drain_rate = sim_cfg.get("battery_drain_per_second", 0.01)
        self.movement_speed = sim_cfg.get("movement_speed_mps", 5.0)

        bat_cfg = get_battery_config(self.config)
        self.fully_charged_threshold = bat_cfg.get("fully_charged_threshold", 95.0)

        chg_cfg = get_charging_config(self.config)
        full_time_min = chg_cfg.get("full_charge_time_minutes", 30)
        self.charge_rate = 100.0 / (full_time_min * 60)

    def create_state_machine(self):
        states = [
            {"name": "standby", "entry": "on_enter_standby"},
            {
                "name": "charging",
                "entry": "on_enter_charging",
                "exit": "on_exit_charging",
            },
            {
                "name": "travel_to_warehouse",
                "entry": "on_enter_travel_to_warehouse",
                "exit": "on_exit_travel",
            },
            {
                "name": "order_pickup",
                "entry": "on_enter_order_pickup",
                "exit": "on_exit_order_pickup",
            },
            {
                "name": "travel_to_customer",
                "entry": "on_enter_travel_to_customer",
                "exit": "on_exit_travel",
            },
            {"name": "deliver", "entry": "on_enter_deliver"},
            {
                "name": "travel_return",
                "entry": "on_enter_travel_return",
                "exit": "on_exit_travel",
            },
        ]

        transitions = [
            {"source": "initial", "target": "standby", "effect": "on_init"},
            {
                "trigger": "assign_delivery",
                "source": "standby",
                "target": "travel_to_warehouse",
                "effect": "on_dispatch(*)",
            },
            {
                "trigger": "sim_tick",
                "source": "travel_to_warehouse",
                "target": "travel_to_warehouse",
                "effect": "on_warehouse_tick",
            },
            {
                "trigger": "arrived_at_shop",
                "source": "travel_to_warehouse",
                "target": "order_pickup",
            },
            {
                "trigger": "battery_depleted",
                "source": "travel_to_warehouse",
                "target": "charging",
            },
            {
                "trigger": "pickup_done",
                "source": "order_pickup",
                "target": "travel_to_customer",
                "effect": "on_pickup_done",
            },
            {
                "trigger": "sim_tick",
                "source": "travel_to_customer",
                "target": "travel_to_customer",
                "effect": "on_customer_tick",
            },
            {
                "trigger": "arrived_at_destination",
                "source": "travel_to_customer",
                "target": "deliver",
            },
            {
                "trigger": "battery_depleted",
                "source": "travel_to_customer",
                "target": "charging",
            },
            {
                "trigger": "delivery_completed_signal",
                "source": "deliver",
                "target": "travel_return",
            },
            {
                "trigger": "sim_tick",
                "source": "travel_return",
                "target": "travel_return",
                "effect": "on_return_tick",
            },
            {
                "trigger": "arrived_home",
                "source": "travel_return",
                "target": "standby",
            },
            {
                "trigger": "battery_depleted",
                "source": "travel_return",
                "target": "charging",
            },
            {
                "trigger": "sim_tick",
                "source": "charging",
                "target": "charging",
                "effect": "on_charge_tick",
            },
            {
                "trigger": "resume_to_warehouse",
                "source": "charging",
                "target": "travel_to_warehouse",
            },
            {
                "trigger": "resume_to_customer",
                "source": "charging",
                "target": "travel_to_customer",
            },
            {
                "trigger": "resume_to_return",
                "source": "charging",
                "target": "travel_return",
            },
            {
                "trigger": "resume_to_standby",
                "source": "charging",
                "target": "standby",
            },
        ]

        self.stm = stmpy.Machine(
            name="drone_stm",
            transitions=transitions,
            states=states,
            obj=self,
        )
        return self.stm

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(min(1.0, a)))

    def _current_target(self):
        if self.route_step < len(self.route):
            return self.route[self.route_step]
        return None

    def _dist_to_target(self):
        target = self._current_target()
        if not target:
            return float("inf")
        return self._haversine(
            self.location["lat"],
            self.location["lon"],
            target["lat"],
            target["lon"],
        )

    def _move_step(self, dt=0.5):
        target = self._current_target()
        if not target:
            return True
        dist = self._dist_to_target()
        step = self.movement_speed * dt
        if dist <= step:
            self.location["lat"] = target["lat"]
            self.location["lon"] = target["lon"]
            return True
        ratio = step / dist
        self.location["lat"] += (target["lat"] - self.location["lat"]) * ratio
        self.location["lon"] += (target["lon"] - self.location["lon"]) * ratio
        return False

    def _drain_battery(self, dt=0.5):
        self.battery_level = max(0, self.battery_level - self.battery_drain_rate * dt)

    def _charge_step(self, dt=0.5):
        self.battery_level = min(100, self.battery_level + self.charge_rate * dt)

    def _publish_event(self, event_type, message=""):
        if self.mqtt_handler:
            self.mqtt_handler.publish_event(event_type, message)

    def on_init(self):
        logger.info(
            "Drone initialized at (%.4f, %.4f) battery=%.1f%%",
            self.location["lat"],
            self.location["lon"],
            self.battery_level,
        )

    def on_dispatch(self, payload):
        self.order_id = payload["order_id"]
        self.route = payload["route"]
        self.route_step = 1
        logger.info("Dispatch received: order=%s", self.order_id)

    def on_enter_travel_to_warehouse(self):
        self.state = "travel_to_warehouse"
        logger.info("Drone entering TRAVEL TO WAREHOUSE")
        self.stm.start_timer("sim_tick", SIM_TICK_MS)
        if self.display:
            self.display.set_state("travel_to_warehouse")

    def on_exit_travel(self):
        self.stm.stop_timer("sim_tick")

    def on_warehouse_tick(self):
        arrived = self._move_step()
        self._drain_battery()

        if self.battery_level <= 0:
            self.resume_target = "travel_to_warehouse"
            self._publish_event("battery_depleted", "Battery depleted during travel")
            self.stm.send("battery_depleted")
            return

        if arrived:
            self._publish_event("arrived", "Arrived at pickup")
            self.stm.send("arrived_at_shop")
            return

    def on_enter_order_pickup(self):
        self.state = "order_pickup"
        logger.info("Drone entering ORDER PICKUP")
        self.stm.start_timer("pickup_done", PICKUP_TIME_MS)
        if self.display:
            self.display.set_state("order_pickup")

    def on_exit_order_pickup(self):
        self.stm.stop_timer("pickup_done")

    def on_pickup_done(self):
        self._publish_event("package_loaded", "Package loaded at warehouse")
        self.route_step = 2

    def on_enter_travel_to_customer(self):
        self.state = "travel_to_customer"
        logger.info("Drone entering TRAVEL TO CUSTOMER")
        self.stm.start_timer("sim_tick", SIM_TICK_MS)
        if self.display:
            self.display.set_state("travel_to_customer")

    def on_customer_tick(self):
        arrived = self._move_step()
        self._drain_battery()

        if self.battery_level <= 0:
            self.resume_target = "travel_to_customer"
            self._publish_event("battery_depleted", "Battery depleted during travel")
            self.stm.send("battery_depleted")
            return

        if arrived:
            self.stm.send("arrived_at_destination")
            return

    def on_enter_deliver(self):
        self.state = "deliver"
        logger.info("Drone entering DELIVER")
        self._publish_event("delivery_completed", "Package delivered to customer")
        if self.display:
            self.display.set_state("deliver")
        self.stm.send("delivery_completed_signal")

    def on_enter_travel_return(self):
        self.state = "travel_return"
        logger.info("Drone entering TRAVEL RETURN")
        self.route = [
            {"lat": self.location["lat"], "lon": self.location["lon"]},
            {"lat": self.home_location["lat"], "lon": self.home_location["lon"]},
        ]
        self.route_step = 1
        self.stm.start_timer("sim_tick", SIM_TICK_MS)
        if self.display:
            self.display.set_state("travel_return")

    def on_return_tick(self):
        arrived = self._move_step()
        self._drain_battery()

        if self.battery_level <= 0:
            self.resume_target = "travel_return"
            self._publish_event("battery_depleted", "Battery depleted during return")
            self.stm.send("battery_depleted")
            return

        if arrived:
            self.stm.send("arrived_home")
            return

    def on_enter_standby(self):
        self.state = "standby"
        self.order_id = None
        self.route = []
        self.route_step = 0
        logger.info(
            "Drone entering STANDBY at (%.4f, %.4f)",
            self.location["lat"],
            self.location["lon"],
        )
        if self.display:
            self.display.set_state("standby")

    def on_enter_charging(self):
        self.state = "charging"
        logger.info("Drone entering CHARGING (%.1f%%)", self.battery_level)
        self.stm.start_timer("sim_tick", SIM_TICK_MS)
        if self.display:
            self.display.set_state("charge")

    def on_exit_charging(self):
        self.stm.stop_timer("sim_tick")

    def on_charge_tick(self):
        self._charge_step()

        if self.battery_level >= self.fully_charged_threshold:
            self._publish_event("fully_charged", "Battery fully charged")
            if self.display:
                self.display.show_event("fully_charged")
            resume_map = {
                "travel_to_warehouse": "resume_to_warehouse",
                "travel_to_customer": "resume_to_customer",
                "travel_return": "resume_to_return",
                "standby": "resume_to_standby",
            }
            signal = resume_map.get(self.resume_target, "resume_to_standby")
            self.stm.send(signal)

    def get_telemetry_data(self):
        return {
            "location": {
                "lat": self.location["lat"],
                "lon": self.location["lon"],
                "gps_valid": self.location["gps_valid"],
            },
            "battery_level": self.battery_level,
            "max_payload": self.max_payload,
            "state": self.state,
        }
