# Simplified MQTT Contract

This document contains only the MQTT channels and their datatypes. Possible values are listed in comments.

## 1. Telemetry Channel

**Topic:** `drones/{drone_id}/telemetry`  
**Direction:** Drone → Server

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
  "state": "string" // standby | charging | travel_to_warehouse | order_pickup | travel_to_customer | deliver | travel_return
}
```

## 2. Dispatch Channel

**Topic:** `drones/{drone_id}/dispatch`  
**Direction:** Server → Drone

```json
{
  "order_id": "string",
  "package_info": {
    "weight": "number", // >= 0
    "priority": "string" // priority | standard
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

**Topic:** `drones/{drone_id}/events`  
**Direction:** Drone → Server

```json
{
  "drone_id": "string",
  "order_id": "string | null",
  "timestamp": "string", // ISO 8601 date-time
  "event_type": "string", // arrived | package_loaded | delivery_completed | battery_depleted | fully_charged | gps_lost | connection_restored
  "message": "string"
}
```
