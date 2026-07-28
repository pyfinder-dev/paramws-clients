# -*- coding: utf-8 -*-
"""Live response-shape checks for the ESM ShakeMap connector."""

import math
import unittest

from paramws.clients.services import (
    ESMShakeMapConnector,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from tests.live_result import require_live_result


EVENT_ID = "20170524_0000045"


class TestESMShakeMapConnectorLive(unittest.TestCase):
    """Exercise both current ESM representations against the real service."""

    def setUp(self):
        self.connector = ESMShakeMapConnector(
            agency="ESM",
            base_url="https://esm-db.eu/esmws",
            end_point="shakemap",
            version="1",
        )

    def test_query_format_eventdat(self):
        url = self.connector.build_url(
            eventid=EVENT_ID,
            catalog="EMSC",
            format="event_dat",
        )
        code, data = require_live_result(
            "ESM",
            "station_amplitudes connector response",
            lambda: self.connector.query(url=url),
        )
        context = "ESM station_amplitudes connector response"

        self.assertEqual(code, 200, context)
        self.assertIs(type(data), ShakeMapStationAmplitudes, context)
        stations = data.get_stations()
        self.assertIsInstance(stations, list, context)
        self.assertTrue(stations, "{} returned no stations".format(context))
        self.assertTrue(
            all(type(station) is ShakeMapStationNode for station in stations),
            "{} returned a wrong station model".format(context),
        )

    def test_query_format_event(self):
        url = self.connector.build_url(
            eventid=EVENT_ID,
            catalog="EMSC",
            format="event",
        )
        code, data = require_live_result(
            "ESM",
            "event connector response",
            lambda: self.connector.query(url=url),
        )
        context = "ESM event connector response"

        self.assertEqual(code, 200, context)
        self.assertIs(type(data), ShakeMapEventData, context)
        self.assertEqual(data.get_event_id(), EVENT_ID, context)

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
