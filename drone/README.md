# Drone Module

A simulated autonomous delivery drone implementation using state machines, MQTT communication, and Raspberry Pi Sense HAT integration.

## Overview

This module implements a complete drone delivery system with the following components:

- **State Machine**: STMPY-based state machine managing drone operations (standby, charging, travel, delivery)
- **2D Movement Simulation**: Simulates drone movement on a 2D plane with battery drain management
- **MQTT Communication**: Publishes telemetry and events; receives dispatch commands from server
- **Sense HAT Display**: Optional LED matrix visualization of drone state (for Raspberry Pi deployment)

## Files

### Core Modules

#### `simulated_drone.py`
- **`DroneConfig`**: Configuration class for adjustable parameters
  - `TRAVEL_SPEED`: Units per second (default: 3.0)
  - `BATTERY_DRAIN_PER_SECOND`: Battery % loss per second (default: 1.5)
  - `ARRIVAL_THRESHOLD`: Distance to consider "arrived" (default: 0.25)
  - `MOVEMENT_UPDATE_INTERVAL`: Timer interval in ms (default: 500)

- **`SimulatedDrone`**: Main drone class
  - Manages drone state, position, battery level, and package status
  - Implements all state entry/exit and event handlers
  - Provides 2D movement simulation with physics
  - Integrates with MQTT handler and Sense HAT display

#### `main.py`
- Entry point for the drone system
- Initializes stmpy driver, SimulatedDrone, DroneMQTTHandler, and SenseHATDisplay
- Starts all subsystems

#### `mqtt_handler.py`
- **`DroneMQTTHandler`**: MQTT communication handler
- Publishes telemetry (position, battery, state) every 5 seconds on `drones/{drone_id}/telemetry`
- Subscribes to dispatch commands on `drones/{drone_id}/dispatch`
- Publishes events on `drones/{drone_id}/events`
- Configurable broker host/port and drone ID

#### `sense_hat_display.py`
- **`SenseHATDisplay`**: Optional LED matrix visualization
- Maps drone states to RGB colors:
  - **STANDBY**: Green
  - **CHARGE**: Yellow
  - **TRAVEL_TO_WAREHOUSE**: Blue (animated)
  - **ORDER_PICKUP**: Cyan
  - **TRAVEL_TO_CUSTOMER**: Blue (animated)
  - **DELIVER**: Red
  - **TRAVEL_RETURN**: Purple (animated)
- Special event animations (battery_depleted, fully_charged, arrived, delivery_completed)
- Gracefully disables if Sense HAT not available

#### `test.py`
- Comprehensive state transition tests
- Verifies complete delivery cycles
- Exercises all states and transitions

## State Machine

States:
```
initial → standby ↔ charge
              ↓
        travel_to_warehouse
              ↓
        order_pickup
              ↓
        travel_to_customer ↔ charge
              ↓
            deliver
              ↓
        travel_return ↔ charge
              ↓
           standby
```

Key features:
- Battery depletion can trigger charging from any travel state
- Movement updates every 500ms (configurable) during travel
- Position-based arrival detection with threshold
- Automatic battery drain based on distance and speed

## Configuration

### Drone Behavior

Edit `DroneConfig` in `simulated_drone.py`:

```python
class DroneConfig:
    TRAVEL_SPEED = 3.0                    # units/second
    BATTERY_DRAIN_PER_SECOND = 1.5       # %/second
    ARRIVAL_THRESHOLD = 0.25             # distance units
    MOVEMENT_UPDATE_INTERVAL = 500       # milliseconds
```

### MQTT Connection

Edit `mqtt_handler.py` initialization in `main.py`:

```python
mqtt_handler = DroneMQTTHandler(
    drone, 
    driver, 
    broker_host="localhost",  # MQTT broker address
    broker_port=1883,         # MQTT broker port
    drone_id="drone_001"      # Unique drone identifier
)
```

## Usage

### Basic Usage

```bash
cd drone
python3 main.py
```

This starts the drone in standby state with:
- State machine running
- MQTT connected (if broker available)
- Sense HAT display active (if available)

### Programmatic Usage

```python
from main import main

driver, stm, drone, mqtt_handler, display = main()

# Set delivery target (lat, lon in degrees or x, y in meters)
drone.set_customer_target(8.0, 5.0)

# Send delivery assignment
driver.send('assignment_received', 'drone_stm')

# Wait for completion
# driver.wait_until_finished()
```

### Testing

```bash
python3 test.py
```

Runs complete state transition tests covering all states and critical paths.

## MQTT Contract

### Telemetry (Drone → Server)
Topic: `drones/{drone_id}/telemetry`

```json
{
  "drone_id": "string",
  "timestamp": "ISO 8601",
  "location": {
    "lat": "number",
    "lon": "number",
    "height": "number"
  },
  "battery_level": "number",
  "max_payload": "number",
  "state": "string"
}
```

### Dispatch (Server → Drone)
Topic: `drones/{drone_id}/dispatch`

```json
{
  "order_id": "string",
  "package_info": {
    "weight": "number",
    "priority": "string"
  },
  "route": [
    {
      "lat": "number",
      "lon": "number",
      "type": "string"
    }
  ]
}
```

### Events (Drone → Server)
Topic: `drones/{drone_id}/events`

```json
{
  "drone_id": "string",
  "order_id": "string | null",
  "timestamp": "ISO 8601",
  "event_type": "string",
  "message": "string"
}
```

Event types: `arrived`, `package_loaded`, `delivery_completed`, `battery_depleted`, `fully_charged`, `gps_lost`, `connection_restored`

## Dependencies

- **stmpy**: State machine framework
- **paho-mqtt**: MQTT client library
- **sense-hat**: (Optional) Raspberry Pi Sense HAT library

Install dependencies:

```bash
pip install stmpy paho-mqtt sense-hat
```

Note: `sense-hat` is only required on Raspberry Pi; the system gracefully disables it on other platforms.

## Architecture Integration

This module is designed to integrate with:

1. **Server**: Receives dispatch commands and publishes drone state/events via MQTT
2. **Raspberry Pi**: Optional visual feedback via Sense HAT LED matrix
3. **MQTT Broker**: Central communication hub (e.g., Mosquitto)

## Development Notes

- All state entry/exit actions update displays and publish events
- The movement simulation uses discrete time steps for battery drain calculation
- Travel timers are one-shot and must be restarted each cycle (handled in `update_travel_position`)
- The drone starts at warehouse position (0, 0)
- Battery level is capped at 0-100%

## Future Extensions

- IMU integration for motion tracking
- Real GPS/altitude processing
- Dynamic obstacle avoidance
- Multi-drone coordination
- Priority-based task scheduling
