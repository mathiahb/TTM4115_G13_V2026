import time
import unittest

import stmpy

from simulated_drone import SimulatedDrone

TIMEOUT = 10.0


def wait_for_state(machine, state_name, timeout=TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if machine.state == state_name:
            return True
        time.sleep(0.05)
    raise AssertionError(
        f"Timed out waiting for state '{state_name}', current='{machine.state}'"
    )


class DroneStateMachineTest(unittest.TestCase):
    def setUp(self):
        self.drone = SimulatedDrone()
        self.stm = self.drone.create_state_machine()
        self.driver = stmpy.Driver()
        self.driver.add_machine(self.stm)
        self.drone.driver = self.driver
        self.driver.start()
        wait_for_state(self.stm, "standby")

    def tearDown(self):
        self.driver.stop()

    def test_standby_to_warehouse_to_pickup(self):
        self.drone.location = {"lat": 63.4157, "lon": 10.4060, "gps_valid": True}
        dispatch = {
            "order_id": "ORD-TEST",
            "route": [
                {"lat": 63.4157, "lon": 10.4060, "type": "waypoint"},
                {"lat": 63.4158, "lon": 10.4061, "type": "waypoint"},
                {"lat": 63.4160, "lon": 10.4065, "type": "destination"},
            ],
        }
        self.driver.send("assign_delivery", "drone_stm", args=[dispatch])
        wait_for_state(self.stm, "travel_to_warehouse")
        wait_for_state(self.stm, "order_pickup", timeout=15)
        self.assertEqual(self.drone.order_id, "ORD-TEST")

    def test_pickup_to_customer_to_deliver(self):
        self.drone.location = {"lat": 63.4157, "lon": 10.4060, "gps_valid": True}
        dispatch = {
            "order_id": "ORD-TEST2",
            "route": [
                {"lat": 63.4157, "lon": 10.4060, "type": "waypoint"},
                {"lat": 63.4158, "lon": 10.4061, "type": "waypoint"},
                {"lat": 63.4160, "lon": 10.4065, "type": "destination"},
            ],
        }
        self.driver.send("assign_delivery", "drone_stm", args=[dispatch])
        wait_for_state(self.stm, "order_pickup", timeout=15)
        wait_for_state(self.stm, "travel_to_customer")
        wait_for_state(self.stm, "deliver", timeout=15)

    def test_deliver_to_return_to_standby(self):
        self.drone.location = {"lat": 63.4157, "lon": 10.4060, "gps_valid": True}
        dispatch = {
            "order_id": "ORD-TEST3",
            "route": [
                {"lat": 63.4157, "lon": 10.4060, "type": "waypoint"},
                {"lat": 63.4158, "lon": 10.4061, "type": "waypoint"},
                {"lat": 63.4160, "lon": 10.4065, "type": "destination"},
            ],
        }
        self.driver.send("assign_delivery", "drone_stm", args=[dispatch])
        wait_for_state(self.stm, "deliver", timeout=30)
        wait_for_state(self.stm, "travel_return")
        wait_for_state(self.stm, "standby", timeout=30)
        self.assertIsNone(self.drone.order_id)

    def test_battery_depleted_resumes_travel(self):
        self.drone.location = {"lat": 63.4157, "lon": 10.4060, "gps_valid": True}
        self.drone.battery_level = 0.001
        dispatch = {
            "order_id": "ORD-BAT",
            "route": [
                {"lat": 63.4157, "lon": 10.4060, "type": "waypoint"},
                {"lat": 63.4200, "lon": 10.4100, "type": "waypoint"},
                {"lat": 63.4300, "lon": 10.4200, "type": "destination"},
            ],
        }
        self.driver.send("assign_delivery", "drone_stm", args=[dispatch])
        wait_for_state(self.stm, "charging", timeout=15)
        self.assertEqual(self.drone.resume_target, "travel_to_warehouse")
        wait_for_state(self.stm, "travel_to_warehouse", timeout=60)


if __name__ == "__main__":
    unittest.main()
