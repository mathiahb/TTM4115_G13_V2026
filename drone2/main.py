import logging
import threading
import time

import stmpy

from config_loader import (
    get_battery_params,
    get_charging_params,
    get_drone_id,
    get_home_location,
    get_initial_battery,
    get_max_payload,
    get_sim_tick_ms,
    get_simulation_params,
    get_telemetry_interval,
    load_config,
    parse_args,
)
from display import Display
from mqtt_handler import DroneMQTTHandler
from simulator import charge_battery, compute_charge_rate, drain_battery, move_towards

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("drone")


class DroneSTM:
    def __init__(self, config: dict):
        self.driver = None
        self.stm = None
        self.mqtt_handler: DroneMQTTHandler | None = None
        self.display: Display | None = None

        self.drone_id: str = config.get("drone", {}).get("drone_id", "1")
        self.state: str = "standby"
        self.order_id: str | None = None
        self.is_express: bool = False

        home = get_home_location(config)
        self.home_location: dict = home
        self.location: dict = {**home, "gps_valid": True}
        self.battery_level: float = get_initial_battery(config)
        self.max_payload: float = get_max_payload(config)

        self.route: list[dict] = []
        self.route_step: int = 0

        sim = get_simulation_params(config)
        self.base_drain_rate: float = sim.get("battery_drain_per_second", 0.5)
        self.base_movement_speed: float = sim.get("movement_speed_mps", 50.0)
        self.express_speed_mult: float = sim.get("express_speed_multiplier", 2.0)
        self.express_drain_mult: float = sim.get("express_drain_multiplier", 3.0)

        bat = get_battery_params(config)
        self.fully_charged_threshold: float = bat.get("fully_charged_threshold", 95.0)

        chg = get_charging_params(config)
        full_time_min = chg.get("full_charge_time_minutes", 0.6)
        self.charge_rate: float = compute_charge_rate(full_time_min)

        self.sim_tick_ms: int = get_sim_tick_ms(config)

        self.current_action: str | None = None
        self.action_timer_id: str | None = None

    def build_machine(self) -> stmpy.Machine:
        states = [
            {"name": "standby", "entry": "on_enter_standby"},
            {"name": "travel", "entry": "on_enter_travel", "exit": "on_exit_travel"},
            {"name": "execute", "entry": "on_enter_execute", "exit": "on_exit_execute"},
            {"name": "error", "entry": "on_enter_error"},
        ]

        transitions = [
            {"source": "initial", "target": "standby"},

            {"trigger": "assign_delivery", "source": "standby", "target": "travel", "effect": "on_dispatch(*)"},

            {"trigger": "sim_tick", "source": "travel", "target": "travel", "effect": "on_travel_tick"},
            {"trigger": "arrived_at_waypoint", "source": "travel", "target": "execute"},
            {"trigger": "error", "source": "travel", "target": "error", "effect": "on_error('battery_depleted')"},

            {"trigger": "action_done", "source": "execute", "target": "travel", "effect": "on_next_waypoint"},
            {"trigger": "to_standby", "source": "execute", "target": "standby"},
            {"trigger": "sim_tick", "source": "execute", "target": "execute", "effect": "on_execute_tick"},
            {"trigger": "pickup_done", "source": "execute", "target": "execute", "effect": "on_pickup_done"},
            {"trigger": "error", "source": "execute", "target": "error", "effect": "on_error('unknown')"},

            {"trigger": "error", "source": "standby", "target": "error", "effect": "on_error('unknown')"},
            {"trigger": "fixed", "source": "error", "target": "standby", "effect": "on_reset"},
        ]

        self.stm = stmpy.Machine(
            name="drone_stm",
            transitions=transitions,
            states=states,
            obj=self,
        )
        return self.stm

    @property
    def movement_speed(self) -> float:
        return self.base_movement_speed * (self.express_speed_mult if self.is_express else 1.0)

    @property
    def drain_rate(self) -> float:
        return self.base_drain_rate * (self.express_drain_mult if self.is_express else 1.0)

    def _publish_event(self, event_type: str, message: str = ""):
        if self.mqtt_handler:
            self.mqtt_handler.publish_event(event_type, message)

    def _current_waypoint(self) -> dict | None:
        if self.route_step < len(self.route):
            return self.route[self.route_step]
        return None

    def _has_more_waypoints(self) -> bool:
        return self.route_step + 1 < len(self.route)

    def _finish_action(self):
        if self._has_more_waypoints():
            self.stm.send("action_done")
        else:
            self.stm.send("to_standby")

    def on_dispatch(self, payload: dict):
        self.order_id = payload.get("order_id")
        self.route = payload.get("route", [])
        self.route_step = 0
        priority = payload.get("package_info", {}).get("priority", "standard").lower()
        self.is_express = priority in ("express", "priority")
        logger.info("Dispatch: order=%s priority=%s waypoints=%d", self.order_id, priority, len(self.route))

    def on_enter_standby(self):
        self.state = "standby"
        self.order_id = None
        self.route = []
        self.route_step = 0
        self.is_express = False
        self.location = {**self.home_location, "gps_valid": True}
        logger.info("STANDBY at (%.4f, %.4f)", self.location["lat"], self.location["lon"])
        if self.display:
            self.display.set_state("standby")

    def on_enter_travel(self):
        self.state = "travel"
        self.route_step += 1
        logger.info("TRAVEL to waypoint %d/%d express=%s", self.route_step, len(self.route) - 1, self.is_express)
        self.stm.start_timer("sim_tick", self.sim_tick_ms)
        if self.display:
            self.display.set_state("travel")

    def on_exit_travel(self):
        self.stm.stop_timer("sim_tick")

    def on_travel_tick(self):
        target = self._current_waypoint()
        if not target:
            self.stm.send("arrived_at_waypoint")
            return

        arrived = move_towards(self.location, target, self.movement_speed)
        self.battery_level = drain_battery(self.battery_level, self.drain_rate)

        if self.battery_level <= 0:
            self._publish_event("battery_depleted", "Battery depleted during travel")
            self.stm.send("error")
            return

        if arrived:
            logger.info("Arrived at waypoint %d", self.route_step)
            self.stm.send("arrived_at_waypoint")

    def on_enter_execute(self):
        self.state = "execute"
        wp = self._current_waypoint()
        self.current_action = (wp.get("action") or "none").lower() if wp else "none"
        logger.info("EXECUTE action=%s at waypoint %d", self.current_action, self.route_step)
        self.stm.start_timer("sim_tick", self.sim_tick_ms)
        if self.display:
            self.display.set_state(self.current_action)

        if self.current_action == "deliver":
            self._publish_event("delivery_completed", "Package delivered")
            self._finish_action()
        elif self.current_action == "pickup":
            self.action_timer_id = "pickup_timer"
            self.stm.start_timer(self.action_timer_id, 2000)
        elif self.current_action == "charge":
            logger.info("Charging at waypoint (%.1f%%)", self.battery_level)
        elif self.current_action == "none":
            self._finish_action()

    def on_execute_tick(self):
        if self.current_action == "charge":
            self.battery_level = charge_battery(self.battery_level, self.charge_rate)
            if self.battery_level >= self.fully_charged_threshold:
                self._publish_event("fully_charged", "Battery fully charged")
                self._finish_action()

    def on_pickup_done(self):
        self._publish_event("package_loaded", "Package loaded at warehouse")
        self._finish_action()

    def on_exit_execute(self):
        self.stm.stop_timer("sim_tick")
        if self.action_timer_id:
            self.stm.stop_timer(self.action_timer_id)
            self.action_timer_id = None
        self.current_action = None

    def on_next_waypoint(self):
        logger.info("Moving to next waypoint")

    def on_error(self, error_type: str):
        logger.error("ERROR: %s at (%.4f, %.4f) battery=%.1f%%", error_type, self.location["lat"], self.location["lon"], self.battery_level)
        self._publish_event("error", f"Drone error: {error_type}")
        if self.display:
            self.display.set_state("error")

    def on_enter_error(self):
        self.state = "error"
        logger.info("ERROR state - waiting for manual fix")

    def on_reset(self):
        logger.info("Resetting drone to standby")
        self.battery_level = 100.0
        self.location = {**self.home_location, "gps_valid": True}
        self.order_id = None
        self.route = []
        self.route_step = 0
        self.is_express = False

    def get_telemetry_data(self) -> dict:
        return {
            "location": {
                "lat": self.location["lat"],
                "lon": self.location["lon"],
                "gps_valid": self.location.get("gps_valid", True),
            },
            "battery_level": self.battery_level,
            "max_payload": self.max_payload,
            "state": self.state,
        }


