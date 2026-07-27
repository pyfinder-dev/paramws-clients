# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from paramws.clients import RRSMShakeMapClient, RRSMPeakMotionClient
from paramws.utils.customlogger import logger


class TestRRSMClient(unittest.TestCase):
    def test_default_contructor(self):
        # Test the constructor with default values.
        client = RRSMShakeMapClient()

        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(),
                         "https://orfeus-eu.org/odcws/rrsm/")

    def test_set_url_attributes(self):
        # Test the parts of the query url.
        client = RRSMShakeMapClient()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://orfeus-eu.org/odcws/rrsm/")
        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(),
                         "https://orfeus-eu.org/odcws/rrsm/")

    def test_query_null_event_id(self):
        # Test the query method.
        client = RRSMShakeMapClient()
        self.assertRaises(ValueError, client.query, event_id=None)

    def test_shakemap_type_overrides_are_warned_about_and_ignored(self):
        for supplied_type in ("event", "station"):
            with self.subTest(supplied_type=supplied_type):
                client = RRSMShakeMapClient()
                with patch.object(
                        client.get_web_service(),
                        "query",
                        side_effect=[(200, "event data"),
                                     (200, "station data")]) as query:
                    with self.assertLogs(logger, level="WARNING") as captured:
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

    def test_peak_motion_type_is_warned_about_and_omitted(self):
        client = RRSMPeakMotionClient()

        with patch.object(
                client.get_web_service(),
                "query",
                return_value=(200, "peak motion data")) as query:
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

