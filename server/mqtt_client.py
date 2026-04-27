import json
import logging
import threading
from collections.abc import Callable

import paho.mqtt.client as mqtt

from config_loader import get_mqtt_config, get_mqtt_topic

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(
        self,
        config: dict,
        drones: dict,
        on_drone_event: Callable | None = None,
    ):
        self.config = config
        self.drones = drones
        self.on_drone_event = on_drone_event

        mqtt_cfg = get_mqtt_config(config)
        self.broker_host: str = mqtt_cfg.get("broker_host", "localhost")
        self.broker_port: int = mqtt_cfg.get("broker_port", 1883)
        self.qos: int = mqtt_cfg.get("qos", 1)

        prefix = mqtt_cfg.get("client_id_prefix", "server")
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{prefix}-{id(self)}",
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self._lock = threading.Lock()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(
                "Connected to MQTT broker %s:%d",
                self.broker_host,
                self.broker_port,
            )
            telemetry_topic = get_mqtt_topic(self.config, "telemetry", drone_id="+")
            events_topic = get_mqtt_topic(self.config, "events", drone_id="+")
            client.subscribe([(telemetry_topic, self.qos), (events_topic, self.qos)])
            logger.info("Subscribed to %s and %s", telemetry_topic, events_topic)
        else:
            logger.error("MQTT connection failed: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid payload on %s", msg.topic)
            return

        if "/telemetry" in msg.topic:
            self._handle_telemetry(payload)
        elif "/events" in msg.topic:
            self._handle_event(payload)

    def _handle_telemetry(self, data: dict):
        try:
            drone_id = data["drone_id"]
            location = data["location"]
            battery_level = data["battery_level"]
            state = data["state"]
            gps_valid = location["gps_valid"]
            lat = location["lat"]
            lon = location["lon"]
        except (KeyError, TypeError) as e:
            logger.warning("Malformed telemetry payload, missing %s", e)
            return

        key = f"Drone{drone_id}"
        with self._lock:
            if key in self.drones:
                drone = self.drones[key]
                drone["location"]["lat"] = lat
                drone["location"]["lon"] = lon
                drone["location"]["gps_valid"] = gps_valid
                drone["battery_level"] = battery_level
                drone["state"] = state
                if "max_payload" in data:
                    drone["max_payload"] = data["max_payload"]

        logger.debug(
            "Telemetry drone=%s state=%s battery=%.1f",
            drone_id,
            state,
            battery_level,
        )

    def _handle_event(self, data: dict):
        try:
            event_type = data["event_type"]
            drone_id = data["drone_id"]
        except (KeyError, TypeError) as e:
            logger.warning("Malformed event payload, missing %s", e)
            return

        order_id = data.get("order_id")
        message = data.get("message", "")

        logger.info(
            "Event drone=%s type=%s order=%s msg=%s",
            drone_id,
            event_type,
            order_id,
            message,
        )

        if self.on_drone_event:
            self.on_drone_event(event_type, drone_id, order_id, data)

    def publish_dispatch(self, drone_id: str, payload: dict):
        topic = get_mqtt_topic(self.config, "dispatch", drone_id=drone_id)
        self.client.publish(topic, json.dumps(payload), qos=self.qos)
        logger.info("Dispatched to drone %s on %s", drone_id, topic)

    def start(self):
        self.client.loop_start()
        self.client.connect_async(self.broker_host, self.broker_port)

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
