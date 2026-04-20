import json
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import stmpy

logger = logging.getLogger(__name__)


class DroneMQTTHandler:
    """
    Handles MQTT communication for the drone using paho-mqtt.
    Manages telemetry publishing, event publishing, and dispatch message handling.
    """

    def __init__(self, drone, driver, config=None, broker_host=None, broker_port=None, drone_id="drone_001"):
        self.drone = drone
        self.driver = driver
        self.config = config or {}
        self.drone_id = drone_id

        # Extract MQTT config from config dict, with CLI overrides
        mqtt_cfg = self.config.get('mqtt', {})
        self.broker_host = broker_host or mqtt_cfg.get('broker_host', 'localhost')
        self.broker_port = broker_port or mqtt_cfg.get('broker_port', 1883)
        self.telemetry_interval = self.config.get('drone', {}).get('telemetry_interval', 5000)

        # MQTT client setup
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # Topics
        self.telemetry_topic = f"drones/{self.drone_id}/telemetry"
        self.dispatch_topic = f"drones/{self.drone_id}/dispatch"
        self.events_topic = f"drones/{self.drone_id}/events"

        # Current order ID (set when dispatch received)
        self.current_order_id = None

        # Telemetry publishing timer
        self.telemetry_timer = None

    def connect(self):
        """Connect to MQTT broker."""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def start(self):
        """Start the MQTT client loop and telemetry publishing."""
        self.client.loop_start()
        # Start telemetry publishing with interval from config
        self.telemetry_timer = stmpy.Timer("telemetry_publish", self.telemetry_interval, self.publish_telemetry)
        self.driver.add_timer(self.telemetry_timer)

    def stop(self):
        """Stop the MQTT client and timers."""
        if self.telemetry_timer:
            self.driver.remove_timer(self.telemetry_timer)
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            # Subscribe to dispatch topic
            self.client.subscribe(self.dispatch_topic)
            logger.info(f"Subscribed to dispatch topic: {self.dispatch_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        logger.warning(f"Disconnected from MQTT broker, return code: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback when a message is received."""
        try:
            if msg.topic == self.dispatch_topic:
                self.handle_dispatch(json.loads(msg.payload.decode()))
            else:
                logger.warning(f"Received message on unexpected topic: {msg.topic}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")

    def handle_dispatch(self, dispatch_data):
        """Handle incoming dispatch message."""
        logger.info(f"Received dispatch: {dispatch_data}")

        self.current_order_id = dispatch_data.get("order_id")

        # Extract package info
        package_info = dispatch_data.get("package_info", {})
        weight = package_info.get("weight", 0)
        priority = package_info.get("priority", "standard")

        # Extract route - for now, just set the final destination
        route = dispatch_data.get("route", [])
        if route:
            # Assume last waypoint is destination
            destination = route[-1]
            lat = destination.get("lat", 0)
            lon = destination.get("lon", 0)
            # Convert lat/lon to x/y coordinates (simple approximation)
            # Assuming warehouse at (0,0), scale lat/lon to meters
            target_x = lat * 111320  # rough conversion lat to meters
            target_y = lon * 111320 * 0.707  # rough for lon
            self.drone.set_customer_target(target_x, target_y)

        # Send assignment received event to state machine
        self.driver.send('assignment_received', 'drone_stm')

        # Publish event
        self.publish_event("assignment_received", f"Order {self.current_order_id} assigned")

    def publish_telemetry(self):
        """Publish current drone telemetry."""
        if not self.drone.stm:
            return

        # Get current status
        status = self.drone.get_status()

        # Convert position to lat/lon (reverse of dispatch conversion)
        lat = status['position'][0] / 111320
        lon = status['position'][1] / (111320 * 0.707)

        telemetry = {
            "drone_id": self.drone_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": {
                "lat": lat,
                "lon": lon,
                "height": 10.0  # Assume constant height for now
            },
            "battery_level": status['battery_level'],
            "max_payload": 5.0,  # Assume constant max payload
            "state": self.drone.stm.state if self.drone.stm else "unknown"
        }

        self.client.publish(self.telemetry_topic, json.dumps(telemetry))
        logger.debug(f"Published telemetry: {telemetry}")

    def publish_event(self, event_type, message):
        """Publish a drone event."""
        event = {
            "drone_id": self.drone_id,
            "order_id": self.current_order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message
        }

        self.client.publish(self.events_topic, json.dumps(event))
        logger.info(f"Published event: {event}")

    # Integration methods - call these from drone state changes
    def on_package_loaded(self):
        self.publish_event("package_loaded", "Package loaded successfully")

    def on_delivery_completed(self):
        self.publish_event("delivery_completed", "Delivery completed")
        self.current_order_id = None

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