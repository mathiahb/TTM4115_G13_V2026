from flask import Flask, render_template, jsonify, request
import uuid
import math
from datetime import datetime, timezone
import stmpy

from delivery_state import create_delivery_machine
from client_state import create_client_machine

app = Flask(__name__)

driver = stmpy.Driver()
driver.start(keep_active=True)

shops: dict[str, dict] = {
    "SHOP-001": {
        "shop_id": "SHOP-001",
        "name": "Midtbyen Convenience",
        "lat": 63.4305,
        "lon": 10.3951,
        "items": [
            {"item_id": "ITM-01", "name": "Coffee", "weight": 0.3},
            {"item_id": "ITM-02", "name": "Sandwich", "weight": 0.4},
            {"item_id": "ITM-03", "name": "Energy Drink", "weight": 0.5},
        ],
    },
    "SHOP-002": {
        "shop_id": "SHOP-002",
        "name": "Gloshaugen Market",
        "lat": 63.4157,
        "lon": 10.4060,
        "items": [
            {"item_id": "ITM-04", "name": "Pizza Slice", "weight": 0.5},
            {"item_id": "ITM-05", "name": "Salad Bowl", "weight": 0.6},
            {"item_id": "ITM-06", "name": "Sparkling Water", "weight": 0.4},
        ],
    },
    "SHOP-003": {
        "shop_id": "SHOP-003",
        "name": "Solsiden Bakery",
        "lat": 63.4342,
        "lon": 10.4162,
        "items": [
            {"item_id": "ITM-07", "name": "Cinnamon Roll", "weight": 0.2},
            {"item_id": "ITM-08", "name": "Baguette", "weight": 0.4},
            {"item_id": "ITM-09", "name": "Hot Chocolate", "weight": 0.3},
        ],
    },
    "SHOP-004": {
        "shop_id": "SHOP-004",
        "name": "Heimdal Pharmacy",
        "lat": 63.4080,
        "lon": 10.3500,
        "items": [
            {"item_id": "ITM-10", "name": "First Aid Kit", "weight": 0.5},
            {"item_id": "ITM-11", "name": "Pain Relief", "weight": 0.1},
            {"item_id": "ITM-12", "name": "Bandages", "weight": 0.2},
        ],
    },
}

drones: dict[str, dict] = {
    "Drone1": {
        "drone_id": "1",
        "location": {"lat": 63.4157, "lon": 10.4060, "gps_valid": True},
        "battery_level": 95.0,
        "max_payload": 2.5,
        "state": "standby",
    },
    "Drone2": {
        "drone_id": "2",
        "location": {"lat": 63.4342, "lon": 10.3962, "gps_valid": True},
        "battery_level": 45.0,
        "max_payload": 2.5,
        "state": "standby",
    },
}

orders: dict[str, dict] = {}


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
    for drone in drones.values():
        if drone["state"] != "standby":
            continue
        if weight > drone["max_payload"]:
            continue
        if drone["battery_level"] < 20:
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
        result = []
        for order in orders.values():
            drone_key = f"Drone{order['drone']['drone_id']}"
            if drone_key in drones:
                live = drones[drone_key]
                order["drone"]["location"] = dict(live["location"])
                order["drone"]["battery_level"] = live["battery_level"]
                order["drone"]["state"] = live["state"]
            result.append({
                "order_id": order["order_id"],
                "shop_name": order["shop_name"],
                "shop_lat": order["shop_lat"],
                "shop_lon": order["shop_lon"],
                "item_name": order["item"]["name"],
                "status": order["status"],
                "drone": {
                    "drone_id": order["drone"]["drone_id"],
                    "location": order["drone"]["location"],
                    "battery_level": order["drone"]["battery_level"],
                    "state": order["drone"]["state"],
                },
                "created_at": order["created_at"],
            })
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

    drone = find_best_drone(shop["lat"], shop["lon"], item["weight"])
    if not drone:
        return jsonify({"error": "No available drone"}), 503

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"

    order = {
        "order_id": order_id,
        "shop_id": data["shop_id"],
        "shop_name": shop["name"],
        "shop_lat": shop["lat"],
        "shop_lon": shop["lon"],
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
    delivery_machine = create_delivery_machine(order_id, orders, drones)

    driver.add_machine(client_machine)
    driver.add_machine(delivery_machine)

    driver.send("orderFinished", f"client_{order_id}")
    driver.send("paid", f"client_{order_id}")
    driver.send("scheduleDelivery", order_id, args=[drone["battery_level"]])

    return jsonify(order), 201


@app.route("/api/orders/<order_id>")
def get_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    drone_key = f"Drone{order['drone']['drone_id']}"
    if drone_key in drones:
        live = drones[drone_key]
        order["drone"]["location"] = dict(live["location"])
        order["drone"]["battery_level"] = live["battery_level"]
        order["drone"]["state"] = live["state"]
    return jsonify(order)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
