# -*- coding: utf-8 -*-
"""
Expose event-scoped USGS ComCat data through the public client convention.

One detailed-event request supplies event information and the product index.
The client then retrieves only the requested exact ShakeMap and DYFI contents,
using the established models and the shared connector transport.
"""

import ssl

from paramws.clients.base_client import BaseClient, MissingRequiredOption
from paramws.clients.services.usgs import (
    DatasetNotAvailableError,
    USGSComCatConnector,
    USGSComCatParser,
)
from paramws.utils.customlogger import logger


class USGSComCatClient(BaseClient):
    """
    Retrieve one ComCat event and its requested ShakeMap or DYFI datasets.

    ``producttype`` remains the caller-controlled native selection. Omitting
    it requests both supported datasets in the defined ShakeMap-then-DYFI
    order; the client does not enumerate or download other ComCat products.
    """

    def __init__(self):
        super().__init__()
        self.agency = "USGS"
        self.base_url = "https://earthquake.usgs.gov/fdsnws/event/"
        self.end_point = "query"
        self.version = "1"

        # Event ID and GeoJSON format are fixed per call. Product type is added
        # only when the caller selects one of this client's two datasets.
        self.event_options = {
            "eventid": None,
            "format": "geojson",
        }

        if self.get_web_service() is None:
            self.create_web_service()

    def create_web_service(self) -> USGSComCatConnector:
        """Create a ComCat connector from the client's current configuration."""
        self.ws_client = USGSComCatConnector(
            agency=self.agency,
            base_url=self.base_url,
            end_point=self.end_point,
            version=self.version,
        )
        return self.ws_client

    def query(self, event_id=None, **other_options):
        """
        Return ``code, event_data, datasets`` for one ComCat event.

        Event detail is a prerequisite. After it parses, requested product
        requests are independent: later data is retained even when an earlier
        product is absent, fails transport, fails HTTP, or fails parsing.
        """
        # Clear all prior public and connector results before validating this
        # call. A second reset below records only the valid requested key set.
        self._reset_query_state(())
        self.event_options.clear()
        self.event_options.update({
            "eventid": None,
            "format": "geojson",
        })

        query_options = dict(other_options)

        # The explicit argument and the GeoJSON parser contract own these
        # native fields. Caller attempts are visible in warnings but cannot
        # change event identity or the representation being parsed.
        if "eventid" in query_options:
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; explicit event_id %r remains in effect.",
                self.get_agency(),
                self.get_end_point(),
                "eventid",
                query_options.pop("eventid"),
                event_id,
            )
        if "format" in query_options:
            logger.warning(
                "%s %s ignored caller override of fixed option %r with "
                "value %r; required value %r remains in effect.",
                self.get_agency(),
                self.get_end_point(),
                "format",
                query_options.pop("format"),
                "geojson",
            )

        # producttype is the only caller-controlled supported field. Passing
        # every remaining name through the connector preserves standard
        # invalid-value errors and unsupported-option warnings before network.
        query_options = self.ws_client.validate_options(**query_options)
        producttype = query_options.get("producttype")
        if producttype is None:
            requested_datasets = ("shakemap", "dyfi")
        else:
            requested_datasets = (producttype,)

        # Key presence records caller intent even if the required identifier
        # is missing or a later requested operation cannot populate its value.
        self._reset_query_state(requested_datasets)

        if event_id is None:
            raise MissingRequiredOption("Missing required option: event_id")

        self.event_options["eventid"] = event_id
        self.event_options.update(query_options)
        event_url = self.ws_client.build_url(**self.event_options)

        # Event detail and its product index are prerequisites. An HTTP failure
        # returns immediately; transport and successful-content parsing errors
        # retain their established exception types and prevent product work.
        try:
            event_code, event_data = self.ws_client.query(
                url=event_url,
                response_purpose="event_detail",
            )
        except (TimeoutError, ConnectionError, ssl.SSLError, ValueError) \
                as error:
            logger.error(
                "provider=%r url=%s status=%r dataset=event_detail "
                "outcome=failed reason=%s",
                self.get_agency(),
                USGSComCatConnector._url_for_log(event_url),
                None,
                error,
            )
            raise

        if event_code is None or not 200 <= event_code < 300:
            logger.error(
                "provider=%r url=%s status=%r dataset=event_detail "
                "outcome=failed",
                self.get_agency(),
                USGSComCatConnector._url_for_log(event_url),
                event_code,
            )
            return event_code, self.event_data, self.datasets

        self.set_event_data(event_data)
        parser = USGSComCatParser()
        first_http_failure = None
        first_non_http_failure = None

        # Once event detail is valid, ShakeMap and DYFI are independent. Keep
        # going in requested order so a later usable product remains available
        # even when an earlier selection or request fails.
        for dataset in requested_datasets:
            try:
                content_url = parser.select_product_content(
                    self.event_data,
                    dataset,
                )
            except DatasetNotAvailableError as error:
                # No product request URL exists for an unavailable product.
                # The event URL identifies the unchanged provider response in
                # which product discovery established the absence.
                logger.error(
                    "provider=%r url=%s status=%r dataset=%s "
                    "outcome=unavailable reason=%s",
                    self.get_agency(),
                    USGSComCatConnector._url_for_log(event_url),
                    None,
                    dataset,
                    error,
                )
                if first_non_http_failure is None:
                    first_non_http_failure = error
                continue
            except ValueError as error:
                logger.error(
                    "provider=%r url=%s status=%r dataset=%s "
                    "outcome=failed reason=%s",
                    self.get_agency(),
                    USGSComCatConnector._url_for_log(event_url),
                    None,
                    dataset,
                    error,
                )
                if first_non_http_failure is None:
                    first_non_http_failure = error
                continue

            try:
                # The selected provider URL is opaque. Supplying it directly
                # to transport preserves its bytes, ordering, and encoding.
                product_code, product_data = self.ws_client.query(
                    url=content_url,
                    response_purpose=dataset,
                )
            except (TimeoutError, ConnectionError, ssl.SSLError, ValueError) \
                    as error:
                logger.error(
                    "provider=%r url=%s status=%r dataset=%s "
                    "outcome=failed reason=%s",
                    self.get_agency(),
                    USGSComCatConnector._url_for_log(content_url),
                    None,
                    dataset,
                    error,
                )
                # Exception precedence follows logical request order, but the
                # independent later dataset is still attempted before raising.
                if first_non_http_failure is None:
                    first_non_http_failure = error
                continue

            if product_code is not None and 200 <= product_code < 300:
                self.datasets[dataset] = product_data
                continue

            # HTTP failures use the first real status in logical request order.
            # A later product success or HTTP failure cannot replace it.
            if first_http_failure is None:
                first_http_failure = product_code
            logger.error(
                "provider=%r url=%s status=%r dataset=%s outcome=failed",
                self.get_agency(),
                USGSComCatConnector._url_for_log(content_url),
                product_code,
                dataset,
            )

        if first_non_http_failure is not None:
            raise first_non_http_failure

        overall_code = (
            first_http_failure
            if first_http_failure is not None
            else 200
        )
        return overall_code, self.event_data, self.datasets
