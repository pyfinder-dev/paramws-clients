# -*- coding: utf-8 -*-
from collections import deque
import os
import unittest
import urllib.parse
from unittest.mock import patch

from paramws.clients import RRSMShakeMapClient, RRSMPeakMotionClient
from paramws.clients.services import (
    RRSMPeakMotionConnector,
    RRSMShakeMapConnector,
)
from paramws.clients.services.peakmotion_data import (
    PeakMotionData,
    PeakMotionEventData,
    PeakMotionStationData,
)
from paramws.clients.services.shakemap_data import ShakeMapEventData
from paramws.clients.services.shakemap_data import ShakeMapStationAmplitudes
from paramws.utils.customlogger import logger
from tests.unit.request_double import ScriptedRequest


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_content(filename):
    """Return one deterministic RRSM response from the fixture directory."""
    with open(
            os.path.join(FIXTURE_DIRECTORY, filename),
            "r",
            encoding="utf-8") as fixture:
        return fixture.read()


class ControlledRRSMConnector:
    """Return prepared RRSM models while recording logical request options."""

    def __init__(self, outcomes):
        self.outcomes = deque(outcomes)
        self.built_options = []
        self.requested_urls = []
        self.validated_options = []
        self.data = None
        self._validator = RRSMShakeMapConnector()

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
        return outcome

    def validate_options(self, **options):
        """Use the production RRSM connector's option contract."""
        cleaned_options = self._validator.validate_options(**options)
        self.validated_options.append(dict(cleaned_options))
        return cleaned_options

    def set_data(self, data):
        self.data = data


class ControlledPeakMotionConnector:
    """Return prepared Peak Motion results and record per-query state."""

    def __init__(self, outcomes):
        self.outcomes = deque(outcomes)
        self.built_options = []
        self.requested_urls = []
        self.validated_options = []
        self.data = None
        self._validator = RRSMPeakMotionConnector()

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


def event_model(event_id="rrsm-event-one"):
    """Return the actual event model used by the public RRSM interface."""
    return ShakeMapEventData({"id": event_id})


def amplitude_model():
    """Return the actual station-amplitude model used by the RRSM interface."""
    return ShakeMapStationAmplitudes({"created": None, "stations": []})


def peak_motion_model(event_id="peak-event-one"):
    """Return the established combined Peak Motion hierarchy."""
    peak_motion = PeakMotionData()
    peak_motion.set_event_data(PeakMotionEventData({"event-id": event_id}))
    peak_motion.add_station(
        PeakMotionStationData({"station-code": "TEST"}))
    return peak_motion


