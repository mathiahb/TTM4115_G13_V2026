import logging
import stmpy
from config_loader import load_config, parse_args, get_drone_id
from simulated_drone import SimulatedDrone
from mqtt_handler import DroneMQTTHandler
from sense_hat_display import SenseHATDisplay

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main function - Initialize and run the simulated drone with MQTT communication and Sense HAT display."""
    logger.info("=== Drone State Machine Started ===")

    # Load configuration
    args = parse_args()
    config = load_config(args.config)
    drone_id = get_drone_id(config, args.drone_id)

    # Create drone with config
    drone = SimulatedDrone(config)
    stm_drone = drone.create_state_machine()

    driver = stmpy.Driver()
    driver.add_stm(stm_drone)

    # Initialize Sense HAT display (optional, gracefully handles if not available)
    display = SenseHATDisplay(config)
    drone.display = display
    if display.enabled:
        logger.info("Sense HAT display initialized")
        display.set_state('standby')

    # Initialize MQTT handler
    mqtt_handler = DroneMQTTHandler(drone, driver, config, drone_id=drone_id)
    mqtt_handler.connect()
    mqtt_handler.start()

    # Store MQTT handler reference in drone for event publishing
    drone.mqtt_handler = mqtt_handler

    logger.info("Drone state machine, MQTT handler, and Sense HAT display configured")
    logger.info(f"Drone ID: {drone_id}")
    logger.info("Use SimulatedDrone.set_customer_target(x, y) before assignment_received")

    driver.start()

    return driver, stm_drone, drone, mqtt_handler, display


if __name__ == "__main__":
    driver, stm, drone, mqtt_handler, display = main()
    # Example usage:
    # drone.set_customer_target(8.0, 5.0)
    # driver.send('assignment_received', 'drone_stm')
    # driver.wait_until_finished()
