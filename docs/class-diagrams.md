# Developer class diagrams

These diagrams are selective views of the implemented architecture. They omit
most methods and fields so that inheritance, retained objects, and short-lived
dependencies remain visible. In the diagrams:

* `<|--` means inheritance,
* `*--` means an owned nested part,
* `-->` means a retained association without an ownership claim, and
* `..>` means temporary use or creation.

## Public clients and connectors

All five public clients inherit from abstract `BaseClient`. Each concrete
client creates and retains the connector for its provider endpoint. The base
classes show only the operations that define the main request lifecycle.

```mermaid
classDiagram
    class BaseClient {
        <<abstract>>
        +query()
        +create_web_service()
    }
    class ESMShakeMapClient
    class RRSMShakeMapClient
    class RRSMPeakMotionClient
    class EMSCFeltReportClient
    class USGSComCatClient

    class BaseWebServiceConnector {
        <<abstract>>
        +query()
        +parse_response()
    }
    class ESMShakeMapConnector
    class RRSMShakeMapConnector
    class RRSMPeakMotionConnector
    class EMSCFeltReportConnector
    class USGSComCatConnector

    BaseClient <|-- ESMShakeMapClient
    BaseClient <|-- RRSMShakeMapClient
    BaseClient <|-- RRSMPeakMotionClient
    BaseClient <|-- EMSCFeltReportClient
    BaseClient <|-- USGSComCatClient

    BaseWebServiceConnector <|-- ESMShakeMapConnector
    BaseWebServiceConnector <|-- RRSMShakeMapConnector
    BaseWebServiceConnector <|-- RRSMPeakMotionConnector
    BaseWebServiceConnector <|-- EMSCFeltReportConnector
    BaseWebServiceConnector <|-- USGSComCatConnector

    ESMShakeMapClient "1" *-- "1" ESMShakeMapConnector : creates and retains
    RRSMShakeMapClient "1" *-- "1" RRSMShakeMapConnector : creates and retains
    RRSMPeakMotionClient "1" *-- "1" RRSMPeakMotionConnector : creates and retains
    EMSCFeltReportClient "1" *-- "1" EMSCFeltReportConnector : creates and retains
    USGSComCatClient "1" *-- "1" USGSComCatConnector : creates and retains
```

## Connectors and parsers

Connectors create a parser while handling a successful response and retain the
parsed result, not the parser instance. The dependency arrows therefore denote
temporary creation. `USGSComCatClient` also creates a temporary
`USGSComCatParser` to select exact product-content URLs from parsed event
metadata; product response parsing still belongs to `USGSComCatConnector`.
RRSM ShakeMap inherits the ESM-compatible XML parsing implementation and
overrides only provider-specific error construction.

```mermaid
classDiagram
    class BaseParser {
        <<abstract>>
        +parse()
        +validate()
    }
    class ESMShakeMapParser
    class RRSMShakeMapParser
    class RRSMPeakMotionParser
    class EMSCFeltReportParser
    class USGSComCatParser

    class ESMShakeMapConnector
    class RRSMShakeMapConnector
    class RRSMPeakMotionConnector
    class EMSCFeltReportConnector
    class USGSComCatConnector
    class USGSComCatClient

    BaseParser <|-- ESMShakeMapParser
    ESMShakeMapParser <|-- RRSMShakeMapParser
    BaseParser <|-- RRSMPeakMotionParser
    BaseParser <|-- EMSCFeltReportParser
    BaseParser <|-- USGSComCatParser

    ESMShakeMapConnector ..> ESMShakeMapParser : creates per response
    RRSMShakeMapConnector ..> RRSMShakeMapParser : creates per response
    RRSMPeakMotionConnector ..> RRSMPeakMotionParser : creates per response
    EMSCFeltReportConnector ..> EMSCFeltReportParser : creates per response
    USGSComCatConnector ..> USGSComCatParser : creates per response
    USGSComCatClient ..> USGSComCatParser : selects product URL
```

## Result data models

Every implemented result model extends `BaseDataStructure`. Composition arrows
show the nested model objects stored in collection fields or private lists.
The Peak Motion dataset retains its separately constructed event model through
`set_event_data()`, which is shown as an association rather than composition.
ShakeMap event data is likewise separate from station amplitudes, and Felt
Report event data is separate from felt-intensity data; no direct relationship
between either pair is implied.

The model classes are organized by scientific representation, not by provider.
In particular, ESM, RRSM, and USGS ComCat parsers reuse the established
ShakeMap models, while both EMSC felt reports and USGS ComCat DYFI use
`FeltReportIntensityData`. Felt intensities remain provider-native dictionary
records inside that model rather than instances of `FeltReportEventData`.

```mermaid
classDiagram
    class BaseDataStructure

    class ShakeMapEventData
    class ShakeMapStationAmplitudes
    class ShakeMapStationNode
    class ShakeMapComponentNode

    class PeakMotionEventData
    class PeakMotionData
    class PeakMotionStationData
    class PeakMotionChannelData

    class FeltReportEventData
    class FeltReportIntensityData

    BaseDataStructure <|-- ShakeMapEventData
    BaseDataStructure <|-- ShakeMapStationAmplitudes
    BaseDataStructure <|-- ShakeMapStationNode
    BaseDataStructure <|-- ShakeMapComponentNode

    BaseDataStructure <|-- PeakMotionEventData
    BaseDataStructure <|-- PeakMotionData
    BaseDataStructure <|-- PeakMotionStationData
    BaseDataStructure <|-- PeakMotionChannelData

    BaseDataStructure <|-- FeltReportEventData
    BaseDataStructure <|-- FeltReportIntensityData

    ShakeMapStationAmplitudes "1" *-- "0..*" ShakeMapStationNode : stations
    ShakeMapStationNode "1" *-- "0..*" ShakeMapComponentNode : components

    PeakMotionData "1" --> "0..1" PeakMotionEventData : stores event_data
    PeakMotionData "1" *-- "0..*" PeakMotionStationData : stations
    PeakMotionStationData "1" *-- "0..*" PeakMotionChannelData : channels
```
