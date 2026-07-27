# -*- coding: utf-8 -*-
import copy
from io import StringIO
import json
import os
import unittest

from paramws.clients.services.rrsm.peakmotion_parser import RRSMPeakMotionParser
from paramws.clients.services.peakmotion_data import (
    PeakMotionChannelData,
    PeakMotionData,
    PeakMotionEventData,
    PeakMotionStationData,
)


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_json(filename):
    """Return one deterministic RRSM Peak Motion JSON value."""
    with open(
            os.path.join(FIXTURE_DIRECTORY, filename),
            "r",
            encoding="utf-8") as fixture:
        return json.load(fixture)


def parse_json(value):
    """Parse an in-memory provider value without network access."""
    return RRSMPeakMotionParser().parse(StringIO(json.dumps(value)))


class TestRRSMPeakMotionParser(unittest.TestCase):
    """Test the parser for the RRSM peak-motion web service."""
    def test_multiple_records_preserve_established_model_hierarchy(self):
        parsed_data = parse_json(fixture_json("rrsm-peakmotion.json"))

        self.assertIsInstance(parsed_data, PeakMotionData)
        self.assertIsInstance(
            parsed_data.get_event_data(),
            PeakMotionEventData,
        )
        self.assertEqual(
            parsed_data.get_event_data().get_event_id(),
            "20170524_0000045",
        )
        self.assertEqual(
            parsed_data.get_station_codes(),
            ["KBN", "PDG", "TIR"],
        )
        self.assertEqual(len(parsed_data.get_stations()), 3)
        for station in parsed_data.get_stations():
            self.assertIsInstance(station, PeakMotionStationData)
            self.assertEqual(
                station.get_channel_codes(),
                ["HHE", "HHN", "HHZ"],
            )
            for channel in station.get_channels():
                self.assertIsInstance(channel, PeakMotionChannelData)
                self.assertEqual(
                    channel["channel-code"],
                    channel.get_channel_code(),
                )

    def test_singleton_list_and_wrapped_event_list_are_supported(self):
        records = fixture_json("rrsm-peakmotion-single.json")

        for provider_value in (
                records,
                {"event-list": records}):
            with self.subTest(wrapped=isinstance(provider_value, dict)):
                parsed_data = parse_json(provider_value)

                self.assertIsInstance(parsed_data, PeakMotionData)
                self.assertEqual(
                    parsed_data.get_event_data().get_event_id(),
                    "single-event",
                )
                self.assertEqual(
                    parsed_data.get_station_codes(),
                    ["TEST"],
                )
                self.assertEqual(
                    parsed_data.get_stations()[0].get_channel_codes(),
                    ["HHE"],
                )

    def test_empty_event_collection_is_rejected(self):
        for provider_value in ([], {"event-list": []}):
            with self.subTest(provider_value=provider_value):
                with self.assertRaisesRegex(
                        ValueError,
                        "RRSM Peak Motion.*non-empty.*event-list"):
                    parse_json(provider_value)

    def test_malformed_json_is_rejected_with_provider_context(self):
        with self.assertRaisesRegex(
                ValueError, "RRSM Peak Motion.*malformed JSON"):
            RRSMPeakMotionParser().parse(StringIO("{not valid JSON"))

    def test_absent_or_non_list_event_collection_is_rejected(self):
        for provider_value in (
                {},
                {"event-list": None},
                {"event-list": {}},
                "not an event collection"):
            with self.subTest(provider_value=provider_value):
                with self.assertRaisesRegex(
                        ValueError, "RRSM Peak Motion.*event-list"):
                    parse_json(provider_value)

    def test_missing_event_field_is_rejected(self):
        records = fixture_json("rrsm-peakmotion-single.json")
        del records[0]["event-id"]

        with self.assertRaisesRegex(
                ValueError, "RRSM Peak Motion.*event-id"):
            parse_json(records)

    def test_missing_station_field_is_rejected(self):
        records = fixture_json("rrsm-peakmotion-single.json")
        del records[0]["station-code"]

        with self.assertRaisesRegex(
                ValueError, "RRSM Peak Motion.*station-code"):
            parse_json(records)

    def test_sensor_channels_must_exist_and_be_a_list(self):
        records = fixture_json("rrsm-peakmotion-single.json")
        missing_channels = copy.deepcopy(records)
        del missing_channels[0]["sensor-channels"]
        non_list_channels = copy.deepcopy(records)
        non_list_channels[0]["sensor-channels"] = {}

        for provider_value in (missing_channels, non_list_channels):
            with self.subTest(provider_value=provider_value):
                with self.assertRaisesRegex(
                        ValueError, "RRSM Peak Motion.*sensor-channels"):
                    parse_json(provider_value)

    def test_missing_channel_field_is_rejected(self):
        records = fixture_json("rrsm-peakmotion-single.json")
        del records[0]["sensor-channels"][0]["channel-code"]

        with self.assertRaisesRegex(
                ValueError, "RRSM Peak Motion.*channel-code"):
            parse_json(records)

    def test_non_object_records_are_rejected_with_structure_context(self):
        records = fixture_json("rrsm-peakmotion-single.json")
        malformed_values = (
            [None],
            [{**records[0], "sensor-channels": [None]}],
        )

        for provider_value in malformed_values:
            with self.subTest(provider_value=provider_value):
                with self.assertRaisesRegex(
                        ValueError, "RRSM Peak Motion.*object"):
                    parse_json(provider_value)
