# paramws-clients

`paramws-clients` is a Python library for querying supported earthquake
parametric-data services and representing their provider data. It supports
Python 3.9 and later.

## Supported clients and results

Import the five public clients from `paramws.clients`:

| Provider and service | Client | Dataset key | Dataset value type |
| --- | --- | --- | --- |
| ESM ShakeMap | `ESMShakeMapClient` | `station_amplitudes` | `ShakeMapStationAmplitudes` |
| ORFEUS RRSM ShakeMap | `RRSMShakeMapClient` | `station_amplitudes` | `ShakeMapStationAmplitudes` |
| ORFEUS RRSM Peak Motion | `RRSMPeakMotionClient` | `peak_motion` | `PeakMotionData` |
| EMSC Felt Reports | `EMSCFeltReportClient` | `felt_intensities` | `FeltReportIntensityData` |
| USGS ComCat | `USGSComCatClient` | `shakemap` | `ShakeMapStationAmplitudes` |
| USGS ComCat | `USGSComCatClient` | `dyfi` | `FeltReportIntensityData` |

For the implementation structure and class relationships, see the
[developer class diagrams](docs/class-diagrams.md).

Every concrete client has this query signature:

```python
query(event_id=None, **other_options)
```

A query that returns normally produces exactly:

```python
code, event_data, datasets
```

`event_data` describes the earthquake separately from the associated
scientific datasets. `datasets` is always a dictionary with the semantic keys
shown above; the dictionary is the common container, not a normalized
cross-provider scientific model.

Dataset-key presence records caller intent:

- an unrequested dataset key is absent;
- a requested, successful dataset contains its provider-specific model;
- a requested dataset that fails or is unavailable remains present with
  value `None`.

For ComCat, `producttype="shakemap"` requests only `shakemap`,
`producttype="dyfi"` requests only `dyfi`, and omitting `producttype` requests
both datasets supported by this client.

## Installation

Install the checked-out source package into the intended Python environment
from the repository root:

```bash
python -m pip install .
```

The installation uses the package metadata in `pyproject.toml`. The consuming
project owns its environment, installation mode, and revision-pinning policy.

## Usage

This ESM example accesses station data through the semantic dataset
dictionary without assuming particular stations or measurements:

```python
from paramws.clients import ESMShakeMapClient, ShakeMapStationAmplitudes

client = ESMShakeMapClient()
code, event_data, datasets = client.query(event_id="20170524_0000045")

station_amplitudes = datasets["station_amplitudes"]
if station_amplitudes is not None:
    assert isinstance(station_amplitudes, ShakeMapStationAmplitudes)
    stations = station_amplitudes.get_stations()
```

ComCat product selection controls both dictionary membership and network
retrieval:

```python
from paramws.clients import (
    FeltReportIntensityData,
    USGSComCatClient,
)

client = USGSComCatClient()
code, event_data, datasets = client.query(
    event_id="ci38457511",
    producttype="dyfi",
)

assert "shakemap" not in datasets
felt_intensities = datasets["dyfi"]
if felt_intensities is not None:
    assert isinstance(felt_intensities, FeltReportIntensityData)
    intensity_records = felt_intensities.get_intensities()
```

Omitting `producttype` requests both supported ComCat datasets:

```python
from paramws.clients import USGSComCatClient

code, event_data, datasets = USGSComCatClient().query(
    event_id="ci38457511",
)
shakemap = datasets["shakemap"]
dyfi = datasets["dyfi"]
```

RRSM Peak Motion keeps event information and measurements conceptually
separate:

```python
from paramws.clients import PeakMotionData, RRSMPeakMotionClient

code, event_data, datasets = RRSMPeakMotionClient().query(
    event_id="20170524_0000045",
)
peak_motion = datasets["peak_motion"]
if peak_motion is not None:
    assert isinstance(peak_motion, PeakMotionData)
    assert event_data is not peak_motion
```

## Options and failures

`event_id` is required. Other caller options are validated by the applicable
connector:

- an unsupported option name is ignored with a provider- and
  endpoint-specific `WARNING`;
- a supported option with an invalid value raises `InvalidOptionValue`;
- an attempted override of a fixed internal selection is ignored with a
  `WARNING` that identifies the retained value.

The public clients apply those rules as follows:

| Client | Caller-controlled options beyond `event_id` | Fixed selections |
| --- | --- | --- |
| `ESMShakeMapClient` | `catalog` (`ESM`, `ISC`, `USGS`, `EMSC`, or `INGV`), `flag` (`0` or `all`), and `encoding` (`UTF-8`/`utf-8` or `US-ASCII`/`us-ascii`) | event and station `format` values |
| `RRSMShakeMapClient` | none | `type="event"` for event data and omitted `type` for stations |
| `RRSMPeakMotionClient` | none; `type` is unsupported | the explicit event identifier |
| `EMSCFeltReportClient` | none | testimony inclusion is enabled for intensities and disabled for event data |
| `USGSComCatClient` | `producttype` (`shakemap` or `dyfi`); omission means both | `format="geojson"` and the explicit event identifier |

