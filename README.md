# TTM4115_G13_V2026

Drone delivery system with a Flask server, simulated drones, and MQTT-based communication.

## Running

All on one system
```bash
docker compose up --build
```

Server at `http://localhost:5001`, MQTT broker on port `1883`.

To run the simulated drones one can run main.py in the drone repo, the same for the server and webclient, run main.py in the server repo.

## Integration Tests

End-to-end tests that spin up the full stack (broker, server, 2 drones) and verify API responses, MQTT message flows, state machine transitions, and delivery cycles through real HTTP and MQTT communication.

```bash
docker compose -f docker-compose.test.yaml up --build --abort-on-container-exit --exit-code-from test-runner
```

### What is tested

- **API** (`test_api.py`): Shops endpoint, order placement, input validation, order retrieval, session isolation
- **MQTT communication** (`test_mqtt_communication.py`): Telemetry publishing and schema, event sequence (arrived → package_loaded → delivery_completed), event contract validation
- **Delivery flow** (`test_delivery_flow.py`): Full happy path, drone returns to standby after delivery, order status progression, concurrent orders to different drones, battery drain during travel, location updates, sequential orders after drone returns
