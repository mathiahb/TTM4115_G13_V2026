import atexit
import logging
import math
import os
import uuid
from datetime import datetime, timezone

import stmpy
from flask import Flask, jsonify, render_template, request, session

from client_state import create_client_machine
from config_loader import (
    get_default_customer_location,
    get_delivery_config,
    get_secret_key,
    get_server_settings,
    load_config,
    load_drones,
    load_shops,
    parse_args,
)
from delivery_state import create_delivery_machine
from mqtt_client import MQTTClient

logging.basicConfig(level=logging.INFO)

args = parse_args()
config = load_config(args.config)

app = Flask(__name__)
app.secret_key = get_secret_key(config)


@app.before_request
def ensure_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())


driver = stmpy.Driver()
driver.start(keep_active=True)

shops: dict[str, dict] = load_shops(config)
drones: dict[str, dict] = load_drones(config)
_initial_drone_states: dict[str, dict] = {
    k: {
        "location": dict(v["location"]),
        "battery_level": v["battery_level"],
        "state": v["state"],
    }
    for k, v in drones.items()
}
delivery_config = get_delivery_config(config)

orders: dict[str, dict] = {}
default_customer_loc = get_default_customer_location(config)

EVENT_TRIGGER_MAP = {
    "arrived": "drone_arrived",
    "package_loaded": "package_loaded",
    "delivery_completed": "delivery_completed",
    "battery_depleted": "battery_depleted",
    "fully_charged": "fully_charged",
    "gps_lost": "gps_lost",
    "connection_restored": "connection_restored",
}


def handle_drone_event(
    event_type: str, drone_id: str, order_id: str | None, data: dict
):
    trigger = EVENT_TRIGGER_MAP.get(event_type)
    if not trigger:
        return

    if order_id and order_id in orders:
        driver.send(trigger, order_id)
        return

    for oid, order in orders.items():
        if order.get("status") in ("completed", "cancelled", "aborted"):
            continue
        if order.get("drone", {}).get("drone_id") == drone_id:
            driver.send(trigger, oid)
            return


mqtt = MQTTClient(config, drones, on_drone_event=handle_drone_event)
mqtt.start()
atexit.register(mqtt.stop)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def find_best_drone(shop_lat: float, shop_lon: float, weight: float) -> dict | None:
    best: dict | None = None
    best_dist: float = float("inf")
    min_battery = delivery_config.get("min_battery_for_delivery", 20.0)

    for drone in drones.values():
        if drone["state"] != "standby":
            continue
        if weight > drone["max_payload"]:
            continue
        if drone["battery_level"] < min_battery:
            continue
        dist = haversine(
            drone["location"]["lat"],
            drone["location"]["lon"],
            shop_lat,
            shop_lon,
        )
        if dist < best_dist:
            best = drone
            best_dist = dist
    return best


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/shops")
def get_shops():
    return jsonify(list(shops.values()))


@app.route("/api/orders", methods=["GET", "POST"])
def handle_orders():
    if request.method == "GET":
        sid = session["session_id"]
        result = []
        for order in orders.values():
            if order["session_id"] != sid:
                continue
            drone_key = f"Drone{order['drone']['drone_id']}"
            if drone_key in drones:
                live = drones[drone_key]
                order["drone"]["location"] = dict(live["location"])
                order["drone"]["battery_level"] = live["battery_level"]
                order["drone"]["state"] = live["state"]
            result.append(
                {
                    "order_id": order["order_id"],
                    "shop_name": order["shop_name"],
                    "shop_lat": order["shop_lat"],
                    "shop_lon": order["shop_lon"],
                    "item_name": order["item"]["name"],
                    "status": order["status"],
                    "priority": order.get("priority", "standard"),
                    "drone": {
                        "drone_id": order["drone"]["drone_id"],
                        "location": order["drone"]["location"],
                        "battery_level": order["drone"]["battery_level"],
                        "state": order["drone"]["state"],
                    },
                    "created_at": order["created_at"],
                }
            )
        return jsonify(sorted(result, key=lambda o: o["created_at"], reverse=True))

    data = request.json
    shop = shops.get(data["shop_id"])
    if not shop:
        return jsonify({"error": "Shop not found"}), 400

    item_id = data.get("item_id")
    item = next((i for i in shop["items"] if i["item_id"] == item_id), None)
    if not item:
        return jsonify({"error": "Item not found"}), 400

    priority: str = data.get("priority", "standard")

    customer_lat = data.get("lat", default_customer_loc["lat"])
    customer_lon = data.get("lon", default_customer_loc["lon"])
    dist_to_closest_shop = min(
        haversine(customer_lat, customer_lon, s["lat"], s["lon"])
        for s in shops.values()
    )
    if priority in ("priority", "express"):
        max_range = delivery_config.get("max_range_priority_km", 3.0)
    else:
        max_range = delivery_config.get("max_range_standard_km", 5.0)
    if dist_to_closest_shop > max_range:
        return jsonify(
            {
                "error": f"Too far from nearest shop (max {max_range} km for {priority} delivery)"
            }
        ), 400

    drone = find_best_drone(shop["lat"], shop["lon"], item["weight"])
    if not drone:
        return jsonify({"error": "No available drone"}), 503

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"

    order = {
        "order_id": order_id,
        "session_id": session["session_id"],
        "shop_id": data["shop_id"],
        "shop_name": shop["name"],
        "shop_lat": shop["lat"],
        "shop_lon": shop["lon"],
        "customer_lat": customer_lat,
        "customer_lon": customer_lon,
        "item": item,
        "priority": priority,
        "status": "pending",
        "client_state": "waiting_for_user",
        "drone": {
            "drone_id": drone["drone_id"],
            "location": dict(drone["location"]),
            "battery_level": drone["battery_level"],
            "state": drone["state"],
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "eta": "15 min",
    }
    orders[order_id] = order

    client_machine = create_client_machine(order_id, orders)
    delivery_machine = create_delivery_machine(
        order_id, orders, drones, mqtt, shops, delivery_config
    )

    driver.add_machine(client_machine)
    driver.add_machine(delivery_machine)

    driver.send("orderFinished", f"client_{order_id}")
    driver.send("paid", f"client_{order_id}")
    driver.send("scheduleDelivery", order_id, args=[drone["battery_level"]])

    return jsonify(order), 201


@app.route("/api/orders/<order_id>")
def get_order(order_id: str):
    order = orders.get(order_id)
    if not order or order["session_id"] != session["session_id"]:
        return jsonify({"error": "Order not found"}), 404
    drone_key = f"Drone{order['drone']['drone_id']}"
    if drone_key in drones:
        live = drones[drone_key]
        order["drone"]["location"] = dict(live["location"])
        order["drone"]["battery_level"] = live["battery_level"]
        order["drone"]["state"] = live["state"]
    return jsonify(order)


if os.environ.get("TEST_MODE") == "1":

    @app.route("/api/test/reset", methods=["POST"])
    def test_reset():
        machine_ids = list(driver._stms_by_id.keys())
        for mid in machine_ids:
            driver._terminate_stm(mid)
        orders.clear()
        for key, initial in _initial_drone_states.items():
            if key in drones:
                drones[key]["location"] = dict(initial["location"])
                drones[key]["battery_level"] = initial["battery_level"]
                drones[key]["state"] = initial["state"]
        return jsonify({"status": "ok"})


if __name__ == "__main__":
    settings = get_server_settings(config)
    settings.setdefault("use_reloader", False)
    app.run(**settings)
