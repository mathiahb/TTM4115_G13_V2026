import json
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config_loader import get_mqtt_config, get_mqtt_topic

logger = logging.getLogger(__name__)


class DroneMQTTHandler:
    """Handles MQTT communication for the drone using paho-mqtt.

    Manages telemetry publishing, event publishing, and dispatch message handling.
    """

    def __init__(self, drone, driver, config=None, drone_id="1"):
        self.drone = drone
        self.driver = driver
        self.config = config or {}
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
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.telemetry_topic = get_mqtt_topic(self.config, "telemetry", self.drone_id)
        self.dispatch_topic = get_mqtt_topic(self.config, "dispatch", self.drone_id)
        self.events_topic = get_mqtt_topic(self.config, "events", self.drone_id)

    def connect(self):
        """Connect to MQTT broker asynchronously."""
        self.client.loop_start()
        self.client.connect_async(self.broker_host, self.broker_port)
        logger.info("Connecting to MQTT broker at %s:%d", self.broker_host, self.broker_port)

    def stop(self):
        """Stop the MQTT client."""
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback when connected to MQTT broker."""
        if reason_code == 0:
            logger.info("Connected to MQTT broker successfully")
            self.client.subscribe([(self.dispatch_topic, self.qos)])
            logger.info("Subscribed to dispatch topic: %s", self.dispatch_topic)
        else:
            logger.error("Failed to connect to MQTT broker: %s", reason_code)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback when disconnected from MQTT broker."""
        logger.warning("Disconnected from MQTT broker: %s", reason_code)

    def on_message(self, client, userdata, msg):
        """Callback when a message is received."""
        try:
            if msg.topic == self.dispatch_topic:
                self.handle_dispatch(json.loads(msg.payload.decode()))
            else:
                logger.warning("Received message on unexpected topic: %s", msg.topic)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse MQTT message: %s", e)
        except Exception as e:
            logger.error("Error handling MQTT message: %s", e)

    def handle_dispatch(self, dispatch_data):
        """Handle incoming dispatch message by forwarding the full payload to the state machine."""
        logger.info(
            "Received dispatch: order=%s",
            dispatch_data.get("order_id"),
        )
        self.driver.send("assign_delivery", "drone_stm", args=[dispatch_data])

    def publish_telemetry(self):
        """Publish current drone telemetry."""
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
            "Published telemetry: state=%s battery=%.1f%%",
            data["state"],
            data["battery_level"],
        )

    def publish_event(self, event_type, message):
        """Publish a drone event."""
        event = {
            "drone_id": self.drone_id,
            "order_id": self.drone.order_id if self.drone else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
        }

        self.client.publish(self.events_topic, json.dumps(event), qos=self.qos)
        logger.info(
            "Published event: %s order=%s",
            event_type,
            self.drone.order_id if self.drone else None,
        )

    def on_package_loaded(self):
        self.publish_event("package_loaded", "Package loaded successfully")

    def on_delivery_completed(self):
        self.publish_event("delivery_completed", "Delivery completed")

    def on_battery_depleted(self):
        self.publish_event("battery_depleted", "Battery depleted, returning to charge")

    def on_fully_charged(self):
        self.publish_event("fully_charged", "Battery fully charged")

    def on_arrived_at_destination(self):
        self.publish_event("arrived", "Arrived at destination")

    def on_gps_lost(self):
        self.publish_event("gps_lost", "GPS signal lost")

    def on_connection_restored(self):
        self.publish_event("connection_restored", "Connection to server restored")
