# Server

Flask webserver and STMPY state machines for managing drone delivery orders.

## Files

- `main.py`: Flask app with REST API and web dashboard. Handles shop browsing, order creation, drone selection, and session management.
- `mqtt_client.py`: MQTT client. Subscribes to drone telemetry and events, publishes dispatch commands.
- `delivery_state.py`: Delivery state machine. Plans routes with haversine distance and charging stops, processes drone lifecycle events.
- `client_state.py`: Client state machine. Tracks the order from creation through payment to termination.
- `config_loader.py`: Parses CLI arguments and loads `config.yaml`.
- `config.yaml`: Config for server, MQTT topics, shops, drones, delivery ranges, and battery thresholds.
- `templates/index.html` and `static/`: Web dashboard frontend files.

## State machines

Client state machine:
- initial to waiting_for_user
- waiting_for_user to terminated on cancelled
- waiting_for_user to waiting_for_payment on orderFinished
- waiting_for_payment to terminated on aborted
- waiting_for_payment to terminated on paid

Delivery state machine:
- initial to monitoring
- monitoring to calculating_path or recalculating_path on scheduleDelivery
- calculating_path to dispatched on t_calc timer
- recalculating_path to dispatched on t_recalc timer
- dispatched to at_warehouse on drone_arrived
- at_warehouse to in_transit on package_loaded
- in_transit to completed on delivery_completed
- dispatched, at_warehouse, or in_transit to recalculating_path on battery_depleted

The delivery machine also handles gps_lost and connection_restored as self-transitions during active flight.

## Running

    python main.py
    # or
    python main.py -c config.yaml

Then open the browser at the configured host and port (default http://localhost:5000).

## Configuration

Edit `config.yaml` to change:

- Server host and port
- MQTT broker settings
- Shop inventory and locations
- Drone fleet details
- Delivery range and battery constraints

## Dependencies

- Flask
- stmpy
- paho-mqtt
- PyYAML

Install with pip or use the provided `pyproject.toml` / `uv.lock`.