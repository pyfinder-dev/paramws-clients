# Contributing to paramws-clients

## How to contribute

- Fork the repository and create a focused branch.
- Follow the existing code style and add deterministic tests for changed
  behavior.
- Run the normal offline contribution check:

  ```bash
  python -m unittest discover -s tests/unit -v
  ```

- Submit a pull request with a clear description of the change and its
  verification.

Live integration tests are a separate provider-contract check:

```bash
python -m unittest discover -s tests/integration -v
```

They contact external ESM, EMSC, ORFEUS RRSM, and USGS ComCat services and are
not required as an ordinary pull-request check. When run, temporary provider
unavailability may skip according to the project's accepted classification;
unexpected HTTP 4xx responses, TLS failures, and incompatible successful
responses remain failures.

## Reporting issues

Use the
[GitHub issue tracker](https://github.com/pyfinder-dev/paramws-clients/issues).
Include reproducible steps, the expected behavior, the observed behavior, and
the affected provider or client.

## Code style

- Follow PEP 8.
- Match the project's existing comment and docstring style.
- Preserve provider-native scientific meaning and units.