The returned `code` represents the complete requested query. It is `200` only
when every required request succeeds and parses. For HTTP failures, the first
failing status in the client's request order is retained; a later success does
not overwrite it. Independent requests can still retain useful partial event
or dataset data while the overall code remains non-`200`. Failures without an
HTTP status raise an exception instead of fabricating a status code.

Public failure categories are:

| Failure | Meaning |
| --- | --- |
| `MissingRequiredOption` | the required event identifier was omitted |
| `InvalidOptionValue` | a recognized option has an unsupported value |
| `DatasetNotAvailableError` | an event exists but lacks a requested supported dataset or its exact required content |
| `ValueError` | an HTTP `200` response fails parser, schema, or scientific validation |
| `TimeoutError` | connection or response timeout after retries |
| `ConnectionError` | DNS or connection failure after retries |
| `ssl.SSLError` | TLS failure; it is not retried |

The package-specific exceptions are available from their established public
modules:

```python
from paramws.clients.base_client import MissingRequiredOption
from paramws.clients.services import InvalidOptionValue
from paramws.clients.services.usgs import DatasetNotAvailableError
```

Each HTTP attempt has a fixed ten-second timeout. A request makes at most
three total attempts with a fixed two-second delay between attempts. Only
timeouts, DNS/connection failures, and HTTP `429`, `500`, `502`, `503`, and
`504` are retried. TLS failures, other HTTP statuses, option errors, dataset
absence, and deterministic parsing or validation failures are not retried.

## Scientific representation

Values preserve the provider's scientific meaning and representation. The
library does not impose a common unit system across ESM, RRSM, EMSC, and USGS
data. Units and uncertainty are retained where a provider supplies them, and
provider-native string flags and optional or empty values are not recast into
a synthetic common convention.

Some optional getters were added to the shared ShakeMap models for
ComCat-specific fields such as units, uncertainty, flags, geometry, station
type, and product metadata. Those getters return `None` for ESM or RRSM data
when those providers do not supply the corresponding fields.

## Logging

The package configures its own non-propagating `paramws` logger. Its default
output is `./paramws.log` in the process working directory, or the path in
`PARAMWS_LOG_FILE` when that environment variable is set. File logging:

- uses `DEBUG` for the logger and handler;
- appends through `RotatingFileHandler`;
- rotates at 1,000,000 bytes and retains seven backups;
- contains standard levels plus the package-owned `OK` level.

`OUTPUT_MODE` in `paramws/utils/customlogger.py` is the single configuration
switch between file output and colored console output; set it before package
import. If the selected log file cannot be opened, logging falls back to the
colored console handler and emits a warning containing the path and underlying
error.

## Testing and CI

Deterministic unit tests are the normal offline contribution check:

```bash
python -m unittest discover -s tests/unit -v
```

Live integration tests contact ESM, EMSC, ORFEUS RRSM, and USGS ComCat:

```bash
python -m unittest discover -s tests/integration -v
```

Live tests skip only accepted temporary provider-unavailability outcomes
(timeouts, DNS/connection failures, HTTP `429`, and HTTP 5xx), with a clear
reason. Unexpected HTTP 4xx responses, TLS failures, parser/schema failures,
and scientific contract violations fail.

GitHub Actions runs the offline unit matrix on pushes and pull requests for
Python 3.9 through 3.14. Live tests run only on pushes to `master` or manual
dispatch. CI also builds and inspects the wheel and source distribution,
installs the wheel into a clean target, and verifies public imports.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidance.


## Provider documentation

These pages describe the providers’ complete interfaces. `paramws-clients`
accepts only the options documented for each client above.

| Service | Official documentation |
| --- | --- |
| ESM ShakeMap | [Query options](https://esm-db.eu/esmws/shakemap/1/query-options.html) |
| ORFEUS RRSM | [Service WADL](https://www.orfeus-eu.org/odcws/rrsm/1/application.wadl) · [RRSM overview](https://www.orfeus-eu.org/rrsm/about/) |
| EMSC Felt Reports | [Service page](https://seismicportal.eu/testimonies-ws/) · [Version 1.1 specification](https://www.emsc.eu/Files/epos/specifications/Specs_Testimony-WS.pdf) |
| USGS ComCat | [FDSN Event API](https://earthquake.usgs.gov/fdsnws/event/1/) · [ComCat products and fields](https://earthquake.usgs.gov/data/comcat/) |


## Acknowledgment

**paramws-clients** was initially developed as part of the EU project
“A Digital Twin for Geophysical Extremes”
([DT-GEO](https://dtgeo.eu/)) and received funding from Horizon Europe
under Grant Agreement No 101058129 for the Digital Twin Component (DTC) E6
(“Rapid Source and Shaking Characterization”), which aims to provide rapid
information on ground shaking and warnings for significant earthquakes in
the Euro-Mediterranean region.


## License and conduct

The project is licensed under the MIT License; see [LICENSE](./LICENSE).
Contributors must follow [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

