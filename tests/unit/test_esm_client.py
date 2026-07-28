# -*- coding: utf-8 -*-
from collections import deque
import unittest
import urllib.parse

from paramws.clients import ESMShakeMapClient
from paramws.clients.base_client import MissingRequiredOption
from paramws.clients.services import ESMShakeMapConnector
from paramws.clients.services.baseconnector import InvalidOptionValue
from paramws.clients.services.shakemap_data import ShakeMapEventData
from paramws.clients.services.shakemap_data import ShakeMapStationAmplitudes
from tests.unit.request_double import ScriptedRequest


EVENT_XML = (
    '<earthquake id="event-one" catalog="EMSC" lat="41.0" lon="20.0" '
    'depth="8.0" mag="4.2" year="2026" month="07" day="27" hour="12" '
    'minute="30" second="15.5" time="2026-07-27T12:30:15.5Z" '
    'timezone="GMT" netid="ESM" network="ESM database" locstring="" '
    'created="1785155415"/>'
)

STATION_XML = (
    '<stationlist created="1685534294">'
    '<station code="ONE" netid="NW">'
    '<comp name="HNZ" depth="0">'
    '<acc value="0.25" flag="0"/>'
    '</comp>'
    '</station>'
    '</stationlist>'
)


class ControlledESMConnector:
    """Return prepared ESM models while recording logical request options."""

    def __init__(self, outcomes):
        self.outcomes = deque(outcomes)
        self.built_options = []
        self.requested_urls = []
        self.data = None
        self._validator = ESMShakeMapConnector()

    def build_url(self, **options):
        self.built_options.append(dict(options))
        return "https://example.test/query?" + urllib.parse.urlencode(options)

    def query(self, url=None, **options):
        self.requested_urls.append(url)
        if not self.outcomes:
            raise AssertionError(
                "The client made more requests than the test configured."
            )
        return self.outcomes.popleft()

    def validate_options(self, **options):
        """Use the production ESM connector's option contract."""
        return self._validator.validate_options(**options)

    def set_data(self, data):
        self.data = data


def event_model(event_id="event-one"):
    """Return the actual event model used by the public ESM interface."""
    return ShakeMapEventData({"id": event_id})


def amplitude_model():
    """Return the actual station-amplitude model used by the ESM interface."""
    return ShakeMapStationAmplitudes({"created": None, "stations": []})


