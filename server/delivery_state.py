import stmpy
import logging

logger = logging.getLogger(__name__)


class DeliveryState:
    def __init__(
        self,
        order_id: str,
        orders: dict,
        drones: dict,
        mqtt_client,
    ):
        self.order_id = order_id
        self.orders = orders
        self.drones = drones
        self.mqtt_client = mqtt_client
        self._dispatch_published = False

    def _drone_key(self) -> str | None:
        order = self.orders.get(self.order_id)
        if order and "drone" in order:
            return f"Drone{order['drone']['drone_id']}"
        return None

    def _get_route(self) -> list[dict]:
        order = self.orders.get(self.order_id)
        if not order:
            return []
        dk = self._drone_key()
        drone = self.drones.get(dk, {}) if dk else {}
        drone_loc = drone.get("location", {})
        return [
            {
                "lat": drone_loc.get("lat", 0),
                "lon": drone_loc.get("lon", 0),
                "type": "waypoint",
            },
            {
                "lat": order["shop_lat"],
                "lon": order["shop_lon"],
                "type": "waypoint",
            },
            {
                "lat": order["customer_lat"],
                "lon": order["customer_lon"],
                "type": "destination",
            },
        ]

    def _publish_dispatch(self):
        order = self.orders.get(self.order_id)
        if not order:
            return
        drone_id = order["drone"]["drone_id"]
        payload = {
            "order_id": self.order_id,
            "package_info": {
                "weight": order["item"]["weight"],
                "priority": order.get("priority", "standard"),
            },
            "route": self._get_route(),
        }
        self.mqtt_client.publish_dispatch(drone_id, payload)

    def on_calculate_path(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "calculating_route"
        logger.info("[%s] Calculating route", self.order_id)

    def on_recalculate_path(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "recalculating_route"
        self._dispatch_published = False
        logger.info("[%s] Recalculating route (low battery)", self.order_id)

    def on_dispatch(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "dispatched"
            dk = self._drone_key()
            if dk and dk in self.drones:
                self.drones[dk]["state"] = "travel_to_warehouse"
        if not self._dispatch_published:
            self._publish_dispatch()
            self._dispatch_published = True
            logger.info("[%s] Drone dispatched via MQTT", self.order_id)

    def on_drone_arrived(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "at_warehouse"
        logger.info("[%s] Drone arrived at warehouse", self.order_id)

    def on_package_loaded(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "in_transit"
            dk = self._drone_key()
            if dk and dk in self.drones:
                self.drones[dk]["state"] = "travel_to_customer"
        logger.info("[%s] Package loaded, in transit", self.order_id)

    def on_delivery_completed(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "completed"
            dk = self._drone_key()
            if dk and dk in self.drones:
                self.drones[dk]["state"] = "standby"
        logger.info("[%s] Delivery completed", self.order_id)

    def on_battery_depleted(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "recalculating_route"
        logger.warning("[%s] Battery depleted, rerouting", self.order_id)

    def on_fully_charged(self):
        dk = self._drone_key()
        if dk and dk in self.drones:
            self.drones[dk]["state"] = "standby"
        logger.info("[%s] Drone fully charged, returning to standby", self.order_id)

    def on_gps_lost(self):
        dk = self._drone_key()
        if dk and dk in self.drones:
            self.drones[dk]["location"]["gps_valid"] = False
        logger.warning("[%s] Drone GPS lost", self.order_id)

    def on_connection_restored(self):
        logger.info("[%s] Drone connection restored", self.order_id)

    def evaluate_delivery(self, battery_level=100):
        if battery_level >= 20:
            return "calculating_path"
        return "recalculating_path"


def create_delivery_machine(
    order_id: str,
    orders: dict,
    drones: dict,
    mqtt_client,
) -> stmpy.Machine:
    obj = DeliveryState(order_id, orders, drones, mqtt_client)

    states = [
        {"name": "monitoring"},
        {
            "name": "calculating_path",
            "entry": "on_calculate_path; start_timer('t_calc', 500)",
        },
        {
            "name": "recalculating_path",
            "entry": "on_recalculate_path; start_timer('t_recalc', 500)",
        },
        {"name": "dispatched", "entry": "on_dispatch"},
        {"name": "at_warehouse", "entry": "on_drone_arrived"},
        {"name": "in_transit", "entry": "on_package_loaded"},
        {"name": "completed", "entry": "on_delivery_completed"},
    ]

    transitions = [
        {"source": "initial", "target": "monitoring"},
        {
            "trigger": "scheduleDelivery",
            "source": "monitoring",
            "function": obj.evaluate_delivery,
            "targets": "calculating_path recalculating_path",
        },
        {"trigger": "t_calc", "source": "calculating_path", "target": "dispatched"},
        {
            "trigger": "t_recalc",
            "source": "recalculating_path",
            "target": "dispatched",
        },
        {
            "trigger": "drone_arrived",
            "source": "dispatched",
            "target": "at_warehouse",
        },
        {
            "trigger": "package_loaded",
            "source": "at_warehouse",
            "target": "in_transit",
        },
        {
            "trigger": "delivery_completed",
            "source": "in_transit",
            "target": "completed",
        },
        {
            "trigger": "battery_depleted",
            "source": "dispatched",
            "target": "recalculating_path",
        },
        {
            "trigger": "battery_depleted",
            "source": "at_warehouse",
            "target": "recalculating_path",
        },
        {
            "trigger": "battery_depleted",
            "source": "in_transit",
            "target": "recalculating_path",
        },
        {
            "trigger": "fully_charged",
            "source": "dispatched",
            "target": "dispatched",
        },
        {
            "trigger": "fully_charged",
            "source": "at_warehouse",
            "target": "at_warehouse",
        },
        {
            "trigger": "fully_charged",
            "source": "in_transit",
            "target": "in_transit",
        },
        {
            "trigger": "gps_lost",
            "source": "dispatched",
            "target": "dispatched",
        },
        {
            "trigger": "gps_lost",
            "source": "at_warehouse",
            "target": "at_warehouse",
        },
        {
            "trigger": "gps_lost",
            "source": "in_transit",
            "target": "in_transit",
        },
        {
            "trigger": "connection_restored",
            "source": "dispatched",
            "target": "dispatched",
        },
        {
            "trigger": "connection_restored",
            "source": "at_warehouse",
            "target": "at_warehouse",
        },
        {
            "trigger": "connection_restored",
            "source": "in_transit",
            "target": "in_transit",
        },
    ]

    return stmpy.Machine(
        name=order_id,
        transitions=transitions,
        states=states,
        obj=obj,
    )
