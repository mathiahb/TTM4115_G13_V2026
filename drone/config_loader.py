"""Configuration loader for the drone."""

import argparse
import os
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Drone Delivery Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--drone-id",
        type=str,
        default=None,
        help="Override drone ID from config file",
    )
    return parser.parse_args()


def get_drone_id(config: dict, override: str | None = None) -> str:
    """Get the drone ID from config or CLI override."""
    if override:
        return override
    drone_cfg = config.get("drone", {})
    return drone_cfg.get("drone_id", "1")


def get_mqtt_config(config: dict) -> dict:
    """Extract MQTT configuration."""
    mqtt_cfg = config.get("mqtt", {})
    if broker := os.environ.get("MQTT_BROKER_HOST"):
        mqtt_cfg = {**mqtt_cfg, "broker_host": broker}
    return mqtt_cfg


def get_mqtt_topic(config: dict, topic_name: str, drone_id: str | None = None) -> str:
    """Build a full MQTT topic name with prefix and optional drone_id substitution."""
    mqtt_cfg = config.get("mqtt", {})
    prefix = mqtt_cfg.get("topic_prefix", "").strip("/")
    topics_cfg = mqtt_cfg.get("topics", {})

    pattern = topics_cfg.get(topic_name, topic_name)

    if drone_id:
        pattern = pattern.replace("{drone_id}", str(drone_id))

    if prefix:
        return f"{prefix}/{pattern}"
    return pattern


def get_battery_config(config: dict) -> dict:
    """Extract battery management configuration."""
    return config.get("battery", {})


def get_charging_config(config: dict) -> dict:
    """Extract charging configuration."""
    return config.get("charging", {})


def get_simulation_config(config: dict) -> dict:
    """Extract simulation configuration."""
    return config.get("simulation", {})


def get_telemetry_interval(config: dict) -> float:
    """Get telemetry publishing interval in seconds."""
    drone_cfg = config.get("drone", {})
    return drone_cfg.get("telemetry_interval", 2.0)


def get_initial_location(config: dict) -> dict:
    """Get initial drone location from config."""
    drone_cfg = config.get("drone", {})
    loc = drone_cfg.get("initial_location", {})
    return {
        "lat": loc.get("lat", 63.4157),
        "lon": loc.get("lon", 10.4060),
        "gps_valid": loc.get("gps_valid", True),
    }


def get_initial_battery(config: dict) -> float:
    """Get initial battery level from config."""
    drone_cfg = config.get("drone", {})
    return drone_cfg.get("initial_battery", 95.0)


def get_max_payload(config: dict) -> float:
    """Get max payload capacity from config."""
    drone_cfg = config.get("drone", {})
    return drone_cfg.get("max_payload", 2.5)
