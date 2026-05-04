# Drone 2

A simulated autonomous delivery drone using STMPY state machines, MQTT, and an optional Raspberry Pi Sense HAT.

## Files

- `main.py`: Entry point and state machine (`DroneSTM`). Manages states, battery, routes, telemetry loop, and manual error recovery.
- `simulator.py`: Movement math (haversine, lat/lon conversion) and battery drain/charge helpers.
- `mqtt_handler.py`: MQTT client. Subscribes to dispatch commands and publishes telemetry and events.
- `display.py`: Optional Sense HAT LED matrix. Shows state color, battery level, and route progress.
- `config_loader.py`: Parses CLI arguments and loads `config.yaml`.
- `config.yaml`: Runtime settings for MQTT, simulation speeds, battery, and display colors.

## State machine

States: `standby`, `travel`, `execute`, `error`.

Transitions:
- initial to standby
- standby to travel on assign_delivery
- travel to execute on arrived_at_waypoint
- execute to travel on action_done (next waypoint)
- execute to standby on to_standby (route complete)
- travel or execute to error on battery depletion or other errors
- error to standby on fixed (manual fix)

During `travel`, the drone moves toward the current waypoint every simulation tick and drains battery. During `execute`, it performs the waypoint action (`pickup`, `delivery`, `charge`, or `return`). Charging happens in `execute` until the battery reaches the configured threshold.

## Running

    python main.py
    # or
    python main.py -c config.yaml --drone-id 1

Press Enter while the drone is in the `error` state to trigger a manual reset to `standby`.

## Configuration

Edit `config.yaml` to change:

- MQTT broker host/port and topics
- Movement speed and battery drain rates
- Express mode multipliers
- Charging thresholds and timing
- Display colors and enable/disable flag

## Dependencies

- `stmpy`
- `paho-mqtt`
- `PyYAML`
- `sense-hat` (optional, for LED matrix)

Install with pip or use the provided `pyproject.toml` / `uv.lock`.