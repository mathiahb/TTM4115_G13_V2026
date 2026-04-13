import stmpy
import logging


class ServerDeliveryState:
    """
    State machine representing the Server Delivery behavior.
    Based on the UML diagram in docs/state-machine-2-server.md
    """

    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger(__name__)

    def on_monitoring(self):
        self.logger.info(f"[{self.name}] State: Monitoring - Waiting for delivery requests.")

    def on_calculate_path(self):
        self.logger.info(f"[{self.name}] State: Calculate path - Calculating optimal drone route.")

    def on_recalculate_path(self):
        self.logger.info(f"[{self.name}] State: Recalculate Drone Path - Modifying route due to battery drainage.")

    def on_dispatch(self):
        self.logger.info(f"[{self.name}] State: Dispatch - Drone has been dispatched on standard route.")

    def on_reroute(self):
        self.logger.info(f"[{self.name}] State: Reroute - Drone has been rerouted to nearest charger.")

    def evaluate_delivery(self, battery_level=100):
        """
        Compound transition (choice): returns the target state based on battery level.
        [Battery OK] -> 'calculate_path'
        [Unexpected Battery Drainage] -> 'recalculate_drone_path'
        """
        self.logger.info(f"[{self.name}] Evaluating scheduleDelivery (Battery: {battery_level}%)...")
        if battery_level >= 20:
            self.logger.info(f"[{self.name}] Decision: [Battery OK]")
            return 'calculate_path'
        else:
            self.logger.info(f"[{self.name}] Decision: [Unexpected Battery Drainage]")
            return 'recalculate_drone_path'


def create_server_delivery_machine(name):
    server = ServerDeliveryState(name)

    t0 = {
        'source': 'initial',
        'target': 'monitoring'
    }
    t_schedule = {
        'trigger': 'scheduleDelivery',
        'source': 'monitoring',
        'function': server.evaluate_delivery,
        'targets': 'calculate_path recalculate_drone_path'
    }
    t_calculated = {
        'trigger': 'calc_timer',
        'source': 'calculate_path',
        'target': 'dispatch',
        'effect': 'start_timer("dispatch_timer", 100)'
    }
    t_recalculated = {
        'trigger': 'recalc_timer',
        'source': 'recalculate_drone_path',
        'target': 'reroute',
        'effect': 'start_timer("reroute_timer", 100)'
    }
    t_dispatch_transit = {
        'trigger': 'dispatch_timer',
        'source': 'dispatch',
        'target': 'monitoring'
    }
    t_reroute_transit = {
        'trigger': 'reroute_timer',
        'source': 'reroute',
        'target': 'monitoring'
    }

    states = [
        {'name': 'monitoring', 'entry': 'on_monitoring'},
        {'name': 'calculate_path', 'entry': 'on_calculate_path'},
        {'name': 'recalculate_drone_path', 'entry': 'on_recalculate_path'},
        {'name': 'dispatch', 'entry': 'on_dispatch'},
        {'name': 'reroute', 'entry': 'on_reroute'},
    ]

    machine = stmpy.Machine(
        name=name,
        transitions=[
            t0,
            t_schedule,
            t_calculated,
            t_recalculated,
            t_dispatch_transit,
            t_reroute_transit,
        ],
        states=states,
        obj=server
    )
    return machine, server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    driver = stmpy.Driver()
    machine, server = create_server_delivery_machine("server_1")

    driver.add_machine(machine)
    driver.start()

    import time
    time.sleep(0.1)

    print("\n--- Simulating Normal Delivery (Battery 95%) ---")
    driver.send('scheduleDelivery', 'server_1', args=[95])
    time.sleep(1)

    print("\n--- Simulating Low Battery Delivery (Battery 15%) ---")
    driver.send('scheduleDelivery', 'server_1', args=[15])
    time.sleep(1)

    driver.stop()
