import math

METERS_PER_DEG_LAT = 110540.0


def meters_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def latlon_to_xy(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    x = (lon - ref_lon) * meters_per_deg_lon(ref_lat)
    y = (lat - ref_lat) * METERS_PER_DEG_LAT
    return x, y


def xy_to_latlon(x: float, y: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    lat = ref_lat + y / METERS_PER_DEG_LAT
    lon = ref_lon + x / meters_per_deg_lon(ref_lat)
    return lat, lon


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


def move_towards(location: dict, target: dict, speed_mps: float, ref_lat: float, dt: float = 0.5) -> bool:
    x, y = latlon_to_xy(location["lat"], location["lon"], ref_lat, ref_lon)
    tx, ty = latlon_to_xy(target["lat"], target["lon"], ref_lat, ref_lon)
    dist = math.sqrt((tx - x) ** 2 + (ty - y) ** 2)
    step = speed_mps * dt
    if dist <= step:
        location["lat"] = target["lat"]
        location["lon"] = target["lon"]
        return True
    ratio = step / dist
    x += (tx - x) * ratio
    y += (ty - y) * ratio
    location["lat"], location["lon"] = xy_to_latlon(x, y, ref_lat, ref_lon)
    return False


def drain_battery(battery_level: float, drain_rate: float, dt: float = 0.5) -> float:
    return max(0.0, battery_level - drain_rate * dt)


def charge_battery(battery_level: float, charge_rate: float, dt: float = 0.5) -> float:
    return min(100.0, battery_level + charge_rate * dt)


def compute_charge_rate(full_charge_time_minutes: float) -> float:
    return 100.0 / (full_charge_time_minutes * 60)
