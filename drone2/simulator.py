import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(min(1.0, a)))


def move_towards(location: dict, target: dict, speed_mps: float, dt: float = 0.5) -> bool:
    dist = haversine(location["lat"], location["lon"], target["lat"], target["lon"])
    step = speed_mps * dt
    if dist <= step:
        location["lat"] = target["lat"]
        location["lon"] = target["lon"]
        return True
    ratio = step / dist
    location["lat"] += (target["lat"] - location["lat"]) * ratio
    location["lon"] += (target["lon"] - location["lon"]) * ratio
    return False


def drain_battery(battery_level: float, drain_rate: float, dt: float = 0.5) -> float:
    return max(0.0, battery_level - drain_rate * dt)


def charge_battery(battery_level: float, charge_rate: float, dt: float = 0.5) -> float:
    return min(100.0, battery_level + charge_rate * dt)


def compute_charge_rate(full_charge_time_minutes: float) -> float:
    return 100.0 / (full_charge_time_minutes * 60)
