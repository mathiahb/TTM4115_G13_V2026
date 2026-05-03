# Development Log

## 2026-05-03 — Route planner overhaul, delivery range restrictions, config cleanup

### Config cleanup
- Replaced `battery` config section with `delivery` section in `server/config.yaml`
- Removed unused keys: `no_charging_below_distance_km`, `charging_threshold`
- Added: `max_range_standard_km`, `max_range_priority_km`, `max_single_charge_range_km`
- `config_loader.get_battery_config()` → `get_delivery_config()`

### Delivery range restrictions
- POST /api/orders now checks customer-to-shop distance
- Standard orders: max 5 km, Priority orders: max 3 km (priority drains 3x battery)
- Returns 400 if out of range

### Route planner overhaul (`delivery_state.py`)
- Replaced 3-point static route (drone → shop → customer) with full route planner
- Route: takeoff → (charging stops) → pickup → (charging stops) → delivery → (charging stops) → return
- Charging stops inserted recursively when any leg exceeds `max_single_charge_range_km` (3 km)
- Shops double as pickup/charging points — drone picks the nearest one to insert as a charging stop
- Return waypoint = closest shop/pickup point to the customer
- Waypoints now use `action` field instead of `type`: `takeoff|charging|pickup|delivery|return`

### Bug fixes
- Fixed user location marker jumping when map moves (geolocation error callback only sets fallback when no position exists)
- Fixed drone marker not updating during order refresh
- Fixed duplicate MQTT dispatches on state self-loop re-entry (`_dispatch_published` guard)
- Awaited `loadOrders()` in `placeOrder()` so drone marker exists before `fitBounds`

### Breaking changes (drone refactor needed)
- Dispatch route format changed: `type` field replaced with `action` field
- Route can now have variable length with multiple charging stops
- Drone needs to read `action` per waypoint instead of hardcoded step indices
