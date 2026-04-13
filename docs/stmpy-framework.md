# STMPY Framework Guide

`stmpy` is a simple yet powerful framework for implementing state machines in Python. It allows developers to define state machine logic in terms of states, transitions, timers, and messages, providing a robust architecture for event-driven applications.

## 1. Architecture

The `stmpy` architecture relies on two primary classes:
- **`Machine`**: Represents a state machine diagram and manages states, transitions, and timers. It bounds to a user-defined Python object that provides the actual execution logic (methods) called during transitions or state changes.
- **`Driver`**: Maintains event queues and controls the execution of one or multiple state machines. A driver contains a single thread, executing machines strictly sequentially. This provides a "run-to-completion" execution model, ensuring that only one transition is processed at a time and preventing concurrent access issues for shared variables.

## 2. Core Concepts

### 2.1 States
States define the various conditions the state machine can be in. 
- **Reserved Names**: The names `initial` and `final` are reserved. Every machine must have exactly one initial transition starting from `initial`. Transitioning to `final` terminates the machine.
- **Actions**: States can have `entry` and `exit` actions, executed when entering or leaving the state.
- **Do-Actions**: A state can declare a `do` action that runs in its own thread, allowing long-running tasks without blocking the state machine. Once finished, it automatically dispatches a `done` event.
- **Deferred Events**: States can "defer" events. If a deferred event occurs, it is ignored in the input queue until the machine transitions to a state that does not defer it.

### 2.2 Transitions
Transitions define how the state machine moves between states. They are declared as dictionaries.
- **Simple Transitions**: Contain a `source` state, `target` state, a `trigger` (signal name), and an `effect`.
- **Initial Transitions**: Start from the `initial` state and do not require a trigger.
- **Internal Transitions**: Triggered events that execute actions without leaving the current state (no entry/exit actions are fired).
- **Compound Transitions**: Enable conditional logic (decisions) by referencing a Python function that computes and returns the target state based on the event's data.

### 2.3 Transition Effects
The `effect` of a transition (or an entry/exit action) is a semicolon-separated string of method calls on the bound object.
- Example: `'m1; m2(1, True, "a"); m3(*)'`
- The `*` argument passes the event's `args` and `kwargs` (data from messages) to the method.
- You can also call built-in actions like `start_timer("t1", 100)` or `stop_timer("t2")` directly in the effect string.

### 2.4 Timers
Timers are used to trigger transitions after a specific duration (in milliseconds).
- **Starting**: `start_timer("timer_name", 1000)` can be called in a transition effect, state action, or directly from code via `Machine.start_timer()`.
- **Triggering**: A transition simply uses the timer's name as its `trigger`.
- **Stopping**: `stop_timer("timer_name")` halts an active timer.

### 2.5 Messages
Transitions can be triggered by messages (events) sent from the machine itself, other machines, or external Python code.
- **Sending**: `Machine.send("msg_name")` sends a message to the same machine. `Driver.send("msg_name", "target_machine_name")` sends a message to a specific machine in the driver.
- **Data Payload**: Messages can carry data via `args` and `kwargs`. Methods in the transition effect with a `*` signature will receive this data.

## 3. Code Examples

### Example 1: Basic Tick-Tock State Machine
This example demonstrates states, simple transitions, and timers.

```python
from stmpy import Machine, Driver

class Tick:
    def __init__(self):
        self.ticks = 0
        self.tocks = 0

    def on_init(self):
        print('Init!')

    def on_tick(self):
        print('Tick!')
        self.ticks += 1

    def on_tock(self):
        print('Tock!')
        self.tocks += 1

driver = Driver()
tick = Tick()

# Transitions
t0 = {'source': 'initial', 'target': 's_tick', 'effect': 'on_init; start_timer("tick", 1000)'}
t1 = {'trigger': 'tick', 'source': 's_tick', 'target': 's_tock', 'effect': 'on_tick; start_timer("tock", 1000)'}
t2 = {'trigger': 'tock', 'source': 's_tock', 'target': 's_tick', 'effect': 'on_tock; start_timer("tick", 1000)'}

# Machine Setup
stm_tick = Machine(transitions=[t0, t1, t2], obj=tick, name='stm_tick')
tick.stm = stm_tick

# Driver Setup
driver.add_stm(stm_tick)
driver.start()
driver.wait_until_finished()
```

### Example 2: Advanced States (Entry, Do, and Deferred Events)
This example highlights state dictionaries for more complex behavior.

```python
# Extended state declarations
state_idle = {
    'name': 'idle',
    'entry': 'op_init',
    'defer': 'start_event'  # Ignores start_event while idle
}

state_active = {
    'name': 'active',
    'entry': 'op_start; start_timer("t1", 500)',
    'do': 'long_running_task',
    'exit': 'op_stop'
}

# The transition leaving a state with a 'do' action must trigger on 'done'
t_done = {'source': 'active', 'trigger': 'done', 'target': 'idle'}
```

## 4. Graphviz Integration
`stmpy` includes built-in support for generating state machine diagrams using Graphviz.

```python
import stmpy

# Assuming `stm` is a configured stmpy.Machine
dot_graph = stmpy.get_graphviz_dot(stm)

with open("graph.gv", "w") as f:
    f.write(dot_graph)

# Can be converted via CLI: dot -Tsvg graph.gv -o graph.svg
```