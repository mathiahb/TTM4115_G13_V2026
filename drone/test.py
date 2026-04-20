import time
import unittest
import logging
import stmpy
from simulated_drone import SimulatedDrone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def wait_for_state(machine, state_name, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if machine.state == state_name:
            return True
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for state '{state_name}', current='{machine.state}'")


def wait_for_condition(condition, timeout=5.0, poll_interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(poll_interval)
    raise AssertionError("Timed out waiting for condition")


class SimulatedDroneStateTransitionTest(unittest.TestCase):
    def setUp(self):
        self.drone = SimulatedDrone()
        self.stm = self.drone.create_state_machine()
        self.driver = stmpy.Driver()
        if hasattr(self.driver, 'add_machine'):
            self.driver.add_machine(self.stm)
        else:
            self.driver.add_stm(self.stm)
        self.driver.start()
        wait_for_state(self.stm, 'standby')

    def tearDown(self):
        if hasattr(self.driver, 'stop'):
            self.driver.stop()

    def test_full_state_cycle_and_transitions(self):
        # standby -> charge -> standby
        self.driver.send('battery_depleted', 'drone_stm')
        wait_for_state(self.stm, 'charge')
        self.driver.send('fully_charged', 'drone_stm')
        wait_for_state(self.stm, 'standby')

        # travel_to_warehouse -> charge -> standby by depleting battery en route
        self.drone.position_x = 5.0
        self.drone.position_y = 0.0
        self.drone.battery_level = 0.5
        self.drone.set_customer_target(10.0, 0.0)
        self.driver.send('assignment_received', 'drone_stm')
        wait_for_state(self.stm, 'charge')
        self.driver.send('fully_charged', 'drone_stm')
        wait_for_state(self.stm, 'standby')

        # travel_to_customer -> charge -> standby by depleting during customer travel
        self.drone.position_x = 0.0
        self.drone.position_y = 0.0
        self.drone.at_warehouse = True
        self.drone.battery_level = 100.0
        self.drone.set_customer_target(10.0, 0.0)
        self.driver.send('assignment_received', 'drone_stm')
        wait_for_state(self.stm, 'order_pickup')
        self.drone.battery_level = 0.2
        self.driver.send('package_loaded', 'drone_stm')
        wait_for_state(self.stm, 'charge')
        self.driver.send('fully_charged', 'drone_stm')
        wait_for_state(self.stm, 'standby')

        # travel_return -> charge -> standby by depleting on return leg
        self.drone.position_x = 0.0
        self.drone.position_y = 0.0
        self.drone.at_warehouse = True
        self.drone.battery_level = 100.0
        self.drone.set_customer_target(8.0, 0.0)
        self.driver.send('assignment_received', 'drone_stm')
        wait_for_state(self.stm, 'order_pickup')
        self.driver.send('package_loaded', 'drone_stm')
        wait_for_state(self.stm, 'deliver')
        self.drone.battery_level = 0.2
        self.driver.send('delivery_completed', 'drone_stm')
        wait_for_state(self.stm, 'charge')
        self.driver.send('fully_charged', 'drone_stm')
        wait_for_state(self.stm, 'standby')

        # Normal delivery cycle to traverse travel_return -> standby
        self.drone.position_x = 0.0
        self.drone.position_y = 0.0
        self.drone.at_warehouse = True
        self.drone.battery_level = 100.0
        self.drone.set_customer_target(4.0, 0.0)
        self.driver.send('assignment_received', 'drone_stm')
        wait_for_state(self.stm, 'order_pickup')
        self.driver.send('package_loaded', 'drone_stm')
        wait_for_state(self.stm, 'deliver')
        self.driver.send('delivery_completed', 'drone_stm')
        wait_for_state(self.stm, 'standby')

        self.assertEqual(self.drone.position_x, 0.0)
        self.assertEqual(self.drone.position_y, 0.0)
        self.assertGreater(self.drone.battery_level, 0.0)


if __name__ == '__main__':
    unittest.main()
