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
        logger.info("[%s] Recalculating route (low battery)", self.order_id)

    def on_dispatch(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "dispatched"
            dk = self._drone_key()
            if dk and dk in self.drones:
                self.drones[dk]["state"] = "travel_to_warehouse"
        self._publish_dispatch()
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
    ]

    return stmpy.Machine(
        name=order_id,
        transitions=transitions,
        states=states,
        obj=obj,
    )
