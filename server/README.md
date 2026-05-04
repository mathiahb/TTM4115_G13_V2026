# Server

Flask webserver and STMPY state machines for managing drone delivery orders.

## Files

- `main.py`: Flask app with REST API and web dashboard. Handles shop browsing, order creation, drone selection, and session management.
- `mqtt_client.py`: MQTT client. Subscribes to drone telemetry and events, publishes dispatch commands.
- `delivery_state.py`: Delivery state machine. Plans routes with haversine distance and charging stops, processes drone lifecycle events.
- `client_state.py`: Client state machine. Tracks the order from creation through payment to termination.
- `config_loader.py`: Parses CLI arguments and loads `config.yaml`. Provides helpers for server settings, MQTT config, shops, drones, and delivery config.
- `config.yaml`: Config for server, MQTT topics, shops, drones, delivery ranges, battery thresholds, and default customer location.
- `templates/index.html` and `static/`: Web dashboard frontend files.

## State machines

Client state machine:
- initial to waiting_for_user (on_init)
- waiting_for_user to terminated on cancelled
- waiting_for_user to waiting_for_payment on orderFinished
- waiting_for_payment to terminated on aborted
- waiting_for_payment to terminated on paid
- waiting_for_user to terminated on orderFailed
- waiting_for_payment to terminated on orderFailed

Delivery state machine:
- initial to monitoring
- monitoring to calculating_path or recalculating_path on scheduleDelivery (function-based: `evaluate_delivery` checks battery level against `min_battery_for_delivery` threshold)
- calculating_path to dispatched on t_calc timer
- recalculating_path to dispatched on t_recalc timer
- dispatched to at_warehouse on drone_arrived
- dispatched to in_transit on package_loaded
- at_warehouse to in_transit on package_loaded
- in_transit to completed on delivery_completed
- dispatched, at_warehouse, or in_transit to recalculating_path on battery_depleted
- dispatched, at_warehouse, or in_transit to failed on drone_error
- gps_lost and connection_restored are self-transitions on dispatched, at_warehouse, and in_transit
- fully_charged is a self-transition on dispatched, at_warehouse, and in_transit

## Running

    python main.py
    # or
    python main.py -c config.yaml

Then open the browser at the configured host and port (default http://localhost:5000).

## Configuration

Edit `config.yaml` to change:

- Server host, port, and debug mode
- Flask secret key (env variable or default)
- MQTT broker settings and topic prefix
- Shop inventory and locations
- Drone fleet details (locations, battery, payload)
- Default customer delivery location
- Delivery range and battery constraints

## Dependencies

- Flask
- stmpy
- paho-mqtt
- PyYAML

Install with pip or use the provided `pyproject.toml` / `uv.lock`.
