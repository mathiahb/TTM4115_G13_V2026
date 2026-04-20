from flask import Flask, render_template, jsonify, request, send_from_directory
import uuid
from datetime import datetime, timezone

app = Flask(__name__)

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/drones")
def get_drones():
    return jsonify(list(drones.values()))


@app.route("/api/orders", methods=["GET", "POST"])
def handle_orders():
    if request.method == "POST":
        data = request.json
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        order = {
            "order_id": order_id,
            "destination": data["destination"],
            "package_info": data["package_info"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "eta": None,
        }
        orders[order_id] = order
        return jsonify(order), 201

    return jsonify(sorted(orders.values(), key=lambda o: o["created_at"], reverse=True))


@app.route("/api/orders/<order_id>")
def get_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order)


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
