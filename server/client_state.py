import stmpy
import logging

logger = logging.getLogger(__name__)


# NOTE: This state machine is scaffolded for future implementation of real
# client-facing interactions (e.g. waiting for user input, payment confirmation).
# Currently the server bypasses it by sending orderFinished and paid immediately
# on order creation, so the machine races to "terminated" without pausing.
# See server/main.py around the create_client_machine call.
class ClientState:
    def __init__(self, order_id: str, orders: dict):
        self.order_id = order_id
        self.orders = orders

    def on_init(self):
        logger.info("[%s] Client session started", self.order_id)

    def on_order_finished(self):
        order = self.orders.get(self.order_id)
        if order:
            order["client_state"] = "awaiting_payment"
        logger.info("[%s] Order finished, awaiting payment", self.order_id)

    def on_paid(self):
        order = self.orders.get(self.order_id)
        if order:
            order["client_state"] = "paid"
        logger.info("[%s] Payment confirmed", self.order_id)

    def on_cancelled(self):
        order = self.orders.get(self.order_id)
        if order:
            order["client_state"] = "cancelled"
            order["status"] = "cancelled"
        logger.info("[%s] Order cancelled", self.order_id)

    def on_aborted(self):
        order = self.orders.get(self.order_id)
        if order:
            order["client_state"] = "aborted"
            order["status"] = "aborted"
        logger.info("[%s] Payment aborted", self.order_id)

    def on_failed(self):
        order = self.orders.get(self.order_id)
        if order:
            order["client_state"] = "failed"
            order["status"] = "failed"
        logger.error("[%s] Order failed", self.order_id)


def create_client_machine(order_id: str, orders: dict) -> stmpy.Machine:
    obj = ClientState(order_id, orders)

    transitions = [
        {"source": "initial", "target": "waiting_for_user", "effect": "on_init"},
        {
            "trigger": "cancelled",
            "source": "waiting_for_user",
            "target": "terminated",
            "effect": "on_cancelled",
        },
        {
            "trigger": "orderFinished",
            "source": "waiting_for_user",
            "target": "waiting_for_payment",
            "effect": "on_order_finished",
        },
        {
            "trigger": "aborted",
            "source": "waiting_for_payment",
            "target": "terminated",
            "effect": "on_aborted",
        },
        {
            "trigger": "paid",
            "source": "waiting_for_payment",
            "target": "terminated",
            "effect": "on_paid",
        },
        {
            "trigger": "orderFailed",
            "source": "waiting_for_user",
            "target": "terminated",
            "effect": "on_failed",
        },
        {
            "trigger": "orderFailed",
            "source": "waiting_for_payment",
            "target": "terminated",
            "effect": "on_failed",
        },
    ]

    return stmpy.Machine(
        name=f"client_{order_id}",
        transitions=transitions,
        obj=obj,
    )
