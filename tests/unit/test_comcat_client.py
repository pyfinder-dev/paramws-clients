# -*- coding: utf-8 -*-
"""
Verify the public USGS ComCat client without network access or real delays.

These tests exercise the production connector with scripted transport so URL
selection, parser dispatch, retry behavior, request ordering, partial state,
and public model types are covered together at the client boundary.
"""

import json
import os
import socket
import ssl
import unittest
from urllib.parse import parse_qs, urlsplit

from paramws.clients import USGSComCatClient
from paramws.clients.base_client import BaseClient, MissingRequiredOption
from paramws.clients.services import InvalidOptionValue
from paramws.clients.services.feltreport_data import FeltReportIntensityData
from paramws.clients.services.shakemap_data import (
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
)
from paramws.clients.services.usgs import (
    DatasetNotAvailableError,
    USGSComCatConnector,
    USGSComCatParser,
)
from paramws.utils.customlogger import logger
from tests.unit.request_double import ScriptedRequest


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)
EVENT_URL_PREFIX = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?"
)
SHAKEMAP_URL = (
    "https://earthquake.usgs.gov/product/shakemap/"
    "ci38457511/atlas/1760000000000/download/stationlist.json"
)
DYFI_URL = (
    "https://earthquake.usgs.gov/product/dyfi/"
    "ci38457511/us/1760000001000/dyfi_geo_1km.geojson"
)


def fixture_bytes(filename):
    """Return one deterministic ComCat fixture as response bytes."""
    with open(os.path.join(FIXTURE_DIRECTORY, filename), "rb") as fixture:
        return fixture.read()


def fixture_json(filename):
    """Return one deterministic ComCat fixture as mutable JSON."""
    return json.loads(fixture_bytes(filename))


def json_bytes(value):
    """Encode a modified provider fixture for scripted transport."""
    return json.dumps(value).encode("utf-8")


def configured_client(outcomes):
    """Return a production client using deterministic transport outcomes."""
    client = USGSComCatClient()
    scripted = ScriptedRequest(outcomes)
    connector = client.get_web_service()
    connector._request_callable = scripted.request
    connector._delay_callable = scripted.delay
    return client, scripted


def success_outcomes():
    """Return successful event, ShakeMap, and DYFI transport outcomes."""
    return [
        (200, fixture_bytes("usgs-comcat-event-detail.json")),
        (200, fixture_bytes("usgs-shakemap-stationlist.json")),
        (200, fixture_bytes("usgs-dyfi-1km.geojson")),
    ]


