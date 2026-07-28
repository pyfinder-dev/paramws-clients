# -*- coding: utf-8 -*-
"""Live response-shape checks for the ORFEUS RRSM ShakeMap connector."""

import math
import unittest

from paramws.clients.services import (
    RRSMShakeMapConnector,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from tests.live_result import require_live_result


EVENT_ID = "20170524_0000045"
BASE_URL = "https://orfeus-eu.org/odcws/rrsm/"


class TestRRSMShakeMapConnectorLive(unittest.TestCase):
    """Exercise both RRSM ShakeMap representations over canonical HTTPS."""

    def setUp(self):
        self.connector = RRSMShakeMapConnector(
            agency="ORFEUS",
            base_url=BASE_URL,
            end_point="shakemap",
            version="1",
        )

    def test_query_station_data(self):
        url = self.connector.build_url(eventid=EVENT_ID)
        code, data = require_live_result(
            "ORFEUS RRSM",
            "station_amplitudes connector response",
            lambda: self.connector.query(url=url),
        )
        context = "ORFEUS RRSM station_amplitudes connector response"

        self.assertEqual(
            url,
            BASE_URL + "1/shakemap?eventid=" + EVENT_ID,
            "{} did not use the canonical HTTPS URL".format(context),
        )
        self.assertEqual(code, 200, context)
        self.assertIs(type(data), ShakeMapStationAmplitudes, context)
        stations = data.get_stations()
        self.assertIsInstance(stations, list, context)
        self.assertTrue(stations, "{} returned no stations".format(context))
        self.assertTrue(
            all(type(station) is ShakeMapStationNode for station in stations),
            "{} returned a wrong station model".format(context),
        )

    def test_query_event_data(self):
        url = self.connector.build_url(eventid=EVENT_ID, type="event")
        code, data = require_live_result(
            "ORFEUS RRSM",
            "event connector response",
            lambda: self.connector.query(url=url),
        )
        context = "ORFEUS RRSM event connector response"

        self.assertEqual(
            url,
            BASE_URL + "1/shakemap?eventid=" + EVENT_ID + "&type=event",
            "{} did not use the canonical HTTPS URL".format(context),
        )
        self.assertEqual(code, 200, context)
        self.assertIs(type(data), ShakeMapEventData, context)
        self.assertIsInstance(data.get_event_id(), str, context)
        self.assertTrue(data.get_event_id().strip(), context)

        for label, value, lower, upper in (
                ("latitude", data.get_latitude(), -90.0, 90.0),
                ("longitude", data.get_longitude(), -180.0, 180.0)):
            self.assertIsInstance(
                value,
                (int, float),
                "{} missing numeric {}".format(context, label),
            )
            self.assertTrue(
                math.isfinite(value),
                "{} has non-finite {}".format(context, label),
            )
            self.assertGreaterEqual(value, lower, context)
            self.assertLessEqual(value, upper, context)

        for label, value in (
                ("depth", data.get_depth()),
                ("magnitude", data.get_magnitude())):
            self.assertIsInstance(
                value,
                (int, float),
                "{} missing numeric {}".format(context, label),
            )
            self.assertTrue(
                math.isfinite(value),
                "{} has non-finite {}".format(context, label),
            )


if __name__ == "__main__":
    unittest.main()
