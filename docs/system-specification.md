# System Specification – Drone Delivery

## Team 13
- Mathias Harkestad Bæverfjord
- Adrian Gunnar Lauterer
- Magnus Bøyum Ystgaard
- Marius Hatlen Nøst

---

## Background
The popularity of drone-based delivery services has increased significantly in recent years. By ignoring roads, drone-based delivery offers faster logistics and reduced traffic congestion. The drones only need to arrive at a pickup station and then reach the customers. Using drones also allows for the implementation of priority levels for the user, allowing express deliveries that prioritize one delivery over others.

The drones do, however, come with logistical constraints that limit their effectiveness. The restricted battery capacity of unmanned aerial vehicles creates a fundamental operational barrier, as units must complete round trips to delivery destinations within a single charge cycle. When the distance required exceeds available power reserves, deliveries are delayed by being forced to take charging stops or complete returns to base, compromising service reliability.

Additionally, should the power management be insufficient or other problems occur, the drone could lose propulsion in the middle of a mission. This will result in a failed mission, and possibly a lost package, loss of the drone, or even an accident.

The impact of failed and late missions could be too much for the logistics company to bear. Customer dissatisfaction could cause customers to prefer normal deliveries over drone deliveries, reducing the demand for this system. Additionally, any lost package or drone is a direct loss to the logistics company. We wish to reduce this loss by improving battery management in drone-based deliveries.

---

## Vision Statement
We aim to make package deliveries more efficient by using autonomous self-charging UAVs. Reducing cost and increasing customer satisfaction by optimizing pathing and battery charging while tending to varying customer priority levels.

---

## Objectives

* **Time reduction:**
  Fully autonomous deliveries should be faster than current solutions.
  *Measurement:* Keep track of time used from order to delivery.
  *Goal:* The autonomous solution should use 10% less time than current solutions.
* **Priority levels & Priority inversion:**
  An express delivery user should on average wait less than a standard delivery user.
  *Measurement:* Keep track of the time used from order to delivery.
  *Goal:* The express delivery should be at least 10% faster than a standard delivery.
* **No charging enroute:**
  There should be no charging enroute to a customer less than 2km away.
  *Measurement:* Keep track of whether a delivery under 2km required charging or not.
  *Goal:* At least 95% of deliveries under 2km without charging enroute.

---

## Stakeholders

| Stakeholder | Major Value | Attitudes | Major Interests | Constraints |
| :--- | :--- | :--- | :--- | :--- |
| **End users** | Faster deliveries | Somewhat positive, sceptical towards higher payment and noise. | Minimizing waiting times; Placing as many orders as they wish. | Paying additional amounts towards delivery; depends on package cost and noise management. |
| **Parcel provider** | More satisfied customers; Higher throughput of delivered product. | Positive, willing to pay more per delivery as overall profits will go up. | Making profit based on high-speed deliveries; Outsourcing delivery logistics. | Giving up profit to pay for delivery service. |
| **System owner** | Providers have better business, meaning growth for the system owner; Drones can be allocated quicker. | Very positive, motivated towards maximizing profit. | Supplying as many providers as possible with delivery infrastructure. | Money to be placed towards developing and implementing the new system. |
| **Aviation control** | Airspace safety, risk mitigation, and usage certification. | Could be negative regarding cluttering airspace and safety. | Reducing risk and traffic management. | Maximum altitude, flying over airports/military, and noise. |

---

## Selected Use Cases

### UC-1: Calculate route (Optimizing drone delivery routes)
* **Primary actor:** Server (routing algorithm) | **Secondary actor:** User, drones
* **Description:** Determines the most efficient route for a delivery by selecting the most suitable drone and calculating the optimal flight path. The objective is to minimize delivery time while respecting battery capacity, payload limits, and environmental constraints. Produces a drone-route pairing as its output.
* **Trigger:** Invoked by UC-2 when a validated delivery request requires drone and route assignment.
* **Preconditions:**
  1. A validated delivery request with destination and priority is available.
  2. At least one drone is registered in the system.
  3. Routing and environmental data systems are online.
* **Postconditions:**
  1. A suitable drone is selected.
  2. An optimal flight path is generated.
  3. The drone-route pairing is returned to UC-2 for dispatch.