class TestRRSMClient(unittest.TestCase):
    def test_default_contructor(self):
        client = RRSMShakeMapClient()

        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(
            client.get_base_url(),
            "https://orfeus-eu.org/odcws/rrsm/",
        )

    def test_set_url_attributes(self):
        client = RRSMShakeMapClient()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://orfeus-eu.org/odcws/rrsm/")

        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(
            client.get_base_url(),
            "https://orfeus-eu.org/odcws/rrsm/",
        )

    def test_query_null_event_id_resets_current_state(self):
        client = RRSMShakeMapClient()
        client.set_event_id("previous-event")
        client.set_event_data(event_model("previous-event"))
        client.set_station_amplitudes(amplitude_model())
        client.get_web_service().set_data("previous response")

        with self.assertRaisesRegex(ValueError, "event_id"):
            client.query(event_id=None)

        self.assertIsNone(client.get_event_id())
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"station_amplitudes": None})
        self.assertIsNone(client.get_web_service().get_data())

    def test_success_returns_exact_models_and_dataset_dictionary(self):
        expected_event = event_model()
        expected_amplitudes = amplitude_model()
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, expected_event),
            (200, expected_amplitudes),
        ])
        client.ws_client = connector

        result = client.query(event_id="rrsm-event-one")

        self.assertEqual(len(result), 3)
        code, event_data, datasets = result
        self.assertEqual(code, 200)
        self.assertIs(event_data, expected_event)
        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertEqual(set(datasets), {"station_amplitudes"})
        self.assertIs(datasets["station_amplitudes"], expected_amplitudes)
        self.assertIsInstance(
            datasets["station_amplitudes"],
            ShakeMapStationAmplitudes,
        )
        self.assertIsNot(event_data, datasets["station_amplitudes"])

    def test_event_request_precedes_station_amplitudes(self):
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        client.query(event_id="rrsm-event-one")

        self.assertEqual(connector.built_options, [
            {"eventid": "rrsm-event-one", "type": "event"},
            {"eventid": "rrsm-event-one"},
        ])
        self.assertEqual(connector.requested_urls, [
            "https://example.test/query?"
            "eventid=rrsm-event-one&type=event",
            "https://example.test/query?eventid=rrsm-event-one",
        ])

    def test_event_http_failure_keeps_successful_station_amplitudes(self):
        expected_amplitudes = amplitude_model()
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (404, None),
            (200, expected_amplitudes),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(
            event_id="rrsm-event-one")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertIs(datasets["station_amplitudes"], expected_amplitudes)
        self.assertEqual(len(connector.requested_urls), 2)

    def test_station_http_failure_keeps_successful_event(self):
        expected_event = event_model()
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, expected_event),
            (410, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(
            event_id="rrsm-event-one")

        self.assertEqual(code, 410)
        self.assertIs(event_data, expected_event)
        self.assertIsNone(datasets["station_amplitudes"])

    def test_two_http_failures_preserve_first_status(self):
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (404, None),
            (422, None),
        ])
        client.ws_client = connector

        code, event_data, datasets = client.query(
            event_id="rrsm-event-one")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertIsNone(datasets["station_amplitudes"])
        self.assertEqual(len(connector.requested_urls), 2)

    def test_invalid_successful_event_still_retrieves_station_amplitudes(self):
        client = RRSMShakeMapClient()
        scripted_request = ScriptedRequest([
            (200, "<not-an-earthquake/>"),
            (200, fixture_content("rrsm-shakemap-stations.xml")),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "RRSM/ORFEUS.*ShakeMap event XML"):
            client.query(event_id="rrsm-event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsNone(client.get_event_data())
        self.assertIsInstance(
            client.get_datasets()["station_amplitudes"],
            ShakeMapStationAmplitudes,
        )

    def test_invalid_successful_station_content_raises_value_error(self):
        client = RRSMShakeMapClient()
        scripted_request = ScriptedRequest([
            (200, fixture_content("rrsm-shakemap-event.xml")),
            (200, "<not-a-stationlist/>"),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "RRSM/ORFEUS.*station-amplitude XML"):
            client.query(event_id="rrsm-event-one")

        self.assertEqual(len(scripted_request.requested_urls), 2)
        self.assertIsInstance(client.get_event_data(), ShakeMapEventData)
        self.assertEqual(
            client.get_datasets(),
            {"station_amplitudes": None},
        )

    def test_two_parse_failures_preserve_event_failure(self):
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            ValueError("first event parse failure"),
            ValueError("later station parse failure"),
        ])
        client.ws_client = connector

        with self.assertRaisesRegex(ValueError, "first event parse failure"):
            client.query(event_id="rrsm-event-one")

        self.assertEqual(len(connector.requested_urls), 2)
        self.assertIsNone(client.get_event_data())
        self.assertEqual(
            client.get_datasets(),
            {"station_amplitudes": None},
        )

    def test_repeated_queries_clear_results_and_do_not_leak_options(self):
        first_event = event_model("first-event")
        first_amplitudes = amplitude_model()
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, first_event),
            (200, first_amplitudes),
            (404, None),
            (410, None),
        ])
        client.ws_client = connector

        with self.assertLogs(logger, level="WARNING"):
            client.query(
                event_id="first-event",
                type="station",
                unexpected="first-value",
            )
        code, event_data, datasets = client.query(event_id="second-event")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {"station_amplitudes": None})
        self.assertIsNone(client.get_event_data())
        self.assertIsNone(client.get_station_amplitudes())
        self.assertEqual(client.get_event_id(), "second-event")
        self.assertEqual(connector.validated_options, [{}, {}])
        self.assertEqual(connector.built_options[2:], [
            {"eventid": "second-event", "type": "event"},
            {"eventid": "second-event"},
        ])

    def test_fixed_native_option_overrides_are_warned_about_and_ignored(self):
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        with self.assertLogs(logger, level="WARNING") as captured:
            client.query(
                event_id="authoritative-event",
                eventid="ignored-event",
                type="station",
            )

        self.assertEqual(len(captured.output), 2)
        warnings = "\n".join(captured.output)
        self.assertIn("eventid", warnings)
        self.assertIn("ignored-event", warnings)
        self.assertIn("authoritative-event", warnings)
        self.assertIn("type", warnings)
        self.assertIn("station", warnings)
        self.assertIn("type='event'", warnings)
        self.assertIn("type omitted", warnings)
        self.assertEqual(connector.built_options, [
            {"eventid": "authoritative-event", "type": "event"},
            {"eventid": "authoritative-event"},
        ])

    def test_unsupported_option_is_warned_about_and_removed(self):
        client = RRSMShakeMapClient()
        connector = ControlledRRSMConnector([
            (200, event_model()),
            (200, amplitude_model()),
        ])
        client.ws_client = connector

        with self.assertLogs(logger, level="WARNING") as captured:
            client.query(
                event_id="rrsm-event-one",
                unexpected="caller-value",
            )

        self.assertEqual(len(captured.output), 1)
        warning = captured.output[0]
        for context in (
                "ORFEUS", "shakemap", "unexpected", "caller-value"):
            self.assertIn(context, warning)
        for options in connector.built_options:
            self.assertNotIn("unexpected", options)

    def test_shakemap_type_overrides_are_warned_about_and_ignored(self):
        for supplied_type in ("event", "station"):
            with self.subTest(supplied_type=supplied_type):
                client = RRSMShakeMapClient()
                with patch.object(
                        client.get_web_service(),
                        "query",
                        side_effect=[(200, event_model()),
                                     (200, amplitude_model())]) as query:
                    with self.assertLogs(
                            logger, level="WARNING") as captured:
                        client.query(
                            event_id="test_id",
                            type=supplied_type,
                        )

                event_url = query.call_args_list[0].kwargs["url"]
                station_url = query.call_args_list[1].kwargs["url"]
                self.assertEqual(
                    event_url,
                    "https://orfeus-eu.org/odcws/rrsm/1/"
                    "shakemap?eventid=test_id&type=event",
                )
                self.assertEqual(
                    station_url,
                    "https://orfeus-eu.org/odcws/rrsm/1/"
                    "shakemap?eventid=test_id",
                )
                warning = captured.output[0]
                for context in (
                        "ORFEUS", "shakemap", "type", supplied_type,
                        "event request", "station request"):
                    self.assertIn(context, warning)

    def test_peak_motion_success_returns_separate_established_models(self):
        expected_peak_motion = peak_motion_model()
        client = RRSMPeakMotionClient()

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(200, expected_peak_motion)) as query:
            result = client.query(event_id="peak-event-one")

        self.assertEqual(len(result), 3)
        code, event_data, datasets = result
        self.assertEqual(code, 200)
        self.assertIsInstance(event_data, PeakMotionEventData)
        self.assertIs(
            event_data,
            expected_peak_motion.get_event_data(),
        )
        self.assertEqual(set(datasets), {"peak_motion"})
        self.assertIs(datasets["peak_motion"], expected_peak_motion)
        self.assertIsInstance(datasets["peak_motion"], PeakMotionData)
        self.assertIsNot(event_data, datasets["peak_motion"])
        self.assertIs(
            client.get_station_amplitudes(),
            expected_peak_motion,
        )
        self.assertEqual(client.get_station_codes(), ["TEST"])
        self.assertEqual(
            client.get_stations(),
            expected_peak_motion.get_stations(),
        )
        query.assert_called_once_with(
            url="https://orfeus-eu.org/odcws/rrsm/1/"
            "peak-motion?eventid=peak-event-one",
        )

    def test_peak_motion_http_failure_preserves_status_and_empty_state(self):
        client = RRSMPeakMotionClient()
        client.set_event_data(
            peak_motion_model("previous").get_event_data())
        client.set_station_amplitudes(peak_motion_model("previous"))
        client.get_web_service().set_data("previous response")

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(503, None)) as query:
            code, event_data, datasets = client.query(
                event_id="failed-event")

        self.assertEqual(code, 503)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {"peak_motion": None})
        self.assertIsNone(client.get_event_data())
        self.assertIsNone(client.get_station_amplitudes())
        self.assertIsNone(client.get_web_service().get_data())
        query.assert_called_once()

    def test_peak_motion_invalid_success_content_raises_value_error(self):
        client = RRSMPeakMotionClient()
        scripted_request = ScriptedRequest([
            (200, "{not valid JSON"),
        ])
        client.get_web_service()._request_callable = scripted_request.request
        client.get_web_service()._delay_callable = scripted_request.delay

        with self.assertRaisesRegex(
                ValueError, "RRSM Peak Motion.*malformed JSON"):
            client.query(event_id="invalid-content")

        self.assertEqual(
            scripted_request.requested_urls,
            [
                "https://orfeus-eu.org/odcws/rrsm/1/"
                "peak-motion?eventid=invalid-content",
            ],
        )
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"peak_motion": None})
        self.assertIsNone(client.get_web_service().get_data())

    def test_peak_motion_missing_event_resets_all_query_state(self):
        client = RRSMPeakMotionClient()
        client.set_event_id("previous-event")
        client.set_event_data(
            peak_motion_model("previous-event").get_event_data())
        client.set_station_amplitudes(peak_motion_model("previous-event"))
        client.get_web_service().set_data("previous response")

        with self.assertRaisesRegex(ValueError, "event_id"):
            client.query(event_id=None)

        self.assertIsNone(client.get_event_id())
        self.assertIsNone(client.event_options["eventid"])
        self.assertIsNone(client.amplitude_options["eventid"])
        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"peak_motion": None})
        self.assertIsNone(client.get_web_service().get_data())

    def test_peak_motion_repeated_queries_isolate_all_query_state(self):
        first_peak_motion = peak_motion_model("first-event")
        client = RRSMPeakMotionClient()
        connector = ControlledPeakMotionConnector([
            (200, first_peak_motion),
            (404, None),
        ])
        client.ws_client = connector

        with self.assertLogs(logger, level="WARNING"):
            client.query(
                event_id="first-event",
                eventid="ignored-event",
                type="event",
                unexpected="first-value",
            )
        code, event_data, datasets = client.query(event_id="second-event")

        self.assertEqual(code, 404)
        self.assertIsNone(event_data)
        self.assertEqual(datasets, {"peak_motion": None})
        self.assertEqual(client.get_event_id(), "second-event")
        self.assertEqual(client.event_options["eventid"], "second-event")
        self.assertEqual(
            client.amplitude_options["eventid"],
            "second-event",
        )
        self.assertEqual(connector.validated_options, [{}, {}])
        self.assertEqual(connector.built_options, [
            {"eventid": "first-event"},
            {"eventid": "second-event"},
        ])
        self.assertEqual(connector.requested_urls, [
            "https://example.test/query?eventid=first-event",
            "https://example.test/query?eventid=second-event",
        ])
        self.assertIsNone(connector.get_data())

    def test_peak_motion_eventid_override_is_warned_about_and_ignored(self):
        client = RRSMPeakMotionClient()
        expected_peak_motion = peak_motion_model("authoritative-event")

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(200, expected_peak_motion)) as query:
            with self.assertLogs(logger, level="WARNING") as captured:
                client.query(
                    event_id="authoritative-event",
                    eventid="ignored-event",
                )

        warning = captured.output[0]
        for context in (
                "ORFEUS", "peak-motion", "eventid", "ignored-event",
                "authoritative-event"):
            self.assertIn(context, warning)
        query.assert_called_once_with(
            url="https://orfeus-eu.org/odcws/rrsm/1/"
            "peak-motion?eventid=authoritative-event",
        )

    def test_peak_motion_type_is_warned_about_and_omitted(self):
        client = RRSMPeakMotionClient()

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(200, peak_motion_model())) as query:
            with self.assertLogs(logger, level="WARNING") as captured:
                client.query(event_id="test_id", type="event")

        requested_url = query.call_args.kwargs["url"]
        self.assertEqual(
            requested_url,
            "https://orfeus-eu.org/odcws/rrsm/1/"
            "peak-motion?eventid=test_id",
        )
        warning = captured.output[0]
        for context in ("ORFEUS", "peak-motion", "type", "event"):
            self.assertIn(context, warning)

    def test_peak_motion_unsupported_option_is_warned_about_and_removed(self):
        client = RRSMPeakMotionClient()

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(200, peak_motion_model())) as query:
            with self.assertLogs(logger, level="WARNING") as captured:
                client.query(
                    event_id="test_id",
                    unexpected="caller-value",
                )

        warning = captured.output[0]
        for context in (
                "ORFEUS", "peak-motion", "unexpected", "caller-value"):
            self.assertIn(context, warning)
        requested_url = query.call_args.kwargs["url"]
        self.assertNotIn("unexpected", requested_url)


if __name__ == "__main__":
    unittest.main()