class TestESMClient(unittest.TestCase):
    def test_default_contructor(self):
        # Test the constructor with default values.
        client = ESMShakeMapClient()

        self.assertEqual(client.get_agency(), "ESM")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), "https://esm-db.eu/esmws/")

    def test_set_url_attributes(self):
        # Test the parts of the query url.
        client = ESMShakeMapClient()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        self.assertEqual(client.get_agency(), "ESM")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), "https://esm-db.eu/esmws/")

    def test_query_null_event_id(self):
        client = ESMShakeMapClient()
        client.set_event_id("previous-event")
        client.set_event_data(event_model("previous-event"))
        client.set_station_amplitudes(amplitude_model())
        client.get_web_service().set_data("previous response")

        with self.assertRaisesRegex(MissingRequiredOption, "event_id"):
            client.query(event_id=None)

        self.assertIsNone(client.get_event_id())
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"station_amplitudes": None})
        self.assertIsNone(client.get_web_service().get_data())

    def test_success_returns_exact_models_and_dataset_dictionary(self):
        expected_event = event_model()
        expected_amplitudes = amplitude_model()
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (200, expected_event),
            (200, expected_amplitudes),
        ])
        client.ws_client = connector

        result = client.query(event_id="event-one")

        self.assertEqual(len(result), 3)
        code, event_data, datasets = result
        self.assertEqual(code, 200)
        self.assertIs(event_data, expected_event)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertIs(type(datasets), dict)
        self.assertEqual(set(datasets), {"station_amplitudes"})
        self.assertIs(datasets["station_amplitudes"], expected_amplitudes)
        self.assertIsInstance(
            datasets["station_amplitudes"],
            ShakeMapStationAmplitudes,
        )
        self.assertIsNot(event_data, datasets["station_amplitudes"])

    def test_event_request_precedes_station_amplitudes(self):
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        client.query(event_id="event-one")

        self.assertEqual(
            [options["format"] for options in connector.built_options],
            ["event", "event_dat"],
        )
        self.assertEqual(connector.requested_urls, [
            "https://example.test/query?"
            "eventid=event-one&catalog=EMSC&format=event&flag=0&encoding=UTF-8",
            "https://example.test/query?"
            "eventid=event-one&catalog=EMSC&format=event_dat&flag=0"
            "&encoding=UTF-8",
        ])

    def test_event_http_failure_keeps_successful_station_amplitudes(self):
        expected_amplitudes = amplitude_model()
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (404, None),
            (200, expected_amplitudes),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertIs(datasets["station_amplitudes"], expected_amplitudes)
        self.assertEqual(len(connector.requested_urls), 2)

    def test_station_http_failure_keeps_successful_event(self):
        expected_event = event_model()
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (200, expected_event),
            (410, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 410)
        self.assertIs(event_data, expected_event)
        self.assertIsNone(datasets["station_amplitudes"])

    def test_two_http_failures_preserve_first_status(self):
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (404, None),
            (422, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(event_id="event-one")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertIsNone(datasets["station_amplitudes"])
        self.assertEqual(
            [options["format"] for options in connector.built_options],
            ["event", "event_dat"],
        )

    def test_repeated_queries_clear_results_and_keyword_options(self):
        first_event = event_model("first-event")
        first_amplitudes = amplitude_model()
        client = ESMShakeMapClient()
        client.set_catalog("ISC")
        client.include_problematic_data(True)
        connector = ControlledESMConnector([
            (200, first_event),
            (200, first_amplitudes),
            (404, None),
            (410, None),
        ])
        client.ws_client = connector

        client.query(
            event_id="first-event",
            catalog="USGS",
            flag="0",
            encoding="US-ASCII",
        )
        code, event_data, datasets = client.query(event_id="second-event")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {"station_amplitudes": None})
        self.assertIsNone(client.get_event_data())
        self.assertIsNone(client.get_station_amplitudes())
        self.assertEqual(client.get_event_id(), "second-event")

        second_query_options = connector.built_options[2:]
        self.assertEqual(
            [options["eventid"] for options in second_query_options],
            ["second-event", "second-event"],
        )
        self.assertEqual(
            [options["catalog"] for options in second_query_options],
            ["ISC", "ISC"],
        )
        self.assertEqual(
            [options["flag"] for options in second_query_options],
            ["all", "all"],
        )
        self.assertEqual(
            [options["encoding"] for options in second_query_options],
            ["UTF-8", "UTF-8"],
        )

        first_query_options = connector.built_options[:2]
        self.assertEqual(
            [options["catalog"] for options in first_query_options],
            ["USGS", "USGS"],
        )
        self.assertEqual(
            [options["flag"] for options in first_query_options],
            ["0", "0"],
        )
        self.assertEqual(
            [options["encoding"] for options in first_query_options],
            ["US-ASCII", "US-ASCII"],
        )

    def test_invalid_options_raise_before_transport(self):
        invalid_options = (
            ("catalog", "UNKNOWN"),
            ("flag", "1"),
            ("encoding", "UTF-16"),
        )
        for option, value in invalid_options:
            with self.subTest(option=option, value=value):
                client = ESMShakeMapClient()
                scripted_request = ScriptedRequest([])
                client.get_web_service()._request_callable = \
                    scripted_request.request
                client.get_web_service()._delay_callable = \
                    scripted_request.delay

                with self.assertRaises(InvalidOptionValue):
                    client.query(
                        event_id="event-one",
                        **{option: value}
                    )

                self.assertEqual(scripted_request.requested_urls, [])

    def test_unsupported_option_is_warned_about_and_removed(self):
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        with self.assertLogs("paramws", level="WARNING") as captured:
            client.query(event_id="event-one", unexpected="caller-value")

        self.assertEqual(len(captured.output), 1)
        warning = captured.output[0]
        self.assertIn("ESM", warning)
        self.assertIn("shakemap", warning)
        self.assertIn("unexpected", warning)
        self.assertIn("caller-value", warning)
        for options in connector.built_options:
            self.assertNotIn("unexpected", options)

    def test_fixed_native_option_overrides_are_warned_about_and_ignored(self):
        client = ESMShakeMapClient()
        connector = ControlledESMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        with self.assertLogs("paramws", level="WARNING") as captured:
            client.query(
                event_id="authoritative-event",
                eventid="ignored-event",
                format="event_fault",
            )

        self.assertEqual(len(captured.output), 2)
        warnings = "\n".join(captured.output)
        self.assertIn("eventid", warnings)
        self.assertIn("ignored-event", warnings)
        self.assertIn("authoritative-event", warnings)
        self.assertIn("format", warnings)
        self.assertIn("event_fault", warnings)
        self.assertIn("event_dat", warnings)
        self.assertEqual(
            [options["eventid"] for options in connector.built_options],
            ["authoritative-event", "authoritative-event"],
        )
        self.assertEqual(
            [options["format"] for options in connector.built_options],
            ["event", "event_dat"],
        )

    def test_invalid_successful_event_still_retrieves_station_amplitudes(self):
        client = ESMShakeMapClient()
        scripted_request = ScriptedRequest([
            (200, "<not-an-earthquake/>"),
            (200, STATION_XML),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "ESM.*ShakeMap event XML"):
            client.query(event_id="event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsNone(client.get_event_data())
        self.assertIsInstance(
            client.get_datasets()["station_amplitudes"],
            ShakeMapStationAmplitudes,
        )

    def test_invalid_successful_station_content_raises_value_error(self):
        client = ESMShakeMapClient()
        scripted_request = ScriptedRequest([
            (200, EVENT_XML),
            (200, "<not-a-stationlist/>"),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "ESM.*station-amplitude XML"):
            client.query(event_id="event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsInstance(client.get_event_data(), ShakeMapEventData)
        self.assertEqual(
            client.get_datasets(),
            {"station_amplitudes": None},
        )


if __name__ == "__main__":
    unittest.main()
