# -*- coding: utf-8 -*-
"""Live public-client coverage for the ORFEUS RRSM services."""

import math
import unittest

from paramws.clients import (
    PeakMotionChannelData,
    PeakMotionData,
    PeakMotionStationData,
    RRSMShakeMapClient,
    RRSMPeakMotionClient,
    ShakeMapComponentNode,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from paramws.clients.services.peakmotion_data import PeakMotionEventData
from tests.live_result import require_live_result


EVENT_ID = "20170524_0000045"


class TestRRSMClientLive(unittest.TestCase):
    """Validate stable RRSM result, identity, and model invariants."""

    def test_rrsm_shakemap_query(self):
        client = RRSMShakeMapClient()
        code, event_data, datasets = require_live_result(
            "ORFEUS RRSM",
            "ShakeMap event and station_amplitudes",
            lambda: client.query(event_id=EVENT_ID),
        )
        context = "ORFEUS RRSM ShakeMap"

        self.assertEqual(code, 200, context)
        self.assertIs(type(event_data), ShakeMapEventData, context)
        self.assertEqual(client.get_event_id(), EVENT_ID, context)
        self.assertIsInstance(event_data.get_event_id(), str, context)
        self.assertTrue(event_data.get_event_id().strip(), context)
        self.assertIsInstance(datasets, dict, context)
        self.assertEqual(set(datasets), {"station_amplitudes"}, context)

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
                component
                for station in stations
                for component in station.get_components()
                if (
                    component.get_acceleration() is not None
                    or component.get_velocity() is not None
                )
            ),
            None,
        )
        self.assertIsNotNone(
            representative,
            "{} has no component with PGA or PGV".format(context),
        )
        self.assertIs(type(representative), ShakeMapComponentNode, context)
        self.assertIsInstance(
            representative.get_component_name(),
            str,
            "{} has a component without identity".format(context),
        )

        supplied = [
            value
            for value in (
                representative.get_acceleration(),
                representative.get_velocity(),
            )
            if value is not None
        ]
        self.assertTrue(
            all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                for value in supplied
            ),
            "{} returned malformed PGA or PGV".format(context),
        )

    def test_rrsm_peakmotions_query(self):
        client = RRSMPeakMotionClient()
        code, event_data, datasets = require_live_result(
            "ORFEUS RRSM",
            "peak_motion",
            lambda: client.query(event_id=EVENT_ID),
        )
        context = "ORFEUS RRSM peak_motion"

        self.assertEqual(code, 200, context)
        self.assertIs(type(event_data), PeakMotionEventData, context)
        self.assertEqual(event_data.get_event_id(), EVENT_ID, context)
        self.assertIsInstance(datasets, dict, context)
        self.assertEqual(set(datasets), {"peak_motion"}, context)

        peak_motion = datasets["peak_motion"]
        self.assertIs(type(peak_motion), PeakMotionData, context)
        stations = peak_motion.get_stations()
        self.assertIsInstance(stations, list, context)
        self.assertTrue(stations, "{} returned no stations".format(context))
        self.assertTrue(
            all(type(station) is PeakMotionStationData
                for station in stations),
            "{} returned a wrong station model".format(context),
        )

        representative = next(
            (
                (station, channel)
                for station in stations
                for channel in station.get_channels()
                if (
                    channel.get_acceleration() is not None
                    or channel.get_velocity() is not None
                )
            ),
            None,
        )
        self.assertIsNotNone(
            representative,
            "{} has no channel with PGA or PGV".format(context),
        )
        station, channel = representative
        self.assertIs(type(channel), PeakMotionChannelData, context)
        self.assertIsInstance(station.get_station_code(), str, context)
        self.assertTrue(station.get_station_code().strip(), context)
        self.assertIsInstance(channel.get_channel_code(), str, context)
        self.assertTrue(channel.get_channel_code().strip(), context)

        for label, value in (
                ("PGA", channel.get_acceleration()),
                ("PGV", channel.get_velocity())):
            if value is None:
                continue
            self.assertIsInstance(
                value,
                (int, float),
                "{} has nonnumeric {}".format(context, label),
            )
            self.assertNotIsInstance(value, bool, context)
            self.assertTrue(
                math.isfinite(value),
                "{} has non-finite {}".format(context, label),
            )


if __name__ == "__main__":
    unittest.main()