class TestUSGSComCatClientSuccess(unittest.TestCase):
    """Verify selections, public results, ordering, and option ownership."""

    def test_defaults_and_direct_base_client_inheritance(self):
        client = USGSComCatClient()

        self.assertEqual(USGSComCatClient.__bases__, (BaseClient,))
        self.assertEqual(client.get_agency(), "USGS")
        self.assertEqual(client.get_base_url(), (
            "https://earthquake.usgs.gov/fdsnws/event/"
        ))
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "query")

    def test_shakemap_only_returns_exact_models_keys_and_order(self):
        client, scripted = configured_client(success_outcomes()[:2])

        result = client.query(
            event_id="ci38457511",
            producttype="shakemap",
        )

        self.assertEqual(len(result), 3)
        code, event_data, datasets = result
        self.assertEqual(code, 200)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertIs(type(datasets), dict)
        self.assertEqual(set(datasets), {"shakemap"})
        self.assertIsInstance(
            datasets["shakemap"],
            ShakeMapStationAmplitudes,
        )
        self.assertEqual(scripted.requested_urls, [
            EVENT_URL_PREFIX
            + "eventid=ci38457511&format=geojson&producttype=shakemap",
            SHAKEMAP_URL,
        ])
        self.assertNotIn(DYFI_URL, scripted.requested_urls)

    def test_dyfi_only_returns_exact_models_keys_and_order(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            success_outcomes()[2],
        ])

        code, event_data, datasets = client.query(
            event_id="ci38457511",
            producttype="dyfi",
        )

        self.assertEqual(code, 200)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertIs(type(datasets), dict)
        self.assertEqual(set(datasets), {"dyfi"})
        self.assertIsInstance(datasets["dyfi"], FeltReportIntensityData)
        self.assertEqual(scripted.requested_urls, [
            EVENT_URL_PREFIX
            + "eventid=ci38457511&format=geojson&producttype=dyfi",
            DYFI_URL,
        ])
        self.assertNotIn(SHAKEMAP_URL, scripted.requested_urls)

    def test_omitted_product_type_requests_only_both_supported_datasets(self):
        client, scripted = configured_client(success_outcomes())

        code, event_data, datasets = client.query(
            event_id="ci38457511",
        )

        self.assertEqual(code, 200)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertIs(type(datasets), dict)
        self.assertEqual(set(datasets), {"shakemap", "dyfi"})
        self.assertIsInstance(
            datasets["shakemap"],
            ShakeMapStationAmplitudes,
        )
        self.assertIsInstance(datasets["dyfi"], FeltReportIntensityData)
        self.assertEqual(scripted.requested_urls, [
            EVENT_URL_PREFIX + "eventid=ci38457511&format=geojson",
            SHAKEMAP_URL,
            DYFI_URL,
        ])
        for unsupported_content in (
                "stationlist.xml",
                "dyfi_geo_10km.geojson",
                "cdi_geo.xml"):
            self.assertNotIn(
                unsupported_content,
                "\n".join(scripted.requested_urls),
            )

    def test_fixed_overrides_warn_and_unsupported_option_is_removed(self):
        client, scripted = configured_client(success_outcomes())

        with self.assertLogs(logger, level="WARNING") as captured:
            client.query(
                event_id="ci38457511",
                eventid="wrong&format=xml",
                format="xml",
                unsupported="caller-value",
            )

        warnings = "\n".join(captured.output)
        for context in (
                "eventid",
                "wrong&format=xml",
                "ci38457511",
                "format",
                "xml",
                "geojson",
                "USGS",
                "query",
                "unsupported",
                "caller-value"):
            self.assertIn(context, warnings)
        event_options = parse_qs(
            urlsplit(scripted.requested_urls[0]).query)
        self.assertEqual(event_options, {
            "eventid": ["ci38457511"],
            "format": ["geojson"],
        })

    def test_invalid_product_type_fails_before_transport(self):
        client, scripted = configured_client([])

        for producttype in ("origin", ["shakemap"]):
            with self.subTest(producttype=producttype):
                with self.assertRaises(InvalidOptionValue):
                    client.query(
                        event_id="ci38457511",
                        producttype=producttype,
                    )

        self.assertEqual(scripted.requested_urls, [])

    def test_public_imports_preserve_service_package_paths(self):
        from paramws.clients import USGSComCatClient as PublicClient
        from paramws.clients.services import (
            USGSComCatConnector as ServicesConnector,
        )
        from paramws.clients.services.usgs import (
            DatasetNotAvailableError as PublicAbsence,
            USGSComCatConnector as PublicConnector,
            USGSComCatParser as PublicParser,
        )

        self.assertIs(PublicClient, USGSComCatClient)
        self.assertIs(ServicesConnector, USGSComCatConnector)
        self.assertIs(PublicConnector, USGSComCatConnector)
        self.assertIs(PublicParser, USGSComCatParser)
        self.assertIs(PublicAbsence, DatasetNotAvailableError)


