from conftest import MQTT_TOPIC_PREFIX, place_order, wait_for_drone_standby


def test_telemetry_published_within_interval(mqtt_collector):
    msg = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/1/telemetry",
        timeout=15.0,
    )
    assert msg is not None
    assert msg["drone_id"] == "1"
    assert "battery_level" in msg
    assert "location" in msg
    assert "lat" in msg["location"]
    assert "lon" in msg["location"]
    assert "state" in msg


def test_telemetry_schema_valid(mqtt_collector):
    msg = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/1/telemetry",
        timeout=10.0,
    )
    assert msg is not None
    assert isinstance(msg["drone_id"], str)
    assert isinstance(msg["timestamp"], str)
    assert isinstance(msg["battery_level"], (int, float))
    assert 0 <= msg["battery_level"] <= 100
    assert isinstance(msg["location"]["gps_valid"], bool)
    assert isinstance(msg["state"], str)


def test_both_drones_publish_telemetry(mqtt_collector):
    drone1_msg = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/1/telemetry",
        timeout=10.0,
    )
    drone2_msg = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/2/telemetry",
        timeout=10.0,
    )
    assert drone1_msg is not None
    assert drone2_msg is not None
    assert drone1_msg["drone_id"] == "1"
    assert drone2_msg["drone_id"] == "2"


def test_events_published_on_dispatch(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201

    drone_id = resp.json()["drone"]["drone_id"]
    order_id = resp.json()["order_id"]

    arrived_event = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "arrived" and m.get("order_id") == order_id,
        timeout=30.0,
    )
    assert arrived_event is not None
    assert arrived_event["event_type"] == "arrived"
    assert arrived_event["drone_id"] == drone_id


def test_package_loaded_event_published(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201

    drone_id = resp.json()["drone"]["drone_id"]
    order_id = resp.json()["order_id"]

    loaded_event = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "package_loaded" and m.get("order_id") == order_id,
        timeout=30.0,
    )
    assert loaded_event is not None
    assert loaded_event["event_type"] == "package_loaded"


def test_delivery_completed_event_published(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201

    drone_id = resp.json()["drone"]["drone_id"]
    order_id = resp.json()["order_id"]

    completed_event = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("event_type") == "delivery_completed" and m.get("order_id") == order_id,
        timeout=45.0,
    )
    assert completed_event is not None
    assert completed_event["event_type"] == "delivery_completed"
    assert completed_event["order_id"] == order_id


def test_event_schema_matches_contract(fresh_session, mqtt_collector):
    wait_for_drone_standby(mqtt_collector, timeout=30.0)
    resp = place_order(fresh_session)
    assert resp.status_code == 201

    drone_id = resp.json()["drone"]["drone_id"]
    order_id = resp.json()["order_id"]

    event = mqtt_collector.wait_for_message(
        f"{MQTT_TOPIC_PREFIX}/drones/{drone_id}/events",
        predicate=lambda m: m.get("order_id") == order_id,
        timeout=20.0,
    )
    assert event is not None
    assert "drone_id" in event
    assert "timestamp" in event
    assert "event_type" in event
    assert isinstance(event.get("message", ""), str)
