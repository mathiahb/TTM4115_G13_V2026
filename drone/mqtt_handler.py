import json
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config_loader import get_mqtt_config, get_mqtt_topic

logger = logging.getLogger(__name__)


class DroneMQTTHandler:
    def __init__(self, drone, driver, config: dict, drone_id: str):
        self.drone = drone
        self.driver = driver
        self.config = config
        self.drone_id = drone_id

        mqtt_cfg = get_mqtt_config(self.config)
        self.broker_host = mqtt_cfg.get("broker_host", "localhost")
        self.broker_port = mqtt_cfg.get("broker_port", 1883)
        self.qos = mqtt_cfg.get("qos", 1)
        prefix = mqtt_cfg.get("client_id_prefix", "drone")

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{prefix}-{drone_id}",
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.telemetry_topic = get_mqtt_topic(self.config, "telemetry", self.drone_id)
        self.dispatch_topic = get_mqtt_topic(self.config, "dispatch", self.drone_id)
        self.events_topic = get_mqtt_topic(self.config, "events", self.drone_id)

    def connect(self):
        self.client.loop_start()
        self.client.connect_async(self.broker_host, self.broker_port)
        logger.info("Connecting to MQTT broker at %s:%d", self.broker_host, self.broker_port)

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self.client.subscribe([(self.dispatch_topic, self.qos)])
            logger.info("Subscribed to: %s", self.dispatch_topic)
        else:
            logger.error("MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning("Disconnected from MQTT broker: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            if msg.topic == self.dispatch_topic:
                data = json.loads(msg.payload.decode())
                logger.info("Received dispatch: order=%s", data.get("order_id"))
                self.driver.send("assign_delivery", "drone_stm", args=[data])
            else:
                logger.warning("Unexpected topic: %s", msg.topic)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse message: %s", e)
        except Exception as e:
            logger.error("Error handling message: %s", e)

    def publish_telemetry(self):
        if not self.drone or not self.drone.stm:
            return

        data = self.drone.get_telemetry_data()
        telemetry = {
            "drone_id": self.drone_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": data["location"],
            "battery_level": data["battery_level"],
            "max_payload": data["max_payload"],
            "state": data["state"],
        }

        self.client.publish(self.telemetry_topic, json.dumps(telemetry), qos=self.qos)
        logger.debug(
            "Telemetry: state=%s battery=%.1f%%",
            data["state"],
            data["battery_level"],
        )

    def publish_event(self, event_type: str, message: str):
        event = {
            "drone_id": self.drone_id,
            "order_id": self.drone.order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
        }

        self.client.publish(self.events_topic, json.dumps(event), qos=self.qos)
        logger.info("Event: %s order=%s", event_type, self.drone.order_id)
