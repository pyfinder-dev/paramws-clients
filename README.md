[![Run tests](https://github.com/pyfinder-dev/paramws-clients/actions/workflows/tests.yml/badge.svg)](https://github.com/pyfinder-dev/paramws-clients/actions/workflows/tests.yml)

# paramws-clients

## Table of Contents
- [Introduction](#paramws-clients)
- [Features](#features)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Use Cases](#use-cases)
- [API Reference](#api-reference)
- [Testing](#testing)
- [License](#license)
- [Acknowledgment](#acknowledgment)

**paramws-clients** is a collection of web service clients for the parametric data providers (ESM, EMSC, RRSM). It initially started as a part of the **pyfinder** package, which is a Python wrapper for the [FinDer](https://docs.gempa.de/sed-eew/current/base/intro-finder.html#finder) (Finite Fault Rupture Detector) library.  

## Features

This package is designed to query the ESM, EMSC and RRSM web services to retrieve the acceleration amplitudes and felt reports. 

This tool is able to query:
- The ESM ```shakemap``` endpoint, using both ```format=event_dat``` for amplitudes and ```format=event``` option to retrieve the basic event information. See the [ESM Shakemap web service](https://esm-db.eu//esmws/shakemap/1/query-options.html) for more information. 

- RRSM ```shakemap``` web service, which also uses the same web service as the ESM. The tool only implements minor changes such as the base service URL and order of options for queries. RRSM queries are slightly different than ESM, and support ```type``` instead of the ```format``` option. The tool is designed to handle these nuances.  

- The same RRSM shakemap data is also retrieved via the ```peak-motions``` service end point. This service returns a json file that includes a list of stations merged with event and amplitude information.  

- The EMSC felt reports, for the basic event information (```includeTestimonies=false```) and intensities (```includeTestimonies=true```).

More information on the web services implemented in this tool are avaliable on:
- RRSM: https://www.orfeus-eu.org/rrsm/about/
- ESM: https://esm-db.eu/#/data_and_services/web_services and https://esm-db.eu//esmws/shakemap/1/
- EMSC: https://www.emsc.eu/Earthquake_data/Data_queries.php

For further information on FinDer, see the references below and [Swiss Seismological Service at ETH Zurich](http://www.seismo.ethz.ch/en/knowledge/earthquake-data-and-analysis-tools/EEW/finite-fault-rupture-detector-finder/) web page.

_**References**:_

> Böse, M., Heaton, T. H., & Hauksson, E., 2012. Real‐time Finite Fault Rupture Detector (FinDer) for large earthquakes. Geophysical Journal International, 191(2), 803–812, doi:10.1111/j.1365-246X.2012.05657.x
>
> Böse, M., Felizardo, C., & Heaton, T. H., 2015. Finite-Fault Rupture Detector (FinDer): Going Real-Time in Californian ShakeAlertWarning System. Seismological Research Letters, 86(6), 1692–1704, doi:10.1785/0220150154
>
> Böse, M., Smith, D., Felizardo, C., Meier, M.-A., Heaton, T. H., & Clinton, J. F., 2018. FinDer v.2: Improved Real-time Ground-Motion Predictions for M2-M9 with Seismic Finite-Source Characterization. Geophysical Journal International, 212(1), 725-742, doi:10.1093/gji/ggx430
>
> Cauzzi, C., Behr, Y. D., Clinton, J., Kastli, P., Elia, L., & Zollo, A., 2016. An Open-Source Earthquake Early Warning Display. Seismological Research Letters, 87(3), 737–742, doi:10.1785/0220150284

## Installation

> **Python Version Requirement:**  
> This package requires **Python 3.9 or higher**.

The package is not yet installable via PyPI. To install locally from source, follow these steps:

1. **Clone the repository and enter the project directory:**
   ```bash
   git clone https://github.com/pyfinder-dev/paramws-clients.git
   cd paramws-clients
   ```

2. **(Recommended) Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # On Unix/macOS
   source .venv/bin/activate
   # On Windows
   .venv\Scripts\activate
   ```

3. If you just want to use the package:
    ```bash
    pip install .
    ```
    
    If you plan to contribute or develop, install the package in **editable mode**:
    ```bash
    pip install -e .
    ```

## Usage Examples
Coming soon

## Use Cases
Coming soon

## API Reference
Coming soon

## Testing
Automated tests are executed on GitHub Actions for every push and pull request. For local development, you can also run the tests manually:

```bash
python run_tests.py
```

Alternatively, if you prefer using `pytest`, install it first:

```bash
pip install pytest
```

Then, trigger the test modules:

```bash
PYTHONPATH=. pytest -v
```

## License
Licensed under the MIT License – see [LICENSE](./LICENSE) for details.

## Acknowledgment
**pyfinder** and this package were initally developed as part of the EU project "A Digital Twin for Geophysical Extremes" (DT-GEO; https://dtgeo.eu/) and has received funding from Horizon Europe under Grant Agreement No 101058129 for the Digital Twin Component (DTC) E6 ("Rapid Source and Shaking Characterization") which aims to provide rapid information on ground shaking and warnings for significant earthquakes in the Euro-Mediterranean region.
