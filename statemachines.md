# State Machines

State machines are implemented using [stmpy](https://falkr.github.io/stmpy/) and run on a shared `stmpy.Driver` in `server/main.py`.

## DroneSTM — `drone/main.py`

Manages a single drone's physical state: movement between waypoints, executing actions (pickup, delivery, charging), and error recovery.

```mermaid
stateDiagram-v2
    [*] --> standby

    state standby {
        entry / on_enter_standby
    }
    state travel {
        entry / on_enter_travel: start sim_tick timer
        exit / on_exit_travel: stop sim_tick timer
        assign_delivery : deferred
        sim_tick / on_travel_tick
    }
    state execute {
        entry / on_enter_execute: start sim_tick timer
        exit / on_exit_execute: stop timers
        assign_delivery : deferred
        sim_tick / on_execute_tick
        pickup_timer / on_pickup_done
    }
    state error {
        entry / on_enter_error
        assign_delivery : deferred
    }

    standby --> travel : assign_delivery / on_dispatch(route, order)
    travel --> execute : arrived_at_waypoint
    travel --> error : error / on_error("battery_depleted")
    execute --> travel : action_done / on_next_waypoint
    execute --> standby : to_standby
    execute --> error : error / on_error("unknown")
    standby --> error : error / on_error("unknown")
    error --> standby : fixed / on_reset
```

## DeliveryState — `server/delivery_state.py`

Tracks the lifecycle of a delivery order from scheduling through completion or failure. One instance per order.

```mermaid
stateDiagram-v2
    [*] --> monitoring

    monitoring --> calculating_path : scheduleDelivery [battery OK] / evaluate_delivery
    monitoring --> recalculating_path : scheduleDelivery [battery low] / evaluate_delivery

    calculating_path --> dispatched : t_calc (500ms timer) / on_calculate_path
    recalculating_path --> dispatched : t_recalc (500ms timer) / on_recalculate_path

    dispatched --> at_warehouse : drone_arrived / on_drone_arrived
    dispatched --> in_transit : package_loaded / on_package_loaded
    at_warehouse --> in_transit : package_loaded / on_package_loaded

    in_transit --> completed : delivery_completed / on_delivery_completed

    dispatched --> recalculating_path : battery_depleted / on_battery_depleted
    at_warehouse --> recalculating_path : battery_depleted / on_battery_depleted
    in_transit --> recalculating_path : battery_depleted / on_battery_depleted

    dispatched --> dispatched : fully_charged
    at_warehouse --> at_warehouse : fully_charged
    in_transit --> in_transit : fully_charged

    dispatched --> dispatched : gps_lost / on_gps_lost
    at_warehouse --> at_warehouse : gps_lost / on_gps_lost
    in_transit --> in_transit : gps_lost / on_gps_lost

    dispatched --> dispatched : connection_restored
    at_warehouse --> at_warehouse : connection_restored
    in_transit --> in_transit : connection_restored

    dispatched --> failed : drone_error / on_drone_error
    at_warehouse --> failed : drone_error / on_drone_error
    in_transit --> failed : drone_error / on_drone_error
```

## ClientState — `server/client_state.py`

Intended to track the client session (order placement, payment). Currently scaffolded for future implementation — the server bypasses it by sending `orderFinished` and `paid` immediately on order creation, so the machine transitions straight to `terminated` without pausing.

```mermaid
stateDiagram-v2
    [*] --> waiting_for_user : on_init

    waiting_for_user --> waiting_for_payment : orderFinished / on_order_finished
    waiting_for_user --> terminated : cancelled / on_cancelled
    waiting_for_user --> terminated : orderFailed / on_failed

    waiting_for_payment --> terminated : paid / on_paid
    waiting_for_payment --> terminated : aborted / on_aborted
    waiting_for_payment --> terminated : orderFailed / on_failed
```
