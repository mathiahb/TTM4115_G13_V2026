"""Configuration loader for the drone delivery server."""

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
        description="Drone Delivery Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the configuration file",
    )
    return parser.parse_args()


def get_secret_key(config: dict) -> str:
    """Get the Flask secret key from config or environment.

    Args:
        config: Configuration dictionary.

    Returns:
        The secret key to use.
    """
    server_cfg = config.get("server", {})
    env_var = server_cfg.get("secret_key_env", "FLASK_SECRET")
    default_key = server_cfg.get("secret_key_default", "dev-secret-change-in-prod")

    return os.environ.get(env_var, default_key)


def get_server_settings(config: dict) -> dict:
    """Extract server settings from config.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with host, port, debug settings.
    """
    server_cfg = config.get("server", {})
    return {
        "host": server_cfg.get("host", "0.0.0.0"),
        "port": server_cfg.get("port", 5000),
        "debug": server_cfg.get("debug", False),
    }


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


def load_shops(config: dict) -> dict[str, dict]:
    """Load shops from config into a dictionary keyed by shop_id.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary mapping shop_id to shop data.
    """
    shops_list = config.get("shops", [])
    return {shop["shop_id"]: shop for shop in shops_list}


def load_drones(config: dict) -> dict[str, dict]:
    """Load drones from config into a dictionary keyed by drone_id.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary mapping drone_id (as "Drone{drone_id}") to drone data.
    """
    drones_list = config.get("drones", [])
    result = {}
    for drone in drones_list:
        key = f"Drone{drone['drone_id']}"
        result[key] = drone
    return result


def get_battery_config(config: dict) -> dict:
    """Extract battery management configuration.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with battery settings.
    """
    return config.get("battery", {})
