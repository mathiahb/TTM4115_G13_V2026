import json
import os
import threading
import time
from collections import defaultdict
from collections.abc import Generator

import paho.mqtt.client as mqtt
import pytest
import requests

MQTT_TOPIC_PREFIX = "ttm4115/team13"
SERVER_BASE_URL = os.environ.get("SERVER_URL", "http://localhost:5001")
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))


class MQTTCollector:
    def __init__(self, broker_host: str, broker_port: int):
        self.messages: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="test-collector",
        )
        self._client.on_message = self._on_message
        self._broker_host = broker_host
        self._broker_port = broker_port

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        with self._lock:
            self.messages[msg.topic].append(payload)

    def get_messages(self, topic: str, timeout: float = 10.0) -> list[dict]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if topic in self.messages and self.messages[topic]:
                    return list(self.messages[topic])
            time.sleep(0.2)
        return []

    def wait_for_message(
        self, topic: str, predicate=None, timeout: float = 15.0
    ) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for msg in self.messages.get(topic, []):
                    if predicate is None or predicate(msg):
                        return msg
            time.sleep(0.2)
        return None

    def subscribe(self, topic: str, qos: int = 1):
        self._client.subscribe(topic, qos=qos)

    def start(self):
        self._client.connect(self._broker_host, self._broker_port)
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: dict, qos: int = 1):
        self._client.publish(topic, json.dumps(payload), qos=qos)


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.get(f"{base_url}/")

    def get(self, path: str, **kwargs):
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.session.post(f"{self.base_url}{path}", **kwargs)


def wait_for_server(url: str = SERVER_BASE_URL, timeout: float = 60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{url}/api/shops", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Server at {url} not ready after {timeout}s")


def wait_for_mqtt(
    broker_host: str = MQTT_BROKER_HOST,
    broker_port: int = MQTT_BROKER_PORT,
    timeout: float = 15.0,
):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            c = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="mqtt-probe",
            )
            c.connect(broker_host, broker_port)
            c.disconnect()
            return True
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(
        f"MQTT broker at {broker_host}:{broker_port} not ready after {timeout}s"
    )


@pytest.fixture(scope="session")
def server_url():
    wait_for_server()
    return SERVER_BASE_URL


@pytest.fixture(scope="session")
def mqtt_ready():
    wait_for_mqtt()
    return True


@pytest.fixture(scope="session")
def mqtt_collector(mqtt_ready) -> Generator[MQTTCollector, None, None]:
    collector = MQTTCollector(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    collector.subscribe(f"{MQTT_TOPIC_PREFIX}/drones/+/telemetry", qos=1)
    collector.subscribe(f"{MQTT_TOPIC_PREFIX}/drones/+/events", qos=1)
    collector.start()
    time.sleep(1)
    yield collector
    collector.stop()


@pytest.fixture()
def api_client(server_url):
    return APIClient(SERVER_BASE_URL)


@pytest.fixture()
def fresh_session(server_url):
    return APIClient(SERVER_BASE_URL)


def place_order(
    client: APIClient,
    shop_id: str = "SHOP-001",
    item_id: str = "ITM-01",
    priority: str = "standard",
    lat: float = 63.4220,
    lon: float = 10.4000,
) -> requests.Response:
    return client.post(
        "/api/orders",
        json={
            "shop_id": shop_id,
            "item_id": item_id,
            "priority": priority,
            "lat": lat,
            "lon": lon,
        },
    )
