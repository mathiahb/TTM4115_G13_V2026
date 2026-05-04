# MQTT Contract

MQTT topics and their datatypes. All topics are prefixed with `ttm4115/team13/` by default (configurable in `config.yaml`).

## 1. Telemetry Channel

**Topic:** `ttm4115/team13/drones/{drone_id}/telemetry`
**Direction:** Drone -> Server

```json
{
  "drone_id": "string",
  "timestamp": "string", // ISO 8601 date-time
  "location": {
    "lat": "number", // -90 to 90
    "lon": "number", // -180 to 180
    "gps_valid": "boolean"
  },
  "battery_level": "number", // 0 to 100
  "max_payload": "number", // >= 0
  "state": "string" // standby | travel | execute | error
}
```

## 2. Dispatch Channel

**Topic:** `ttm4115/team13/drones/{drone_id}/dispatch`
**Direction:** Server -> Drone

```json
{
  "order_id": "string",
  "package_info": {
    "weight": "number", // >= 0
    "priority": "string" // priority | standard | express
  },
  "route": [
    {
      "lat": "number", // -90 to 90
      "lon": "number", // -180 to 180
      "action": "string" // takeoff | charging | pickup | delivery | return
    }
  ]
}
```

## 3. Events Channel

**Topic:** `ttm4115/team13/drones/{drone_id}/events`
**Direction:** Drone -> Server

```json
{
  "drone_id": "string",
  "order_id": "string | null",
  "timestamp": "string", // ISO 8601 date-time
  "event_type": "string", // arrived | package_loaded | delivery_completed | battery_depleted | fully_charged | error
  "message": "string"
}
```

The server maps incoming event types to state machine triggers:
- `arrived` -> `drone_arrived`
- `package_loaded` -> `package_loaded`
- `delivery_completed` -> `delivery_completed`
- `battery_depleted` -> `battery_depleted`
- `fully_charged` -> `fully_charged`
- `error` -> `drone_error`
