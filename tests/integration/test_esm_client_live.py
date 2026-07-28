# -*- coding: utf-8 -*-
"""Live public-client coverage for the ESM ShakeMap service."""

import math
import unittest

from paramws.clients import (
    ESMShakeMapClient,
    ShakeMapComponentNode,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from tests.live_result import require_live_result


EVENT_ID = "20170524_0000045"


class TestESMClientLive(unittest.TestCase):
    """Validate stable ESM public result and scientific model invariants."""

    def test_query(self):
        client = ESMShakeMapClient()
        code, event_data, datasets = require_live_result(
            "ESM",
            "event and station_amplitudes",
            lambda: client.query(event_id=EVENT_ID),
        )
        context = "ESM event and station_amplitudes"

        self.assertEqual(code, 200, context)
        self.assertIs(type(event_data), ShakeMapEventData, context)
        self.assertIsInstance(datasets, dict, context)
        self.assertEqual(set(datasets), {"station_amplitudes"}, context)
        self.assertEqual(event_data.get_event_id(), EVENT_ID, context)

        latitude = event_data.get_latitude()
        longitude = event_data.get_longitude()
        magnitude = event_data.get_magnitude()
        depth = event_data.get_depth()
        for label, value in (
                ("latitude", latitude),
                ("longitude", longitude),
                ("magnitude", magnitude),
                ("depth", depth)):
            self.assertIsInstance(value, (int, float),
                                  "{} missing numeric {}".format(
                                      context, label))
            self.assertTrue(math.isfinite(value),
                            "{} has non-finite {}".format(context, label))
        self.assertGreaterEqual(latitude, -90.0, context)
        self.assertLessEqual(latitude, 90.0, context)
        self.assertGreaterEqual(longitude, -180.0, context)
        self.assertLessEqual(longitude, 180.0, context)
        self.assertIsNotNone(event_data.get_origin_time(), context)

        amplitudes = datasets["station_amplitudes"]
        self.assertIs(type(amplitudes), ShakeMapStationAmplitudes, context)
        stations = amplitudes.get_stations()
        self.assertIsInstance(stations, list, context)
        self.assertTrue(stations, "{} returned no stations".format(context))
        self.assertTrue(
            all(type(station) is ShakeMapStationNode for station in stations),
            "{} returned a wrong station model".format(context),
        )

        representative = next(
            (
                (station, component)
                for station in stations
                for component in station.get_components()
                if any(
                    value is not None
                    for value in (
                        component.get_acceleration(),
                        component.get_velocity(),
                        component.get_psa03(),
                        component.get_psa10(),
                        component.get_psa30(),
                    )
                )
            ),
            None,
        )
        self.assertIsNotNone(
            representative,
            "{} has no component with a supported measurement".format(
                context),
        )
        station, component = representative
        self.assertIs(type(component), ShakeMapComponentNode, context)
        self.assertIsInstance(station.get_station_id(), str, context)
        self.assertTrue(station.get_station_id().strip(), context)
        self.assertIsInstance(component.get_component_name(), str, context)
        self.assertTrue(component.get_component_name().strip(), context)

        supplied_measurements = [
            value
            for value in (
                component.get_acceleration(),
                component.get_velocity(),
                component.get_psa03(),
                component.get_psa10(),
                component.get_psa30(),
            )
            if value is not None
        ]
        self.assertTrue(
            all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in supplied_measurements
            ),
            "{} returned a malformed component measurement".format(context),
        )


if __name__ == "__main__":
    unittest.main()