class TestUSGSComCatClientLifecycle(unittest.TestCase):
    """Verify that configuration and all event-scoped state remain current."""

    def test_missing_event_identifier_resets_all_query_state(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            success_outcomes()[2],
        ])
        client.query(event_id="ci38457511", producttype="dyfi")
        self.assertIsNotNone(client.get_web_service().get_data())

        with self.assertRaisesRegex(
                MissingRequiredOption, "event_id"):
            client.query(event_id=None, producttype="shakemap")

        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"shakemap": None})
        self.assertIsNone(client.event_options["eventid"])
        self.assertEqual(client.event_options["format"], "geojson")
        self.assertNotIn("producttype", client.event_options)
        self.assertIsNone(client.get_web_service().get_data())
        self.assertEqual(len(scripted.requested_urls), 2)

    def test_repeated_queries_do_not_leak_results_keys_ids_or_options(self):
        second_event = fixture_json("usgs-comcat-event-detail.json")
        second_event["id"] = "second-event"
        client, scripted = configured_client([
            success_outcomes()[0],
            success_outcomes()[2],
            (200, json_bytes(second_event)),
            (404, b"missing"),
            (410, b"gone"),
        ])

        first_result = client.query(
            event_id="ci38457511",
            producttype="dyfi",
        )
        second_result = client.query(event_id="second-event")

        self.assertIsInstance(
            first_result[2]["dyfi"],
            FeltReportIntensityData,
        )
        code, event_data, datasets = second_result
        self.assertEqual(code, 404)
        self.assertEqual(event_data.get_event_id(), "second-event")
        self.assertEqual(datasets, {
            "shakemap": None,
            "dyfi": None,
        })
        self.assertEqual(client.event_options, {
            "eventid": "second-event",
            "format": "geojson",
        })
        self.assertNotIn(
            "producttype",
            parse_qs(urlsplit(scripted.requested_urls[2]).query),
        )
        self.assertIs(
            client.get_web_service().get_data(),
            event_data,
        )

    def test_configuration_setters_survive_connector_recreation(self):
        client = USGSComCatClient()
        client.set_agency("USGS-TEST")
        client.set_base_url("https://catalog.example.test/fdsn/event")
        client.set_version("9")
        client.set_end_point("detail")

        connector = client.create_web_service()

        self.assertEqual(client.get_agency(), "USGS-TEST")
        self.assertEqual(
            client.get_base_url(),
            "https://catalog.example.test/fdsn/event/",
        )
        self.assertEqual(client.get_version(), "9")
        self.assertEqual(client.get_end_point(), "detail")
        self.assertEqual(connector.get_agency(), "USGS-TEST")
        self.assertEqual(
            connector.get_base_url(),
            "https://catalog.example.test/fdsn/event/",
        )
        self.assertEqual(connector.get_version(), "9")
        self.assertEqual(connector.get_end_point(), "detail")
        self.assertEqual(
            connector.build_url(eventid="one", format="geojson"),
            "https://catalog.example.test/fdsn/event/9/detail?"
            "eventid=one&format=geojson",
        )


