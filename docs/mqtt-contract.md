# MQTT Communication Contract

This document defines the communication contract over MQTT between the Drones and the Server. It describes the data schemas, topics, and how each channel connects to our use cases and architectural models.

## Architecture Overview

As described in the [Deployment Diagram](deployment-diagram.md), communication between the Drone execution environment and the Server execution environment flows through an MQTT Broker. To ensure loose coupling and reliable message passing, the communication is divided into three distinct channels based on the `drone_id`.

## 1. Telemetry Channel (`drones/{drone_id}/telemetry`)

**Direction:** Drone → Server
**Purpose:** Continuous periodic updates (every 1-5s) of the drone's position, battery level, and current state.

**Architectural Connections:**
*   **Use Case 1 (Calculate route):** The Server uses this real-time data to know drone locations and battery levels to select the optimal drone for a new delivery.
*   **Use Case 3 (Drone Position Tracking):** The Server uses the `location` data to calculate updated ETAs for the user.
*   **State Machine 1 (Drone Behaviour):** The `state` enum maps directly to the active state in the drone's state machine (e.g., `Standby`, `Charge`, `Travel`).

### JSON Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DroneTelemetry",
  "description": "Periodic telemetry data sent from drone to server for monitoring and route planning.",
  "type": "object",
  "required": ["drone_id", "timestamp", "location", "battery_level", "max_payload", "state"],
  "properties": {
    "drone_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "location": {
      "type": "object",
      "required": ["lat", "lon", "gps_valid"],
      "properties": {
        "lat": { "type": "number", "minimum": -90, "maximum": 90 },
        "lon": { "type": "number", "minimum": -180, "maximum": 180 },
        "gps_valid": { "type": "boolean" }
      },
      "additionalProperties": false
    },
    "battery_level": { "type": "number", "minimum": 0, "maximum": 100 },
    "max_payload": { "type": "number", "minimum": 0 },
    "state": {
      "type": "string",
      "enum": ["standby", "charging", "travel_to_warehouse", "order_pickup", "travel_to_customer", "deliver", "travel_return"]
    }
  },
  "additionalProperties": false
}
```

### Sample Message
```json
{
  "drone_id": "D-042",
  "timestamp": "2026-04-13T14:32:10Z",
  "location": {
    "lat": 63.4305,
    "lon": 10.3951,
    "gps_valid": true
  },
  "battery_level": 72.4,
  "max_payload": 2.5,
  "state": "travel_to_customer"
}
```

---

## 2. Dispatch Channel (`drones/{drone_id}/dispatch`)

**Direction:** Server → Drone
**Purpose:** Commands from the Server to assign a new delivery or reroute an in-flight drone. 

**Architectural Connections:**
*   **Use Case 1 (Calculate route) / Use Case 2 (Place an order):** After UC-1 calculates the optimal pairing, the Server sends this payload to dispatch the drone.
*   **State Machine 2 (Server Delivery):** Triggered when the server transitions to the `Dispatch` or `Reroute` states.

### JSON Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DroneDispatch",
  "description": "Delivery assignment or reroute command sent from server to drone.",
  "type": "object",
  "required": ["order_id", "package_info", "route"],
  "properties": {
    "order_id": { "type": "string" },
    "package_info": {
      "type": "object",
      "required": ["weight", "priority"],
      "properties": {
        "weight": { "type": "number", "minimum": 0 },
        "priority": {
          "type": "string",
          "enum": ["express", "standard"]
        }
      },
      "additionalProperties": false
    },
    "route": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["lat", "lon", "type"],
        "properties": {
          "lat": { "type": "number", "minimum": -90, "maximum": 90 },
          "lon": { "type": "number", "minimum": -180, "maximum": 180 },
          "type": {
            "type": "string",
            "enum": ["waypoint", "charging_stop", "destination"]
          }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

### Sample Message
```json
{
  "order_id": "ORD-9876",
  "package_info": {
    "weight": 1.2,
    "priority": "express"
  },
  "route": [
    { "lat": 63.4305, "lon": 10.3951, "type": "waypoint" },
    { "lat": 63.4320, "lon": 10.4000, "type": "charging_stop" },
    { "lat": 63.4350, "lon": 10.4100, "type": "destination" }
  ]
}
```

---

## 3. Events Channel (`drones/{drone_id}/events`)

**Direction:** Drone → Server
**Purpose:** Discrete state-change notifications and anomaly alerts. Sent with higher QoS (e.g., QoS 1) to ensure the Server accurately tracks the drone's lifecycle and intercepts failures.

**Architectural Connections:**
*   **State Machine 1 (Drone Behaviour):** The `event_type` enum values correspond directly to the transition triggers that move the drone between states (e.g., `batteryDepleted`, `fullyCharged`, `arrived`, `packageLoaded`).
*   **State Machine 2 (Server Delivery):** Critical events like `battery_depleted` unexpected drops will trigger the Server's `Recalculate Drone Path` state.

### JSON Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "DroneEvent",
  "description": "Discrete state-change event sent from drone to server when a transition or anomaly occurs.",
  "type": "object",
  "required": ["drone_id", "timestamp", "event_type"],
  "properties": {
    "drone_id": { "type": "string" },
    "order_id": { "type": ["string", "null"] },
    "timestamp": { "type": "string", "format": "date-time" },
    "event_type": {
      "type": "string",
      "enum": ["arrived", "package_loaded", "delivery_completed", "battery_depleted", "fully_charged", "gps_lost", "connection_restored"]
    },
    "message": { "type": "string" }
  },
  "additionalProperties": false
}
```

### Sample Message
```json
{
  "drone_id": "D-042",
  "order_id": "ORD-9876",
  "timestamp": "2026-04-13T14:45:02Z",
  "event_type": "delivery_completed",
  "message": "Package dropped at destination."
}
```