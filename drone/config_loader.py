"""Configuration loader for the drone."""

import argparse
import os
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the config.yaml file.

    Returns:
        Dictionary containing the configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file has invalid YAML syntax.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace with config path.
    """
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
    """Get the drone ID from config or CLI override.

    Args:
        config: Configuration dictionary.
        override: Optional override from CLI arguments.

    Returns:
        The drone ID to use.
    """
    if override:
        return override

    drone_cfg = config.get("drone", {})
    return drone_cfg.get("drone_id", "1")


def get_mqtt_config(config: dict) -> dict:
    """Extract MQTT configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with MQTT settings.
    """
    return config.get("mqtt", {})


def get_mqtt_topic(config: dict, topic_name: str, drone_id: str | None = None) -> str:
    """Build a full MQTT topic name with prefix and optional drone_id substitution.

    Args:
        config: Configuration dictionary.
        topic_name: Name of the topic from config.topics (e.g., "telemetry").
        drone_id: Optional drone ID to substitute in the topic pattern.

    Returns:
        Full topic path with prefix, e.g., "ttm4115/team13/drones/1/telemetry"
    """
    mqtt_cfg = config.get("mqtt", {})
    prefix = mqtt_cfg.get("topic_prefix", "").strip("/")
    topics_cfg = mqtt_cfg.get("topics", {})

    # Get the topic pattern (e.g., "drones/{drone_id}/telemetry")
    pattern = topics_cfg.get(topic_name, topic_name)

    # Substitute drone_id if provided
    if drone_id:
        pattern = pattern.replace("{drone_id}", str(drone_id))

    # Combine prefix and topic
    if prefix:
        return f"{prefix}/{pattern}"
    return pattern


def get_battery_config(config: dict) -> dict:
    """Extract battery management configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with battery settings.
    """
    return config.get("battery", {})


def get_charging_config(config: dict) -> dict:
    """Extract charging configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with charging settings.
    """
    return config.get("charging", {})


def get_simulation_config(config: dict) -> dict:
    """Extract simulation configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with simulation settings.
    """
    return config.get("simulation", {})


def get_telemetry_interval(config: dict) -> float:
    """Get telemetry publishing interval.

    Args:
        config: Configuration dictionary.

    Returns:
        Interval in seconds.
    """
    drone_cfg = config.get("drone", {})
    return drone_cfg.get("telemetry_interval", 2.0)
