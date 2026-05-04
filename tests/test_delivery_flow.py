import time

from conftest import MQTT_TOPIC_PREFIX, place_order, wait_for_drone_standby


def test_full_delivery_happy_path(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    order_id = resp.json()["order_id"]
    drone_id = resp.json()["drone"]["drone_id"]

    completed = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "delivery_completed" and m.get("order_id") == order_id,
        timeout=60.0,
    )
    assert completed is not None, "Delivery should complete within timeout"

    time.sleep(1)
    resp = fresh_session.get(f"/api/orders/{order_id}")
    assert resp.status_code == 200
    order = resp.json()
    assert order["status"] == "completed"


def test_drone_returns_to_standby_after_delivery(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    order_id = resp.json()["order_id"]
    drone_id = resp.json()["drone"]["drone_id"]

    mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "delivery_completed" and m.get("order_id") == order_id,
        timeout=60.0,
    )

    standby_telemetry = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/telemetry",
        predicate=lambda m: m.get("state") == "standby",
        timeout=30.0,
    )
    assert standby_telemetry is not None


def test_order_status_progresses_through_states(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    order_id = resp.json()["order_id"]
    drone_id = resp.json()["drone"]["drone_id"]

    mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "arrived" and m.get("order_id") == order_id,
        timeout=30.0,
    )

    order_resp = fresh_session.get(f"/api/orders/{order_id}")
    assert order_resp.status_code == 200
    order = order_resp.json()
    assert order["status"] in ("dispatched", "at_warehouse", "in_transit", "completed")


def test_second_order_uses_other_drone(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp1 = place_order(fresh_session)
    assert resp1.status_code == 201
    drone1 = resp1.json()["drone"]["drone_id"]

    resp2 = place_order(fresh_session, shop_id="SHOP-002", item_id="ITM-04")
    assert resp2.status_code == 201
    drone2 = resp2.json()["drone"]["drone_id"]

    assert drone1 != drone2, "Second order should be assigned to the other available drone"


def test_drone_battery_decreases_during_travel(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    drone_id = resp.json()["drone"]["drone_id"]

    first_telemetry = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/telemetry",
        predicate=lambda m: m.get("state") in (
            "travel",
            "execute",
        ),
        timeout=20.0,
    )
    assert first_telemetry is not None
    initial_battery = first_telemetry["battery_level"]

    later_telemetry = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/telemetry",
        predicate=lambda m: (
            m.get("battery_level") is not None
            and m["battery_level"] < initial_battery
        ),
        timeout=20.0,
    )
    assert later_telemetry is not None
    assert later_telemetry["battery_level"] < initial_battery


def test_telemetry_reflects_drone_location_changes(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201
    drone_id = resp.json()["drone"]["drone_id"]

    first = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/telemetry",
        predicate=lambda m: m.get("state") == "travel",
        timeout=15.0,
    )
    assert first is not None
    initial_lat = first["location"]["lat"]
    initial_lon = first["location"]["lon"]

    moved = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/telemetry",
        predicate=lambda m: (
            m.get("state") == "travel"
            and (
                m["location"]["lat"] != initial_lat
                or m["location"]["lon"] != initial_lon
            )
        ),
        timeout=15.0,
    )
    assert moved is not None


def test_drone_picks_up_new_order_after_returning(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp1 = place_order(fresh_session)
    assert resp1.status_code == 201
    order1 = resp1.json()["order_id"]
    drone1 = resp1.json()["drone"]["drone_id"]

    mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone1}/events",
        predicate=lambda m: m.get("event_type") == "delivery_completed" and m.get("order_id") == order1,
        timeout=60.0,
    )

    wait_for_drone_standby(mqtt_collector, drone_id=drone1, timeout=30.0)

    resp2 = place_order(fresh_session, shop_id="SHOP-002", item_id="ITM-04")
    assert resp2.status_code == 201
    assert resp2.json()["drone"]["drone_id"] == drone1, "Same drone should pick up second order after returning"
