# -*- coding: utf-8 -*-
"""
Connect the USGS FDSN event endpoint to the contracted ComCat parsers.

The event request uses native FDSN options, while ShakeMap and DYFI content
URLs are discovered later in the parsed event metadata. Those discovered URLs
remain opaque transport input. A response purpose supplied by the client
selects one of the three known parsers explicitly, which is necessary because
an empty FeatureCollection cannot identify its scientific dataset.
"""

import urllib

from paramws.clients.services.baseconnector import BaseWebServiceConnector
from paramws.clients.services.usgs.comcat_parser import USGSComCatParser


class USGSComCatConnector(BaseWebServiceConnector):
    """
    Represent the USGS ComCat detailed-event query and product downloads.

    URL construction is limited to the FDSN event endpoint. Product downloads
    reuse the base connector's resolved-URL transport without rebuilding or
    validating provider-discovered content URLs.
    """

    _RESPONSE_PURPOSES = ("event_detail", "shakemap", "dyfi")

    def __init__(
            self,
            agency="USGS",
            base_url="https://earthquake.usgs.gov/fdsnws/event/",
            end_point="query",
            version="1"):
        self._response_purpose = None
        super().__init__(agency, base_url, end_point, version)

    def get_supported_options(self):
        """Return the native FDSN options used by this ComCat client."""
        return ["eventid", "format", "producttype"]

    def is_value_valid(self, option, value):
        """
        Validate fixed GeoJSON format and the two supported product types.

        ``producttype`` is a native scalar parameter. Requiring an exact string
        rejects sequences as well as ComCat product types whose discovery,
        content representation, and parsing are outside this client.
        """
        if option == "format":
            return value == "geojson"
        if option == "producttype":
            return (
                isinstance(value, str)
                and value in ("shakemap", "dyfi")
            )
        return True

    def build_url(self, **options):
        """Build a URL-encoded detailed-event request for the FDSN endpoint."""
        options = self.validate_options(**options)

        if self.base_url and not self.base_url.endswith("/"):
            self.base_url += "/"

        # Event identifiers are native parameter values. Encoding prevents an
        # embedded delimiter from becoming unintended query syntax.
        encoded_options = urllib.parse.urlencode(
            options,
            encoding="utf-8",
        )
        self.combined_url = (
            f"{self.base_url}{self.version}/{self.end_point}?"
            f"{encoded_options}"
        )
        return self.combined_url

    def query(
            self,
            url=None,
            user=None,
            password=None,
            response_purpose=None,
            **options):
        """
        Query through shared transport with an explicit response purpose.

        A native FDSN query has a known event-detail purpose. Any already
        resolved URL, including a product URL, requires the caller to name the
        expected response so parsing never depends on payload sniffing.
        """
        if response_purpose is None and url is None:
            response_purpose = "event_detail"
        if response_purpose not in self._RESPONSE_PURPOSES:
            raise ValueError(
                "USGS/ComCat response purpose must be one of {}."
                .format(", ".join(self._RESPONSE_PURPOSES))
            )

        self._response_purpose = response_purpose
        try:
            return super().query(
                url=url,
                user=user,
                password=password,
                **options
            )
        finally:
            self._response_purpose = None

    def parse_response(self, file_like_obj=None, options=None):
        """
        Parse only the three contracted ComCat response purposes.

        Purpose comes from the request operation rather than response fields.
        ShakeMap and DYFI both use FeatureCollection, and their empty
        collections are indistinguishable, so provider-specific explicit
        dispatch is the only deterministic choice.
        """
        parser = USGSComCatParser()
        if self._response_purpose == "event_detail":
            data = parser.parse_event_detail(file_like_obj)
        elif self._response_purpose == "shakemap":
            data = parser.parse_shakemap_station_list(file_like_obj)
        elif self._response_purpose == "dyfi":
            data = parser.parse_dyfi_1km(file_like_obj)
        else:
            raise ValueError(
                "USGS/ComCat response parsing requires a known request "
                "purpose."
            )

        self.set_data(data)
        return self.get_data()