* **Normal flow:**
  1. System receives delivery request with destination, package details, and priority.
  2. System fetches environmental data (weather, restricted airspace, obstructions).
  3. System retrieves operational data from all drones (location, battery, payload, status).
  4. System filters out drones lacking sufficient battery or payload capacity.
  5. System generates possible flight paths for eligible drones (including required charging stops).
  6. System scores drone-route combinations by ETA, priority, and battery consumption.
  7. System selects the combination with the shortest practical delivery time.
  8. System returns the selected drone and route to UC-2.
* **Alternate flow:**
  * *1.1 Delivery requires charging stop:* No eligible drone can complete the route on a single charge. System evaluates routes with intermediate charging, selects the most efficient pairing, and returns it.
  * *1.2 Closer drone becomes available:* While routing, a new drone becomes available. System discards the previous pairing, recalculates, and returns the new pairing.
* **Exceptions:**
  * *1.E1 No drone has sufficient capacity:* Places delivery in queue until a drone becomes available/recharged.
  * *1.E2 Data unavailable:* Delays optimization until routing/environmental data is retrieved.
* **Business rules:** Routing must account for priority levels. Charging stops mid-delivery minimized. No charging stops for routes under 2 km.

### UC-2: Place an order
* **Primary Actor:** End User | **Secondary actor:** Drone Management System
* **Description:** An authenticated user requests a delivery by specifying destination, details, and priority. System validates the request, invokes UC-1, and dispatches the drone. User receives confirmation and ETA.
* **Trigger:** User initiates request via web portal.
* **Preconditions:**
  1. User is authenticated and has payment method on file.
  2. Drone management system is active.
  3. At least one drone is registered.
* **Postconditions:**
  1. Order stored in logistics queue.
  2. Drone assigned to order (via UC-1).
  3. Delivery process initiated.
  4. User receives confirmation with ETA.
* **Normal Flow:**
  1. User specifies destination and package details.
  2. User selects priority (Express/Standard).
  3. System verifies package limits against available drones.
  4. System invokes UC-1 for optimal pairing.
  5. System stores order and assigns drone.
  6. System initiates delivery.
  7. System notifies user with confirmation and ETA.
* **Alternate Flow:**
  * *2.1 Insufficient battery:* UC-1 finds no direct route. Assigns alternative drone or route with charging stop, notifies user of slight delay.
  * *2.2 No drone available:* Flags order as delayed, notifies user with estimated wait time or cancel option.
* **Exceptions:**
  * *2.E1 Package exceeds limits:* Error displayed, user asked to modify package.
  * *2.E2 User not authorized:* Error displayed, incident logged.
  * *2.E3 System failure:* Error displayed, automated restart attempted.

### UC-3: Drone Position Tracking
* **Primary Actor:** Server | **Secondary actors:** Drone, User
* **Description:** Server reports the current whereabouts of a drone relevant to a given order, including an updated ETA.
* **Trigger:** User sends request for delivery status.
* **Preconditions:** Drone and User are connected to the server.
* **Postconditions:** User is informed of delivery status and ETA.
* **Normal flow:**
  1. User requests delivery status.
  2. Server requests current position from drone.
  3. Drone sends position (lat, lon, timestamp).
  4. Server calculates updated ETA.
  5. Server responds to user with position and ETA.
* **Alternative Flow:**
  * *3.1 No valid GPS:* Drone responds but lacks valid GPS. Server falls back to last known position, calculates ETA, and warns user that live location is unavailable.
* **Exceptions:**
  * *3.E1 Drone disconnected:* Server cannot reach drone, notifies user with error, attempts to reconnect in background.

---

## Architectural Models and Diagrams
The following markdown files in the `docs` folder contain the visual diagrams corresponding to this specification:

* **Deployment**: [Deployment Diagram](deployment-diagram.md)
* **Contracts**: [MQTT Contract](mqtt-contract.md)
* **Sequence Diagrams**:
  * [Use Case 1 (Calculate route)](use-case-1-sequence.md)
  * [Use Case 2 (Place an order)](use-case-2-sequence.md)
  * [Use Case 3 (Drone Position Tracking)](use-case-3-sequence.md)
* **State Machines**:
  * [State Machine 1: Drone Behaviour](state-machine-1-drone.md)
  * [State Machine 2: Server Delivery](state-machine-2-server.md)
  * [State Machine 3: Server Clients](state-machine-3-clients.md)