def main():
    args = parse_args()
    config = load_config(args.config)
    drone_id = get_drone_id(config, args.drone_id)

    driver = stmpy.Driver()

    drone = DroneSTM(config)
    drone.drone_id = drone_id
    machine = drone.build_machine()
    drone.driver = driver

    display = Display(config)
    drone.display = display

    mqtt_handler = DroneMQTTHandler(drone=drone, driver=driver, config=config, drone_id=drone_id)
    drone.mqtt_handler = mqtt_handler

    driver.add_machine(machine)
    driver.start(keep_active=True)

    mqtt_handler.connect()

    stop_event = threading.Event()

    def telemetry_loop():
        interval = get_telemetry_interval(config)
        while not stop_event.is_set():
            mqtt_handler.publish_telemetry()
            stop_event.wait(interval)

    def wait_for_fix():
        while not stop_event.is_set():
            try:
                input()
            except EOFError:
                stop_event.wait(1)
                continue
            if drone.state == "error":
                logger.info("Manual fix triggered")
                drone.stm.send("fixed")

    telem_thread = threading.Thread(target=telemetry_loop, daemon=True)
    telem_thread.start()

    fix_thread = threading.Thread(target=wait_for_fix, daemon=True)
    fix_thread.start()

    logger.info("Drone %s running. Press Enter to fix error. Ctrl+C to stop.", drone_id)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_event.set()
        mqtt_handler.stop()
        driver.stop()


if __name__ == "__main__":
    main()
