# -*- coding: utf-8 -*-
"""Deterministic tests for the provider-specific USGS ComCat connector."""

import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from paramws.clients.services import (
    BaseWebServiceConnector,
    InvalidOptionValue,
    USGSComCatConnector,
)
from paramws.clients.services.feltreport_data import FeltReportIntensityData
from paramws.clients.services.shakemap_data import (
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
)
from paramws.utils.customlogger import logger
from tests.unit.request_double import ScriptedRequest


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_bytes(filename):
    """Return one deterministic ComCat fixture as response bytes."""
    with open(os.path.join(FIXTURE_DIRECTORY, filename), "rb") as fixture:
        return fixture.read()


class TestUSGSComCatConnector(unittest.TestCase):
    """Verify URL, option, dispatch, and resolved-URL connector behavior."""

    def test_defaults_and_direct_base_connector_inheritance(self):
        connector = USGSComCatConnector()

        self.assertEqual(
            USGSComCatConnector.__bases__,
            (BaseWebServiceConnector,),
        )
        self.assertEqual(connector.get_agency(), "USGS")
        self.assertEqual(connector.get_base_url(), (
            "https://earthquake.usgs.gov/fdsnws/event/"
        ))
        self.assertEqual(connector.get_version(), "1")
        self.assertEqual(connector.get_end_point(), "query")
        self.assertEqual(
            connector.get_combined_url(),
            "https://earthquake.usgs.gov/fdsnws/event/1/query?",
        )

    def test_exact_event_detail_url_and_identifier_encoding(self):
        connector = USGSComCatConnector()
        event_id = "ci38457511&format=xml=extra"

        url = connector.build_url(
            eventid=event_id,
            format="geojson",
            producttype="shakemap",
        )

        self.assertEqual(
            url,
            "https://earthquake.usgs.gov/fdsnws/event/1/query?"
            "eventid=ci38457511%26format%3Dxml%3Dextra&format=geojson"
            "&producttype=shakemap",
        )
        self.assertEqual(parse_qs(urlsplit(url).query), {
            "eventid": [event_id],
            "format": ["geojson"],
            "producttype": ["shakemap"],
        })

    def test_supported_native_options_and_valid_product_types(self):
        connector = USGSComCatConnector()

        self.assertEqual(
            connector.get_supported_options(),
            ["eventid", "format", "producttype"],
        )
        with patch.object(logger, "warning") as warning:
            for producttype in ("shakemap", "dyfi"):
                url = connector.build_url(
                    eventid="event-one",
                    format="geojson",
                    producttype=producttype,
                )
                self.assertIn("producttype=" + producttype, url)

        warning.assert_not_called()

    def test_invalid_and_sequence_product_types_are_rejected(self):
        connector = USGSComCatConnector()

        for value in (
                "origin",
                "ShakeMap",
                "",
                ["shakemap"],
                ("dyfi",),
                {"shakemap"},
                None):
            with self.subTest(value=value):
                with self.assertRaises(InvalidOptionValue):
                    connector.build_url(
                        eventid="event-one",
                        format="geojson",
                        producttype=value,
                    )

    def test_format_accepts_only_geojson(self):
        connector = USGSComCatConnector()

        with self.assertRaises(InvalidOptionValue):
            connector.build_url(
                eventid="event-one",
                format="xml",
            )

    def test_unsupported_option_warns_and_is_omitted(self):
        connector = USGSComCatConnector()

        with self.assertLogs(logger, level="WARNING") as captured:
            url = connector.build_url(
                eventid="event-one",
                format="geojson",
                catalog="preferred",
            )

        self.assertNotIn("catalog", parse_qs(urlsplit(url).query))
        warning = captured.output[0]
        for context in ("USGS", "query", "catalog", "preferred"):
            self.assertIn(context, warning)

    def test_explicit_response_purpose_selects_each_parser(self):
        cases = (
            (
                "event_detail",
                "usgs-comcat-event-detail.json",
                ShakeMapEventData,
            ),
            (
                "shakemap",
                "usgs-shakemap-stationlist.json",
                ShakeMapStationAmplitudes,
            ),
            (
                "dyfi",
                "usgs-dyfi-1km.geojson",
                FeltReportIntensityData,
            ),
        )

        for purpose, filename, expected_type in cases:
            with self.subTest(purpose=purpose):
                connector = USGSComCatConnector()
                scripted = ScriptedRequest([
                    (200, fixture_bytes(filename)),
                ])
                connector._request_callable = scripted.request
                connector._delay_callable = scripted.delay

                code, data = connector.query(
                    url="https://content.example.test/data",
                    response_purpose=purpose,
                )

                self.assertEqual(code, 200)
                self.assertIsInstance(data, expected_type)

    def test_empty_collections_still_use_known_scientific_purpose(self):
        content = b'{"type": "FeatureCollection", "features": []}'

        for purpose, expected_type in (
                ("shakemap", ShakeMapStationAmplitudes),
                ("dyfi", FeltReportIntensityData)):
            with self.subTest(purpose=purpose):
                connector = USGSComCatConnector()
                scripted = ScriptedRequest([(200, content)])
                connector._request_callable = scripted.request
                connector._delay_callable = scripted.delay

                _code, data = connector.query(
                    url="https://content.example.test/empty",
                    response_purpose=purpose,
                )

                self.assertIsInstance(data, expected_type)

    def test_resolved_content_url_is_requested_byte_for_byte_unchanged(self):
        connector = USGSComCatConnector()
        scripted = ScriptedRequest([
            (200, fixture_bytes("usgs-dyfi-1km.geojson")),
        ])
        connector._request_callable = scripted.request
        connector._delay_callable = scripted.delay
        resolved_url = (
            "https://content.example.test/product/data%2Fone?"
            "token=a%2Bb&order=second%20value&order=first"
        )

        connector.query(
            url=resolved_url,
            response_purpose="dyfi",
        )

        self.assertEqual(scripted.requested_urls, [resolved_url])
        self.assertEqual(scripted.recorded_timeouts, [10])

    def test_resolved_url_requires_an_explicit_known_purpose(self):
        connector = USGSComCatConnector()
        scripted = ScriptedRequest([])
        connector._request_callable = scripted.request

        for purpose in (None, "unknown"):
            with self.subTest(purpose=purpose):
                with self.assertRaisesRegex(ValueError, "response purpose"):
                    connector.query(
                        url="https://content.example.test/data",
                        response_purpose=purpose,
                    )

        self.assertEqual(scripted.requested_urls, [])


if __name__ == "__main__":
    unittest.main()