class TestUSGSComCatClientFailures(unittest.TestCase):
    """Verify prerequisite, independence, absence, and failure precedence."""

    def test_event_http_failure_prevents_all_product_requests(self):
        client, scripted = configured_client([(404, b"not found")])

        code, event_data, datasets = client.query(
            event_id="missing-event",
        )

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {
            "shakemap": None,
            "dyfi": None,
        })
        self.assertEqual(len(scripted.requested_urls), 1)

    def test_invalid_event_http_200_content_prevents_product_requests(self):
        client, scripted = configured_client([
            (200, b'{"type": "FeatureCollection", "features": []}'),
        ])

        with self.assertRaisesRegex(
                ValueError, "USGS/ComCat.*single-event"):
            client.query(event_id="ci38457511")

        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {
            "shakemap": None,
            "dyfi": None,
        })

    def test_product_http_failures_keep_first_status_and_attempt_later(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            (404, b"missing"),
            (410, b"gone"),
        ])

        code, event_data, datasets = client.query(
            event_id="ci38457511",
        )

        self.assertEqual(code, 404)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertEqual(datasets, {
            "shakemap": None,
            "dyfi": None,
        })
        self.assertEqual(scripted.requested_urls[1:], [
            SHAKEMAP_URL,
            DYFI_URL,
        ])

    def test_product_parse_failure_retains_later_independent_data(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            (200, b'{"type": "FeatureCollection", "features": [null]}'),
            success_outcomes()[2],
        ])

        with self.assertRaisesRegex(
                ValueError, "USGS/ComCat.*stationlist.json"):
            client.query(event_id="ci38457511")

        self.assertEqual(scripted.requested_urls[1:], [
            SHAKEMAP_URL,
            DYFI_URL,
        ])
        self.assertIsInstance(client.get_event_data(), ShakeMapEventData)
        self.assertIsNone(client.get_datasets()["shakemap"])
        self.assertIsInstance(
            client.get_datasets()["dyfi"],
            FeltReportIntensityData,
        )

    def test_missing_shakemap_still_retrieves_dyfi_before_raising(self):
        event = fixture_json("usgs-comcat-event-detail.json")
        del event["properties"]["products"]["shakemap"]
        client, scripted = configured_client([
            (200, json_bytes(event)),
            success_outcomes()[2],
        ])

        with self.assertRaisesRegex(
                DatasetNotAvailableError, "shakemap"):
            client.query(event_id="ci38457511")

        self.assertEqual(len(scripted.requested_urls), 2)
        self.assertEqual(scripted.requested_urls[-1], DYFI_URL)
        self.assertIsNone(client.get_datasets()["shakemap"])
        self.assertIsInstance(
            client.get_datasets()["dyfi"],
            FeltReportIntensityData,
        )

    def test_deleted_dyfi_does_not_block_successful_shakemap(self):
        event = fixture_json("usgs-comcat-event-detail.json")
        event["properties"]["products"]["dyfi"][0]["status"] = "DELETE"
        client, scripted = configured_client([
            (200, json_bytes(event)),
            success_outcomes()[1],
        ])

        with self.assertRaisesRegex(
                DatasetNotAvailableError, "dyfi.*deleted"):
            client.query(event_id="ci38457511")

        self.assertEqual(scripted.requested_urls, [
            EVENT_URL_PREFIX + "eventid=ci38457511&format=geojson",
            SHAKEMAP_URL,
        ])
        self.assertIsInstance(
            client.get_datasets()["shakemap"],
            ShakeMapStationAmplitudes,
        )
        self.assertIsNone(client.get_datasets()["dyfi"])

    def test_both_absent_raise_shakemap_first_without_content_requests(self):
        event = fixture_json("usgs-comcat-event-detail.json")
        event["properties"]["products"] = {}
        client, scripted = configured_client([
            (200, json_bytes(event)),
        ])

        with self.assertRaisesRegex(
                DatasetNotAvailableError, "shakemap"):
            client.query(event_id="ci38457511")

        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(client.get_datasets(), {
            "shakemap": None,
            "dyfi": None,
        })

    def test_missing_exact_content_never_falls_back_to_alternates(self):
        event = fixture_json("usgs-comcat-event-detail.json")
        preferred = event["properties"]["products"]["shakemap"][2]
        preferred["contents"] = {
            "download/stationlist.xml": {
                "url": "https://fallback.example.test/stationlist.xml",
            },
            "download/stationlist.txt": {
                "url": "https://fallback.example.test/stationlist.txt",
            },
        }
        # Older and non-preferred contributors still retain valid JSON content;
        # selecting either would incorrectly hide the preferred-product gap.
        client, scripted = configured_client([
            (200, json_bytes(event)),
            success_outcomes()[2],
        ])

        with self.assertRaisesRegex(
                DatasetNotAvailableError,
                "shakemap.*download/stationlist.json"):
            client.query(event_id="ci38457511")

        self.assertEqual(scripted.requested_urls[1:], [DYFI_URL])
        requested = "\n".join(scripted.requested_urls)
        for forbidden in (
                "stationlist.xml",
                "stationlist.txt",
                "/us/1750000000000/",
                "/ci/1740000000000/"):
            self.assertNotIn(forbidden, requested)

    def test_missing_dyfi_1km_never_uses_10km_xml_or_text(self):
        event = fixture_json("usgs-comcat-event-detail.json")
        dyfi_contents = (
            event["properties"]["products"]["dyfi"][0]["contents"]
        )
        del dyfi_contents["dyfi_geo_1km.geojson"]
        dyfi_contents["dyfi_geo_1km.txt"] = {
            "url": "https://fallback.example.test/dyfi_geo_1km.txt",
        }
        client, scripted = configured_client([
            (200, json_bytes(event)),
            success_outcomes()[1],
        ])

        with self.assertRaisesRegex(
                DatasetNotAvailableError,
                "dyfi.*dyfi_geo_1km.geojson"):
            client.query(event_id="ci38457511")

        self.assertEqual(scripted.requested_urls[1:], [SHAKEMAP_URL])
        requested = "\n".join(scripted.requested_urls)
        for forbidden in (
                "dyfi_geo_10km.geojson",
                "cdi_geo.xml",
                "dyfi_geo_1km.txt"):
            self.assertNotIn(forbidden, requested)


