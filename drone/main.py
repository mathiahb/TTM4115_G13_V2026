import logging
import threading
import time

import stmpy

from config_loader import (
    get_drone_id,
    get_telemetry_interval,
    load_config,
    parse_args,
)
from mqtt_handler import DroneMQTTHandler
from simulated_drone import SimulatedDrone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("drone")


def main():
    args = parse_args()
    config = load_config(args.config)
    drone_id = get_drone_id(config, args.drone_id)

    driver = stmpy.Driver()

    drone = SimulatedDrone(config=config)
    machine = drone.create_state_machine()
    drone.driver = driver

    mqtt_handler = DroneMQTTHandler(
        drone=drone,
        driver=driver,
        config=config,
        drone_id=drone_id,
    )
    drone.mqtt_handler = mqtt_handler

    driver.add_machine(machine)
    driver.start(keep_active=True)

    mqtt_handler.connect()

    stop_event = threading.Event()

    def telemetry_loop():
        interval = get_telemetry_interval(config)
        while not stop_event.is_set():
            mqtt_handler.publish_telemetry()
            stop_event.wait(interval)

    telem_thread = threading.Thread(target=telemetry_loop, daemon=True)
    telem_thread.start()

    logger.info("Drone %s running. Press Ctrl+C to stop.", drone_id)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_event.set()
        mqtt_handler.stop()
        driver.stop()


if __name__ == "__main__":
    main()
