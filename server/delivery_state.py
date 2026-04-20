import stmpy
import logging

logger = logging.getLogger(__name__)


class DeliveryState:
    def __init__(self, order_id: str, orders: dict, drones: dict):
        self.order_id = order_id
        self.orders = orders
        self.drones = drones

    def _drone_key(self) -> str | None:
        order = self.orders.get(self.order_id)
        if order and "drone" in order:
            return f"Drone{order['drone']['drone_id']}"
        return None

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
        logger.info("[%s] Drone dispatched", self.order_id)

    def on_reroute(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "rerouted"
        logger.info("[%s] Rerouted to charger", self.order_id)

    def on_in_transit(self):
        order = self.orders.get(self.order_id)
        if order:
            order["status"] = "in_transit"
            dk = self._drone_key()
            if dk and dk in self.drones:
                self.drones[dk]["state"] = "travel_to_customer"
        logger.info("[%s] In transit", self.order_id)

    def evaluate_delivery(self, battery_level=100):
        if battery_level >= 20:
            return "calculate_path"
        return "recalculate_drone_path"


def create_delivery_machine(order_id: str, orders: dict, drones: dict) -> stmpy.Machine:
    obj = DeliveryState(order_id, orders, drones)

    states = [
        {"name": "monitoring"},
        {"name": "calculate_path", "entry": "on_calculate_path; start_timer('t_calc', 1000)"},
        {"name": "recalculate_drone_path", "entry": "on_recalculate_path; start_timer('t_recalc', 2000)"},
        {"name": "dispatch", "entry": "on_dispatch; start_timer('t_dispatch', 1500)"},
        {"name": "reroute", "entry": "on_reroute; start_timer('t_reroute', 3000)"},
        {"name": "in_transit", "entry": "on_in_transit"},
    ]

    transitions = [
        {"source": "initial", "target": "monitoring"},
        {
            "trigger": "scheduleDelivery",
            "source": "monitoring",
            "function": obj.evaluate_delivery,
            "targets": "calculate_path recalculate_drone_path",
        },
        {"trigger": "t_calc", "source": "calculate_path", "target": "dispatch"},
        {"trigger": "t_recalc", "source": "recalculate_drone_path", "target": "reroute"},
        {"trigger": "t_dispatch", "source": "dispatch", "target": "in_transit"},
        {"trigger": "t_reroute", "source": "reroute", "target": "in_transit"},
    ]

    return stmpy.Machine(
        name=order_id,
        transitions=transitions,
        states=states,
        obj=obj,
    )
