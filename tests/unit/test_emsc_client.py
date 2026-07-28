# -*- coding: utf-8 -*-
from collections import deque
import io
import json
import os
import unittest
import urllib.parse
import zipfile

from paramws.clients import EMSCFeltReportClient
from paramws.clients.base_client import MissingRequiredOption
from paramws.clients.services import EMSCFeltReportConnector
from paramws.clients.services.feltreport_data import (
    FeltReportEventData,
    FeltReportIntensityData,
)
from tests.unit.request_double import ScriptedRequest


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_bytes(filename):
    """Return one deterministic EMSC fixture as bytes."""
    with open(os.path.join(FIXTURE_DIRECTORY, filename), "rb") as fixture:
        return fixture.read()


def intensity_zip_bytes(content=None):
    """Wrap representative intensity text in an in-memory ZIP response."""
    if content is None:
        content = fixture_bytes("emsc-intensities.txt")
    if isinstance(content, str):
        content = content.encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("event-one.txt", content)
    return buffer.getvalue()


class ControlledEMSCConnector:
    """Return prepared EMSC outcomes while recording per-query state."""

    def __init__(self, outcomes):
        self.outcomes = deque(outcomes)
        self.built_options = []
        self.requested_urls = []
        self.validated_options = []
        self.data = None
        self._validator = EMSCFeltReportConnector()

    def build_url(self, **options):
        self.built_options.append(dict(options))
        return "https://example.test/query?" + urllib.parse.urlencode(options)

    def query(self, url=None, **options):
        self.requested_urls.append(url)
        if not self.outcomes:
            raise AssertionError(
                "The client made more requests than the test configured."
            )
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        code, data = outcome
        if code is not None and 200 <= code < 300:
            self.data = data
        return code, data

    def validate_options(self, **options):
        cleaned_options = self._validator.validate_options(**options)
        self.validated_options.append(dict(cleaned_options))
        return cleaned_options

    def set_data(self, data):
        self.data = data

    def get_data(self):
        return self.data


def event_model(event_id="event-one"):
    """Return the established EMSC event model."""
    return FeltReportEventData({"ev_unid": event_id})


def intensity_model(event_id="event-one"):
    """Return the established multi-event EMSC intensity model."""
    return FeltReportIntensityData({
        event_id: {
            "unid": event_id,
            "intensities": [
                {"lon": 0.0, "lat": 0.0, "raw": 0.0, "corrected": 0.0},
            ],
            "comments": "#provider comments ",
        },
    })


