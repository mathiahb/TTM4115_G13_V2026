# State Machine 1: Drone Behaviour

This document contains the state machine diagram representing the behavior of the drone.

## PlantUML Representation

```plantuml
@startuml
skinparam roundcorner 10
skinparam state {
  BackgroundColor LightYellow
  BorderColor Coral
}

state "Standby" as Standby
state "Charge" as ChargeTop
state "Travel" as TravelToWh
state "Order pickup" as OrderPickup
state "Travel" as TravelToCustomer
state "Charge" as ChargeBottom
state "Deliver" as Deliver
state "Travel" as TravelReturn
state choice1 <<choice>>

[*] --> Standby

Standby -right-> ChargeTop : batteryDepleted /
ChargeTop -left-> Standby : fullyCharged /

Standby --> choice1 : assignDelivery /

choice1 -left-> TravelToWh : [not at warehouse]
choice1 --> OrderPickup : [at warehouse]

TravelToWh -right-> OrderPickup : arrived /
OrderPickup -right-> TravelToCustomer : packageLoaded /

TravelToCustomer -down-> ChargeBottom : batteryDepleted /
ChargeBottom -up-> TravelToCustomer : fullyCharged /

TravelToCustomer -down-> Deliver

Deliver -right-> TravelReturn : deliveryCompleted /

TravelReturn -up-> ChargeTop : batteryDepleted /
ChargeTop -down-> TravelReturn : fullyCharged /

TravelReturn -left-> Standby

@enduml
```
