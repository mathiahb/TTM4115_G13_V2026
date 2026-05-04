# TTM4115_G13_V2026

Drone delivery system with a Flask server, simulated drones, and MQTT-based communication.

## Running

Start the server:
```bash
cd server && python main.py
```
Server at `http://localhost:5000` (configurable in `server/config.yaml`).

Start a drone:
```bash
cd drone && python main.py
# or with a specific config and drone ID:
python main.py -c config.yaml --drone-id 1
```

MQTT broker is at `mqtt20.iik.ntnu.no:1883` by default (configured in `config.yaml`).