class TestEMSCClient(unittest.TestCase):
    def test_default_contructor(self):
        client = EMSCFeltReportClient()

        self.assertEqual(client.get_agency(), "EMSC")
        self.assertEqual(client.get_version(), "1.1")
        self.assertEqual(client.get_end_point(), "api")
        self.assertEqual(
            client.get_base_url(),
            "https://www.seismicportal.eu/testimonies-ws/",
        )

    def test_set_url_attributes(self):
        client = EMSCFeltReportClient()
        client.set_agency("EMSC")
        client.set_version("1.1")
        client.set_end_point("api")
        client.set_base_url("https://www.seismicportal.eu/testimonies-ws")

        self.assertEqual(client.get_agency(), "EMSC")
        self.assertEqual(client.get_version(), "1.1")
        self.assertEqual(client.get_end_point(), "api")
        self.assertEqual(
            client.get_base_url(),
            "https://www.seismicportal.eu/testimonies-ws/",
        )

    def test_missing_event_resets_all_query_state(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([])
        client.ws_client = connector
        client.set_event_id("previous-event")
        client.set_event_data(event_model("previous-event"))
        client.set_feltreports(intensity_model("previous-event"))
        connector.data = object()
        client.felt_report_options["temporary"] = "old"
        client.event_data_options["temporary"] = "old"

        with self.assertRaisesRegex(MissingRequiredOption, "event_id"):
            client.query(event_id=None)

        self.assertIsNone(client.get_event_id())
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"felt_intensities": None})
        self.assertIsNone(client.get_feltreports())
        self.assertIsNone(connector.get_data())
        self.assertEqual(
            client.felt_report_options,
            {"includeTestimonies": "true"},
        )
        self.assertEqual(
            client.event_data_options,
            {"includeTestimonies": "false"},
        )

    def test_success_returns_exact_models_and_dataset_dictionary(self):
        expected_event = event_model()
        expected_intensities = intensity_model()
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, expected_intensities),
            (200, expected_event),
        ])
        client.ws_client = connector

        result = client.query(event_id="event-one")

        self.assertEqual(len(result), 3)
        code, event_data, datasets = result
        self.assertEqual(code, 200)
        self.assertIs(event_data, expected_event)
        self.assertIsInstance(event_data, FeltReportEventData)
        self.assertIs(type(datasets), dict)
        self.assertEqual(set(datasets), {"felt_intensities"})
        self.assertIs(datasets["felt_intensities"], expected_intensities)
        self.assertIsInstance(
            datasets["felt_intensities"],
            FeltReportIntensityData,
        )
        self.assertIsNot(event_data, datasets["felt_intensities"])

        event_view = client.get_feltreports()
        self.assertIsInstance(event_view, FeltReportIntensityData)
        self.assertEqual(event_view.get_event_id(), "event-one")
        self.assertEqual(event_view.get_intensities()[0]["raw"], 0.0)

    def test_felt_intensities_request_precedes_event_request(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, intensity_model()),
            (200, event_model()),
        ])
        client.ws_client = connector

        client.query(event_id="event-one")

        self.assertEqual(
            [options["includeTestimonies"]
             for options in connector.built_options],
            ["true", "false"],
        )
        self.assertEqual(
            [options["unids"] for options in connector.built_options],
            ["[event-one]", "[event-one]"],
        )
        self.assertEqual(len(connector.requested_urls), 2)

    def test_felt_http_failure_keeps_successful_event(self):
        expected_event = event_model()
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (404, None),
            (200, expected_event),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 404)
        self.assertIs(event_data, expected_event)
        self.assertIsNone(datasets["felt_intensities"])
        self.assertEqual(len(connector.requested_urls), 2)

    def test_event_http_failure_keeps_successful_intensities(self):
        expected_intensities = intensity_model()
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, expected_intensities),
            (410, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 410)
        self.assertIsNone(event_data)
        self.assertIs(datasets["felt_intensities"], expected_intensities)

    def test_two_http_failures_preserve_first_status(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (404, None),
            (422, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertIsNone(datasets["felt_intensities"])
        self.assertEqual(len(connector.requested_urls), 2)

    def test_felt_parse_failure_still_retrieves_event(self):
        expected_event = event_model()
        felt_error = ValueError("EMSC first felt-intensity failure")
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            felt_error,
            (200, expected_event),
        ])
        client.ws_client = connector

        with self.assertRaises(ValueError) as raised:
            client.query(event_id="event-one")

        self.assertIs(raised.exception, felt_error)
        self.assertEqual(len(connector.requested_urls), 2)
        self.assertIs(client.get_event_data(), expected_event)
        self.assertIsNone(client.get_datasets()["felt_intensities"])

    def test_event_parse_failure_retains_successful_intensities(self):
        expected_intensities = intensity_model()
        event_error = ValueError("EMSC event JSON failure")
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, expected_intensities),
            event_error,
        ])
        client.ws_client = connector

        with self.assertRaises(ValueError) as raised:
            client.query(event_id="event-one")

        self.assertIs(raised.exception, event_error)
        self.assertIsNone(client.get_event_data())
        self.assertIs(
            client.get_datasets()["felt_intensities"],
            expected_intensities,
        )

    def test_two_parse_failures_preserve_the_first(self):
        felt_error = ValueError("EMSC first felt-intensity failure")
        event_error = ValueError("EMSC later event failure")
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            felt_error,
            event_error,
        ])
        client.ws_client = connector

        with self.assertRaises(ValueError) as raised:
            client.query(event_id="event-one")

        self.assertIs(raised.exception, felt_error)
        self.assertEqual(len(connector.requested_urls), 2)

    def test_repeated_queries_isolate_results_options_and_connector_data(self):
        first_event = event_model("first-event")
        first_intensities = intensity_model("first-event")
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, first_intensities),
            (200, first_event),
            (404, None),
            (410, None),
        ])
        client.ws_client = connector

        with self.assertLogs("paramws", level="WARNING"):
            client.query(
                event_id="first-event",
                unsupported_for_one_call="ignored",
            )
        code, event_data, datasets = client.query(event_id="second-event")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {"felt_intensities": None})
        self.assertEqual(client.get_event_id(), "second-event")
        self.assertIsNone(client.get_feltreports())
        self.assertIsNone(connector.get_data())
        self.assertEqual(connector.validated_options, [{}, {}])
        self.assertEqual(
            [options["unids"] for options in connector.built_options],
            [
                "[first-event]",
                "[first-event]",
                "[second-event]",
                "[second-event]",
            ],
        )
        self.assertEqual(
            [options["includeTestimonies"]
             for options in connector.built_options],
            ["true", "false", "true", "false"],
        )
        for options in connector.built_options:
            self.assertNotIn("unsupported_for_one_call", options)

    def test_fixed_option_overrides_are_warned_about_and_ignored(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, intensity_model()),
            (200, event_model()),
        ])
        client.ws_client = connector

        with self.assertLogs("paramws", level="WARNING") as captured:
            client.query(
                event_id="authoritative-event",
                unids="ignored-event",
                includeTestimonies="caller-value",
            )

        self.assertEqual(len(captured.output), 2)
        warnings = "\n".join(captured.output)
        for context in (
                "unids",
                "ignored-event",
                "authoritative-event",
                "includeTestimonies",
                "caller-value",
                "true",
                "false"):
            self.assertIn(context, warnings)
        self.assertEqual(
            [options["unids"] for options in connector.built_options],
            ["[authoritative-event]", "[authoritative-event]"],
        )
        self.assertEqual(
            [options["includeTestimonies"]
             for options in connector.built_options],
            ["true", "false"],
        )

    def test_legacy_fixed_option_spellings_are_warned_about_and_ignored(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, intensity_model()),
            (200, event_model()),
        ])
        client.ws_client = connector
        aliases = (
            "includetestimonies",
            "IncludeTestimonies",
            "Includetestimonies",
        )

        with self.assertLogs("paramws", level="WARNING") as captured:
            client.query(
                event_id="event-one",
                **{alias: "caller-value" for alias in aliases}
            )

        self.assertEqual(len(captured.output), len(aliases))
        warnings = "\n".join(captured.output)
        for alias in aliases:
            self.assertIn(alias, warnings)
        self.assertEqual(
            [options["includeTestimonies"]
             for options in connector.built_options],
            ["true", "false"],
        )

    def test_unsupported_option_is_warned_about_and_removed(self):
        client = EMSCFeltReportClient()
        connector = ControlledEMSCConnector([
            (200, intensity_model()),
            (200, event_model()),
        ])
        client.ws_client = connector

        with self.assertLogs("paramws", level="WARNING") as captured:
            client.query(event_id="event-one", unexpected="caller-value")

        self.assertEqual(len(captured.output), 1)
        warning = captured.output[0]
        for context in ("EMSC", "api", "unexpected", "caller-value"):
            self.assertIn(context, warning)
        for options in connector.built_options:
            self.assertNotIn("unexpected", options)

    def test_invalid_felt_content_still_requests_and_retains_event(self):
        client = EMSCFeltReportClient()
        scripted_request = ScriptedRequest([
            (200, b"not-a-zip"),
            (200, fixture_bytes("emsc-event.json")),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "EMSC felt-intensity ZIP"):
            client.query(event_id="event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsInstance(client.get_event_data(), FeltReportEventData)
        self.assertIsNone(client.get_datasets()["felt_intensities"])

    def test_invalid_event_content_retains_parsed_intensities(self):
        client = EMSCFeltReportClient()
        scripted_request = ScriptedRequest([
            (200, intensity_zip_bytes()),
            (200, json.dumps({"unexpected": True}).encode("utf-8")),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "EMSC felt-report event JSON"):
            client.query(event_id="event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsNone(client.get_event_data())
        self.assertIsInstance(
            client.get_datasets()["felt_intensities"],
            FeltReportIntensityData,
        )


if __name__ == "__main__":
    unittest.main()
