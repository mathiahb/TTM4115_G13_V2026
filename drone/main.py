import json
import logging
import math
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import stmpy

from config_loader import (
    get_battery_config,
    get_charging_config,
    get_drone_id,
    get_initial_battery,
    get_initial_location,
    get_max_payload,
    get_mqtt_config,
    get_mqtt_topic,
    get_simulation_config,
    get_telemetry_interval,
    load_config,
    parse_args,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("drone")


class DroneLogic:
    """Drone business logic bound to the stmpy state machine."""

    def __init__(
        self,
        drone_id: str,
        config: dict,
        mqtt_client: mqtt.Client,
    ):
        self.drone_id = drone_id
        self.config = config
        self.mqtt_client = mqtt_client
        self.stm: stmpy.Machine | None = None
        self.driver: stmpy.Driver | None = None

        self.location = get_initial_location(config)
        self.home_location = dict(self.location)
        self.battery_level = get_initial_battery(config)
        self.max_payload = get_max_payload(config)
        self.state = "standby"

        self.route: list[dict] = []
        self.route_step = 0
        self.order_id: str | None = None
        self.resume_target = "standby"

        sim_cfg = get_simulation_config(config)
        self.battery_drain_rate = sim_cfg.get("battery_drain_per_second", 0.01)
        self.movement_speed = sim_cfg.get("movement_speed_mps", 5.0)

        bat_cfg = get_battery_config(config)
        self.charging_threshold = bat_cfg.get("charging_threshold", 30.0)
        self.fully_charged_threshold = bat_cfg.get("fully_charged_threshold", 95.0)

        chg_cfg = get_charging_config(config)
        full_time_min = chg_cfg.get("full_charge_time_minutes", 30)
        self.charge_rate = 100.0 / (full_time_min * 60)

        self._sim_thread: threading.Thread | None = None
        self._sim_start = threading.Event()
        self._sim_stop = threading.Event()
        self._sim_action = None

    # --- Simulation thread management ---

    def _ensure_sim_thread(self):
        if self._sim_thread is None or not self._sim_thread.is_alive():
            self._sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
            self._sim_thread.start()

    def _sim_loop(self):
        while not self._sim_stop.is_set():
            self._sim_start.wait()
            if self._sim_stop.is_set():
                break
            self._sim_start.clear()
            if self._sim_action:
                try:
                    self._sim_action()
                except Exception:
                    logger.exception("Simulation action failed")

    def _start_sim(self, action):
        self._sim_action = action
        self._sim_start.set()
        self._ensure_sim_thread()

    # --- Helpers ---

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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

    def _current_target(self) -> dict | None:
        if self.route_step < len(self.route):
            return self.route[self.route_step]
        return None

    def _dist_to_target(self) -> float:
        target = self._current_target()
        if not target:
            return float("inf")
        return self._haversine(
            self.location["lat"],
            self.location["lon"],
            target["lat"],
            target["lon"],
        )

    def _move_step(self, dt: float = 0.5) -> bool:
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

    def _drain_battery(self, dt: float = 0.5):
        self.battery_level = max(0, self.battery_level - self.battery_drain_rate * dt)

    def _charge_step(self, dt: float = 0.5):
        self.battery_level = min(100, self.battery_level + self.charge_rate * dt)

    def _publish_event(self, event_type: str, message: str = ""):
        payload = {
            "drone_id": self.drone_id,
            "order_id": self.order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
        }
        topic = get_mqtt_topic(self.config, "events", drone_id=self.drone_id)
        self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
        logger.info("Event: %s order=%s", event_type, self.order_id)

    # --- Simulation actions (run in sim thread) ---

    def _sim_travel(self):
        while not self._sim_stop.is_set():
            arrived = self._move_step()
            self._drain_battery()

            if self.battery_level <= 0:
                target = self._current_target()
                if target and target.get("type") == "destination":
                    self.resume_target = "travel_to_customer"
                else:
                    self.resume_target = "travel_to_warehouse"
                self._publish_event("battery_depleted", "Battery depleted during travel")
                self.driver.send("battery_depleted", self.stm.id)
                return

            if arrived:
                target = self._current_target()
                if target and target.get("type") == "destination":
                    self.driver.send("arrived_at_destination", self.stm.id)
                else:
                    self._publish_event("arrived", "Arrived at pickup")
                    self.driver.send("arrived_at_shop", self.stm.id)
                return

            time.sleep(0.5)

    def _sim_return(self):
        while not self._sim_stop.is_set():
            arrived = self._move_step()
            self._drain_battery()

            if self.battery_level <= 0:
                self.resume_target = "travel_return"
                self._publish_event("battery_depleted", "Battery depleted during return")
                self.driver.send("battery_depleted", self.stm.id)
                return

            if arrived:
                self.driver.send("arrived_home", self.stm.id)
                return

            time.sleep(0.5)

    def _sim_pickup(self):
        time.sleep(2.0)
        if self._sim_stop.is_set():
            return
        self._publish_event("package_loaded", "Package loaded at warehouse")
        self.route_step = 2
        self.driver.send("package_loaded_signal", self.stm.id)

    def _sim_charge(self):
        while self.battery_level < self.fully_charged_threshold and not self._sim_stop.is_set():
            time.sleep(0.5)
            self._charge_step()
        self._publish_event("fully_charged", "Battery fully charged")
        resume_signals = {
            "travel_to_warehouse": "resume_to_warehouse",
            "travel_to_customer": "resume_to_customer",
            "travel_return": "resume_to_return",
            "standby": "resume_to_standby",
        }
        signal = resume_signals.get(self.resume_target, "resume_to_standby")
        self.driver.send(signal, self.stm.id)

    # --- State machine entry actions ---

    def on_init(self):
        logger.info(
            "Drone %s initialized at (%.4f, %.4f) battery=%.1f%%",
            self.drone_id,
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
        self._start_sim(self._sim_travel)

    def on_enter_order_pickup(self):
        self.state = "order_pickup"
        self._start_sim(self._sim_pickup)

    def on_enter_travel_to_customer(self):
        self.state = "travel_to_customer"
        self._start_sim(self._sim_travel)

    def on_enter_deliver(self):
        self.state = "deliver"
        self._publish_event("delivery_completed", "Package delivered to customer")
        logger.info("Package delivered, order=%s", self.order_id)
        self.driver.send("delivery_completed_signal", self.stm.id)

    def on_enter_travel_return(self):
        self.state = "travel_return"
        self.route = [
            {"lat": self.location["lat"], "lon": self.location["lon"]},
            {"lat": self.home_location["lat"], "lon": self.home_location["lon"]},
        ]
        self.route_step = 1
        self._start_sim(self._sim_return)

    def on_enter_standby(self):
        self.state = "standby"
        self.order_id = None
        self.route = []
        self.route_step = 0
        logger.info("Standing by at (%.4f, %.4f)", self.location["lat"], self.location["lon"])

    def on_enter_charging(self):
        self.state = "charging"
        logger.info("Charging battery (%.1f%%)", self.battery_level)
        self._start_sim(self._sim_charge)

    def on_resume_travel(self):
        self.state = self.resume_target
        self._start_sim(self._sim_travel)

    def on_resume_return(self):
        self.state = "travel_return"
        self._start_sim(self._sim_return)

    def evaluate_charge_resume(self) -> str:
        return self.resume_target


def create_drone_machine(obj: DroneLogic) -> stmpy.Machine:
    states = [
        {"name": "standby", "entry": "on_enter_standby"},
        {"name": "charging", "entry": "on_enter_charging"},
        {"name": "travel_to_warehouse", "entry": "on_enter_travel_to_warehouse"},
        {"name": "order_pickup", "entry": "on_enter_order_pickup"},
        {"name": "travel_to_customer", "entry": "on_enter_travel_to_customer"},
        {"name": "deliver", "entry": "on_enter_deliver"},
        {"name": "travel_return", "entry": "on_enter_travel_return"},
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
            "trigger": "package_loaded_signal",
            "source": "order_pickup",
            "target": "travel_to_customer",
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
            "trigger": "resume_to_warehouse",
            "source": "charging",
            "target": "travel_to_warehouse",
            "effect": "on_resume_travel",
        },
        {
            "trigger": "resume_to_customer",
            "source": "charging",
            "target": "travel_to_customer",
            "effect": "on_resume_travel",
        },
        {
            "trigger": "resume_to_return",
            "source": "charging",
            "target": "travel_return",
            "effect": "on_resume_return",
        },
        {
            "trigger": "resume_to_standby",
            "source": "charging",
            "target": "standby",
        },
    ]

    return stmpy.Machine(
        name="drone_stm",
        transitions=transitions,
        states=states,
        obj=obj,
    )


def main():
    args = parse_args()
    config = load_config(args.config)
    drone_id = get_drone_id(config, args.drone_id)

    mqtt_cfg = get_mqtt_config(config)
    broker_host = mqtt_cfg.get("broker_host", "localhost")
    broker_port = mqtt_cfg.get("broker_port", 1883)
    qos = mqtt_cfg.get("qos", 1)
    prefix = mqtt_cfg.get("client_id_prefix", "drone")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{prefix}-{drone_id}",
    )

    driver = stmpy.Driver()
    drone = DroneLogic(drone_id, config, client)
    drone.driver = driver

    machine = create_drone_machine(drone)
    drone.stm = machine
    driver.add_machine(machine)
    driver.start(keep_active=True)

    def on_connect(cl, userdata, flags, reason_code, properties):
        if reason_code == 0:
            dispatch_topic = get_mqtt_topic(config, "dispatch", drone_id=drone_id)
            cl.subscribe([(dispatch_topic, qos)])
            logger.info("Connected to broker, subscribed to %s", dispatch_topic)
        else:
            logger.error("MQTT connection failed: %s", reason_code)

    def on_message(cl, userdata, msg):
        logger.debug("MQTT message on topic: %s", msg.topic)
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid payload on %s", msg.topic)
            return

        if "/dispatch" in msg.topic:
            logger.info("Dispatch received on %s: order=%s", msg.topic, payload.get("order_id"))
            driver.send("assign_delivery", "drone_stm", args=[payload])

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect_async(broker_host, broker_port)
    client.loop_start()

    stop_event = threading.Event()

    def telemetry_loop():
        interval = get_telemetry_interval(config)
        while not stop_event.is_set():
            payload = {
                "drone_id": drone_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "location": {
                    "lat": drone.location["lat"],
                    "lon": drone.location["lon"],
                    "gps_valid": drone.location["gps_valid"],
                },
                "battery_level": drone.battery_level,
                "max_payload": drone.max_payload,
                "state": drone.state,
            }
            topic = get_mqtt_topic(config, "telemetry", drone_id=drone_id)
            client.publish(topic, json.dumps(payload), qos=qos)
            logger.debug(
                "Telemetry: state=%s battery=%.1f%%",
                drone.state,
                drone.battery_level,
            )
            stop_event.wait(interval)

    telem_thread = threading.Thread(target=telemetry_loop, daemon=True)
    telem_thread.start()

    logger.info("Drone %s running. Press Ctrl+C to stop.", drone_id)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_event.set()
        drone._sim_stop.set()
        client.loop_stop()
        client.disconnect()
        driver.stop()


if __name__ == "__main__":
    main()
