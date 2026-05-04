# Drone Simulator

A simulated autonomous delivery drone using STMPY state machines, MQTT, and an optional Raspberry Pi Sense HAT.

## Files

- `main.py`: Entry point and state machine (`DroneSTM`). Manages states, battery, routes, telemetry loop, and manual error recovery.
- `simulator.py`: Movement math (haversine, lat/lon conversion) and battery drain/charge helpers.
- `mqtt_handler.py`: MQTT client. Subscribes to dispatch commands, publishes telemetry and events.
- `display.py`: Optional Sense HAT LED matrix. Shows state color, battery level, and route progress.
- `config_loader.py`: Parses CLI arguments and loads `config.yaml`. Provides helpers for MQTT, simulation, battery, charging, and display config.
- `config.yaml`: Runtime settings for drone identity, MQTT, simulation speeds, battery, charging, and display colors.

## State machine

States: `standby`, `travel`, `execute`, `error`.

`assign_delivery` is deferred in `travel`, `execute`, and `error` (queued until a state that handles it is reached).

Transitions:
- initial to standby
- standby to travel on assign_delivery (calls `on_dispatch` with payload)
- travel to execute on arrived_at_waypoint
- execute to travel on action_done (next waypoint)
- execute to standby on to_standby (route complete)
- standby to error on error
- travel to error on error (battery_depleted)
- execute to error on error
- error to standby on fixed (manual reset)

Actions:
- `travel`: Moves toward current waypoint every simulation tick, drains battery. Sends `error` on battery depletion.
- `execute` with `delivery`: Publishes `delivery_completed` event, advances route.
- `execute` with `pickup`: Publishes `arrived` event, waits 2s pickup timer, then publishes `package_loaded` and advances.
- `execute` with `charge`/`charging`: Charges battery per tick until `fully_charged_threshold`, then publishes `fully_charged` and advances.
- `execute` with `return`/`none`: Immediately advances route.
- `error`: Waits for manual fix via Enter key, which resets battery to 100% and location to home.

Express mode (`priority` or `express` delivery) multiplies movement speed and battery drain rate.

## Running

    python main.py
    # or
    python main.py -c config.yaml --drone-id 1

Press Enter while the drone is in the `error` state to trigger a manual reset to `standby`. Ctrl+C to stop.

## Configuration

Edit `config.yaml` to change:

- Drone ID, home location, initial battery, max payload
- Telemetry publish interval and simulation tick rate
- MQTT broker host/port, topic prefix, and QoS
- Movement speed, battery drain rate, express multipliers
- Battery fully-charged threshold
- Charge time (full charge duration in minutes)
- Display colors and enable/disable Sense HAT

## Dependencies

- `stmpy`
- `paho-mqtt`
- `PyYAML`
- `sense-hat` (optional, for LED matrix)

Install with pip or use the provided `pyproject.toml` / `uv.lock`.