class TestUSGSComCatTransportIntegration(unittest.TestCase):
    """Prove the client uses the shared retry and resolved-URL transport."""

    def test_event_timeout_exhaustion_prevents_product_requests(self):
        client, scripted = configured_client([
            TimeoutError("first timeout"),
            TimeoutError("second timeout"),
            TimeoutError("third timeout"),
        ])

        with self.assertRaises(TimeoutError):
            client.query(event_id="ci38457511")

        event_url = EVENT_URL_PREFIX + "eventid=ci38457511&format=geojson"
        self.assertEqual(scripted.requested_urls, [
            event_url,
            event_url,
            event_url,
        ])
        self.assertEqual(scripted.recorded_timeouts, [10, 10, 10])
        self.assertEqual(scripted.recorded_delays, [2, 2])
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {
            "shakemap": None,
            "dyfi": None,
        })

    def test_product_timeout_exhaustion_continues_then_raises(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            TimeoutError("first timeout"),
            TimeoutError("second timeout"),
            TimeoutError("third timeout"),
            success_outcomes()[2],
        ])

        with self.assertRaises(TimeoutError):
            client.query(event_id="ci38457511")

        self.assertEqual(scripted.requested_urls, [
            EVENT_URL_PREFIX + "eventid=ci38457511&format=geojson",
            SHAKEMAP_URL,
            SHAKEMAP_URL,
            SHAKEMAP_URL,
            DYFI_URL,
        ])
        self.assertEqual(scripted.recorded_timeouts, [10, 10, 10, 10, 10])
        self.assertEqual(scripted.recorded_delays, [2, 2])
        self.assertIsInstance(
            client.get_datasets()["dyfi"],
            FeltReportIntensityData,
        )

    def test_product_connection_exhaustion_keeps_standard_exception_policy(
            self):
        failures = [
            socket.gaierror(-2, "first"),
            socket.gaierror(-2, "second"),
            socket.gaierror(-2, "third"),
        ]
        client, scripted = configured_client([
            success_outcomes()[0],
            *failures,
        ])

        with self.assertRaises(ConnectionError) as raised:
            client.query(
                event_id="ci38457511",
                producttype="shakemap",
            )

        self.assertIs(raised.exception.__cause__, failures[-1])
        self.assertEqual(scripted.requested_urls[1:], [
            SHAKEMAP_URL,
            SHAKEMAP_URL,
            SHAKEMAP_URL,
        ])
        self.assertEqual(scripted.recorded_delays, [2, 2])

    def test_tls_failure_is_not_retried_and_later_product_is_retained(self):
        tls_error = ssl.SSLError("certificate failure")
        client, scripted = configured_client([
            success_outcomes()[0],
            tls_error,
            success_outcomes()[2],
        ])

        with self.assertRaises(ssl.SSLError) as raised:
            client.query(event_id="ci38457511")

        self.assertIs(raised.exception, tls_error)
        self.assertEqual(scripted.requested_urls[1:], [
            SHAKEMAP_URL,
            DYFI_URL,
        ])
        self.assertEqual(scripted.recorded_delays, [])
        self.assertIsInstance(
            client.get_datasets()["dyfi"],
            FeltReportIntensityData,
        )

    def test_invalid_product_http_200_content_is_not_retried(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            (200, b"not json"),
        ])

        with self.assertRaisesRegex(
                ValueError, "USGS/ComCat.*stationlist.json"):
            client.query(
                event_id="ci38457511",
                producttype="shakemap",
            )

        self.assertEqual(scripted.requested_urls[1:], [SHAKEMAP_URL])
        self.assertEqual(scripted.recorded_delays, [])

    def test_exhausted_retryable_product_status_is_overall_status(self):
        client, scripted = configured_client([
            success_outcomes()[0],
            (503, b"first"),
            (503, b"second"),
            (503, b"third"),
            success_outcomes()[2],
        ])

        code, _event_data, datasets = client.query(
            event_id="ci38457511",
        )

        self.assertEqual(code, 503)
        self.assertIsNone(datasets["shakemap"])
        self.assertIsInstance(datasets["dyfi"], FeltReportIntensityData)
        self.assertEqual(scripted.requested_urls[1:], [
            SHAKEMAP_URL,
            SHAKEMAP_URL,
            SHAKEMAP_URL,
            DYFI_URL,
        ])
        self.assertEqual(scripted.recorded_delays, [2, 2])


if __name__ == "__main__":
    unittest.main()
