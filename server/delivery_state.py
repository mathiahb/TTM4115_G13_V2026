import math
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
        shops: dict,
        delivery_config: dict,
    ):
        self.order_id = order_id
        self.orders = orders
        self.drones = drones
        self.mqtt_client = mqtt_client
        self.shops = shops
        self.delivery_config = delivery_config
        self._dispatch_published = False

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    def _drone_key(self) -> str | None:
        order = self.orders.get(self.order_id)
        if order and "drone" in order:
            return f"Drone{order['drone']['drone_id']}"
        return None

    def _pickup_points(self) -> list[dict]:
        return [
            {"lat": s["lat"], "lon": s["lon"], "id": s["shop_id"]}
            for s in self.shops.values()
        ]

    def _nearest_pickup(self, lat: float, lon: float) -> dict | None:
        best = None
        best_dist = float("inf")
        for pp in self._pickup_points():
            d = self._haversine(lat, lon, pp["lat"], pp["lon"])
            if d < best_dist:
                best = pp
                best_dist = d
        return best

    def _insert_charging_stops(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> list[dict]:
        max_range = self.delivery_config.get("max_single_charge_range_km", 3.0)
        dist = self._haversine(from_lat, from_lon, to_lat, to_lon)
        if dist <= max_range:
            return []

        best_pp = None
        best_remaining = float("inf")
        for pp in self._pickup_points():
            d_from = self._haversine(from_lat, from_lon, pp["lat"], pp["lon"])
            if d_from > max_range or d_from < 0.01:
                continue
            d_to = self._haversine(pp["lat"], pp["lon"], to_lat, to_lon)
            if d_to < dist and d_to < best_remaining:
                best_pp = pp
                best_remaining = d_to

        if not best_pp:
            logger.warning(
                "[%s] No reachable charging stop between (%.4f,%.4f) and (%.4f,%.4f)",
                self.order_id, from_lat, from_lon, to_lat, to_lon,
            )
            return []

        stop = {"lat": best_pp["lat"], "lon": best_pp["lon"], "action": "charging"}
        return [stop] + self._insert_charging_stops(
            best_pp["lat"], best_pp["lon"], to_lat, to_lon
        )

    def _plan_route(self) -> list[dict]:
        order = self.orders.get(self.order_id)
        if not order:
            return []
        dk = self._drone_key()
        drone = self.drones.get(dk, {}) if dk else {}
        drone_loc = drone.get("location", {})
        d_lat = drone_loc.get("lat", 0)
        d_lon = drone_loc.get("lon", 0)
        s_lat = order["shop_lat"]
        s_lon = order["shop_lon"]
        c_lat = order["customer_lat"]
        c_lon = order["customer_lon"]

        return_pp = self._nearest_pickup(c_lat, c_lon)
        r_lat = return_pp["lat"] if return_pp else s_lat
        r_lon = return_pp["lon"] if return_pp else s_lon

        route = [{"lat": d_lat, "lon": d_lon, "action": "takeoff"}]
        route.extend(self._insert_charging_stops(d_lat, d_lon, s_lat, s_lon))
        route.append({"lat": s_lat, "lon": s_lon, "action": "pickup"})
        route.extend(self._insert_charging_stops(s_lat, s_lon, c_lat, c_lon))
        route.append({"lat": c_lat, "lon": c_lon, "action": "delivery"})
        route.extend(self._insert_charging_stops(c_lat, c_lon, r_lat, r_lon))
        route.append({"lat": r_lat, "lon": r_lon, "action": "return"})
        return route

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
            "route": self._plan_route(),
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
        min_battery = self.delivery_config.get("min_battery_for_delivery", 20.0)
        if battery_level >= min_battery:
            return "calculating_path"
        return "recalculating_path"


def create_delivery_machine(
    order_id: str,
    orders: dict,
    drones: dict,
    mqtt_client,
    shops: dict,
    delivery_config: dict,
) -> stmpy.Machine:
    obj = DeliveryState(order_id, orders, drones, mqtt_client, shops, delivery_config)

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
