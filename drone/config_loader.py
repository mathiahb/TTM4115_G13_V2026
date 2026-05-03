import argparse
import os
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drone Delivery Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-c", "--config", type=str, default="config.yaml")
    parser.add_argument("--drone-id", type=str, default=None)
    return parser.parse_args()


def get_drone_id(config: dict, override: str | None = None) -> str:
    if override:
        return override
    return config.get("drone", {}).get("drone_id", "1")


def get_mqtt_config(config: dict) -> dict:
    mqtt_cfg = config.get("mqtt", {})
    if broker := os.environ.get("MQTT_BROKER_HOST"):
        mqtt_cfg = {**mqtt_cfg, "broker_host": broker}
    return mqtt_cfg


def get_mqtt_topic(config: dict, topic_name: str, drone_id: str | None = None) -> str:
    mqtt_cfg = config.get("mqtt", {})
    prefix = mqtt_cfg.get("topic_prefix", "").strip("/")
    topics_cfg = mqtt_cfg.get("topics", {})
    pattern = topics_cfg.get(topic_name, topic_name)
    if drone_id:
        pattern = pattern.replace("{drone_id}", str(drone_id))
    if prefix:
        return f"{prefix}/{pattern}"
    return pattern


def get_simulation_config(config: dict) -> dict:
    return config.get("simulation", {})


def get_battery_config(config: dict) -> dict:
    return config.get("battery", {})


def get_charging_config(config: dict) -> dict:
    return config.get("charging", {})


def get_telemetry_interval(config: dict) -> float:
    return config.get("drone", {}).get("telemetry_interval", 2.0)


def get_initial_location(config: dict) -> dict:
    loc = config.get("drone", {}).get("initial_location", {})
    return {
        "lat": loc.get("lat", 63.4157),
        "lon": loc.get("lon", 10.4060),
        "gps_valid": loc.get("gps_valid", True),
    }


def get_initial_battery(config: dict) -> float:
    return config.get("drone", {}).get("initial_battery", 95.0)


def get_max_payload(config: dict) -> float:
    return config.get("drone", {}).get("max_payload", 2.5)


def get_sim_tick_ms(config: dict) -> int:
    return config.get("drone", {}).get("sim_tick_ms", 500)


def get_pickup_time_ms(config: dict) -> int:
    return config.get("drone", {}).get("pickup_time_ms", 2000)


def get_display_colors(config: dict) -> dict:
    return config.get("display", {}).get("colors", {})
