from conftest import MQTT_TOPIC_PREFIX, place_order, wait_for_drone_standby


def test_drone_battery_reflects_in_api_after_delivery(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    drone_id = resp.json()["drone"]["drone_id"]
    order_id = resp.json()["order_id"]

    initial_battery = resp.json()["drone"]["battery_level"]

    mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "delivery_completed" and m.get("order_id") == order_id,
        timeout=30.0,
    )

    wait_for_drone_standby(mqtt_collector, drone_id=drone_id, timeout=30.0)

    resp = fresh_session.get(f"/api/orders/{order_id}")
    assert resp.status_code == 200
    order = resp.json()
    assert order["drone"]["battery_level"] < initial_battery, \
        "Battery should be lower after delivery"
