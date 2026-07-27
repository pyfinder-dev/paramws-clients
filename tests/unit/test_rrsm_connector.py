# -*- coding: utf-8 -*-
"""Unit tests for the RRSM service connectors."""
import logging
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from paramws.clients.services import (
    BaseWebServiceConnector,
    InvalidOptionValue,
    RRSMPeakMotionConnector,
    RRSMShakeMapConnector,
)
from paramws.utils.customlogger import logger

class TestRRSMShakeMapWebService(unittest.TestCase):
    """Unit tests for the RRSM ShakeMap web service connector."""
    def test_url_build(self):
        # Test the build_url method.
        client = RRSMShakeMapConnector()
        client.set_version("1")
        client.set_end_point("shakemap")
        url = client.build_url()
        self.assertEqual(url, "https://orfeus-eu.org/odcws/rrsm/1/shakemap?")

    def test_supported_options(self):
        # Test the get_supported_options method.
        client = RRSMShakeMapConnector()
        options = client.get_supported_options()
        self.assertEqual(options, ['eventid', 'type'])

    def test_url_build_with_valid_options(self):
        # Test the build_url method with valid, several options.
        client = RRSMShakeMapConnector()
        client.set_version("1")
        client.set_end_point("shakemap")
        url = client.build_url(eventid="test_id")
        self.assertEqual(
            url, "https://orfeus-eu.org/odcws/rrsm/1/shakemap?eventid=test_id")

    def test_shakemap_type_event_is_valid(self):
        client = RRSMShakeMapConnector()

        url = client.build_url(eventid="test_id", type="event")

        self.assertEqual(
            url,
            "https://orfeus-eu.org/odcws/rrsm/1/"
            "shakemap?eventid=test_id&type=event",
        )

    def test_shakemap_rejects_other_type_values(self):
        client = RRSMShakeMapConnector()

        with self.assertRaises(InvalidOptionValue):
            client.build_url(eventid="test_id", type="station")

    def test_shakemap_unsupported_option_is_warned_about_and_removed(self):
        client = RRSMShakeMapConnector()
        root = logging.getLogger()
        root_state = (list(root.handlers), root.level)

        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(eventid="test_id", catalog="EMSC")

        self.assertEqual((list(root.handlers), root.level), root_state)
        self.assertNotIn("catalog", url)
        warning = captured.output[0]
        for context in ("ORFEUS", "shakemap", "catalog", "EMSC"):
            self.assertIn(context, warning)

    def test_peak_motion_supports_only_event_identifier(self):
        client = RRSMPeakMotionConnector()

        self.assertEqual(client.get_supported_options(), ["eventid"])
        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(eventid="test_id", type="event")

        self.assertEqual(
            url,
            "https://orfeus-eu.org/odcws/rrsm/1/"
            "peak-motion?eventid=test_id",
        )
        warning = captured.output[0]
        for context in ("ORFEUS", "peak-motion", "type", "event"):
            self.assertIn(context, warning)

    def test_rrsm_event_identifier_delimiters_round_trip_as_one_value(self):
        event_id = "event&type=event=extra"

        for connector in (
                RRSMShakeMapConnector(),
                RRSMPeakMotionConnector()):
            with self.subTest(endpoint=connector.get_end_point()):
                url = connector.build_url(eventid=event_id)
                parsed_options = parse_qs(urlsplit(url).query)

                self.assertEqual(parsed_options, {"eventid": [event_id]})
                self.assertIn("%26", url)
                self.assertIn("%3D", url)
                self.assertTrue(
                    url.startswith("https://orfeus-eu.org/odcws/rrsm/"))

    def test_rrsm_connectors_are_direct_base_connector_siblings(self):
        self.assertEqual(
            RRSMShakeMapConnector.__bases__,
            (BaseWebServiceConnector,),
        )
        self.assertEqual(
            RRSMPeakMotionConnector.__bases__,
            (BaseWebServiceConnector,),
        )

    def test_valid_rrsm_options_do_not_warn(self):
        with patch.object(logger, "warning") as warning:
            RRSMShakeMapConnector().build_url(
                eventid="test_id",
                type="event",
            )
            RRSMPeakMotionConnector().build_url(eventid="test_id")

        warning.assert_not_called()
