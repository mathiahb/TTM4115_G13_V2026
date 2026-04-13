# Deployment Diagram

This document contains the system's deployment diagram based on the provided architecture.

## PlantUML Representation

PlantUML natively supports UML deployment diagrams and perfectly captures the semantics of the architecture.

```plantuml
@startuml
skinparam roundcorner 10
skinparam defaultTextAlignment center

node "<<device>>\nCharging Station" as Station

node "<<device>>\nPC" as PC {
  artifact "<<artifact>>\nBrowser" as Browser
}

node "<<device>>\nServer" as Server {
  artifact "<<artifact>>\nRouting Algorithm" as Algorithm
}

node "<<device>>\nMobile Phone" as Phone {
  artifact "<<artifact>>\nDelivery App" as App
}

node "<<external service>>\nWeather API" as Weather

node "<<device>>\nDrone" as Drone

' Relationships
PC "*" -right- "1" Server : <<HTTPS>>
Station "*" -down- "1" Server : <<MQTT>>
Server "1" -right- "*" Phone : <<HTTPS>>
Server "1" -down- "1" Weather : <<HTTPS>>
Server "1" -down- "*" Drone : <<MQTT>>

@enduml
```

## Mermaid Representation

Mermaid is widely supported in markdown renderers (like GitHub/GitLab). While it doesn't have a strict UML deployment diagram type, we can represent it using a flowchart.

```mermaid
flowchart TD
    %% Nodes
    Station["«device»<br/>Charging Station"]
    
    subgraph PC_Node ["«device» PC"]
        Browser["«artifact»<br/>Browser"]
    end
    
    subgraph Server_Node ["«device» Server"]
        Algorithm["«artifact»<br/>Routing Algorithm"]
    end
    
    subgraph Phone_Node ["«device» Mobile Phone"]
        App["«artifact»<br/>Delivery App"]
    end
    
    Weather["«external service»<br/>Weather API"]
    
    Drone["«device»<br/>Drone"]

    %% Edges
    Station -- "«MQTT»<br/>* : 1" --- Server_Node
    PC_Node -- "«HTTPS»<br/>* : 1" --- Server_Node
    Server_Node -- "«HTTPS»<br/>1 : *" --- Phone_Node
    Server_Node -- "«HTTPS»<br/>1 : 1" --- Weather
    Server_Node -- "«MQTT»<br/>1 : *" --- Drone
```
