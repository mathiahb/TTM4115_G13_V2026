import stmpy
import logging
class ClientState:
    """
    State machine representing a client's order session in the server.
    """
    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger(__name__)
    def on_init(self):
        self.logger.info(f"[{self.name}] Initializing client session.")
    def on_cancelled(self):
        self.logger.info(f"[{self.name}] Client cancelled the order.")
    def on_order_finished(self):
        self.logger.info(f"[{self.name}] Order finished. Moving to payment.")
    def on_aborted(self):
        self.logger.info(f"[{self.name}] Payment aborted.")
    def on_paid(self):
        self.logger.info(f"[{self.name}] Payment successful. Session complete.")
    def terminate_session(self):
        self.logger.info(f"[{self.name}] Session terminated.")

def create_client_machine(name):
    client = ClientState(name)
    initial = {
        'source': 'initial',
        'target': 'waiting_for_user',
        'effect': 'on_init'
    }
    t_cancelled = {
        'trigger': 'cancelled',
        'source': 'waiting_for_user',
        'target': 'terminated',
        'effect': 'on_cancelled; terminate_session'
    }
    t_order_finished = {
        'trigger': 'orderFinished',
        'source': 'waiting_for_user',
        'target': 'waiting_for_payment',
        'effect': 'on_order_finished'
    }
    t_aborted = {
        'trigger': 'aborted',
        'source': 'waiting_for_payment',
        'target': 'terminated',
        'effect': 'on_aborted; terminate_session'
    }
    t_paid = {
        'trigger': 'paid',
        'source': 'waiting_for_payment',
        'target': 'terminated',
        'effect': 'on_paid; terminate_session'
    }
    machine = stmpy.Machine(
        name=name,
        transitions=[initial, t_cancelled, t_order_finished, t_aborted, t_paid],
        obj=client
    )
    return machine, client



# For testing independently
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    driver = stmpy.Driver()
    machine, client = create_client_machine("client_1")

    driver.add_machine(machine)
    driver.start()

    import time
    time.sleep(0.1)
    driver.send('orderFinished', 'client_1')
    time.sleep(0.1)
    driver.send('paid', 'client_1')
    time.sleep(0.1)
    driver.stop()
