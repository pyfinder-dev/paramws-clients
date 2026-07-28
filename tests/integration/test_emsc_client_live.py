# -*- coding: utf-8 -*-
"""Live public-client coverage for EMSC felt reports."""

import math
import unittest

from paramws.clients import (
    EMSCFeltReportClient,
    FeltReportEventData,
    FeltReportIntensityData,
)
from tests.live_result import require_live_result


EVENT_ID = "20161030_0000029"


class TestEMSCClientLive(unittest.TestCase):
    """Validate stable EMSC event and felt-intensity invariants."""

    def test_query(self):
        client = EMSCFeltReportClient()
        code, event_data, datasets = require_live_result(
            "EMSC",
            "event and felt_intensities",
            lambda: client.query(event_id=EVENT_ID),
        )
        context = "EMSC event and felt_intensities"

        self.assertEqual(code, 200, context)
        self.assertIs(type(event_data), FeltReportEventData, context)
        self.assertEqual(client.get_event_id(), EVENT_ID, context)
        provider_event_id = event_data.get_event_id()
        self.assertIsInstance(provider_event_id, str, context)
        self.assertIn(
            EVENT_ID,
            provider_event_id,
            "{} returned an unrelated provider event identity".format(
                context),
        )
        self.assertIsInstance(datasets, dict, context)
        self.assertEqual(set(datasets), {"felt_intensities"}, context)
        self.assertIs(
            type(datasets["felt_intensities"]),
            FeltReportIntensityData,
            context,
        )

        latitude = event_data.get_latitude()
        longitude = event_data.get_longitude()
        magnitude = event_data.get_magnitude()
        depth = event_data.get_depth()
        for label, value in (
                ("latitude", latitude),
                ("longitude", longitude),
                ("magnitude", magnitude),
                ("depth", depth)):
            self.assertIsInstance(
                value,
                (int, float),
                "{} missing numeric {}".format(context, label),
            )
            self.assertTrue(
                math.isfinite(value),
                "{} has non-finite {}".format(context, label),
            )
        self.assertGreaterEqual(latitude, -90.0, context)
        self.assertLessEqual(latitude, 90.0, context)
        self.assertGreaterEqual(longitude, -180.0, context)
        self.assertLessEqual(longitude, 180.0, context)
        self.assertIsNotNone(event_data.get_event_time(), context)
        self.assertIsNotNone(event_data.get_event_region(), context)

        intensities = client.get_feltreports()
        self.assertIs(type(intensities), FeltReportIntensityData, context)
        self.assertEqual(intensities.get_event_id(), EVENT_ID, context)
        records = intensities.get_intensities()
        self.assertIsInstance(records, list, context)
        self.assertTrue(
            records,
            "{} returned no felt-intensity records".format(context),
        )

        representative = next(
            (
                record
                for record in records
                if (
                    isinstance(record, dict)
                    and record.get("lon") is not None
                    and record.get("lat") is not None
                    and (
                        record.get("raw") is not None
                        or record.get("corrected") is not None
                    )
                )
            ),
            None,
        )
        self.assertIsNotNone(
            representative,
            "{} has no located intensity measurement".format(context),
        )
        self.assertGreaterEqual(representative["lat"], -90.0, context)
        self.assertLessEqual(representative["lat"], 90.0, context)
        self.assertGreaterEqual(representative["lon"], -180.0, context)
        self.assertLessEqual(representative["lon"], 180.0, context)
        for field in ("raw", "corrected"):
            value = representative.get(field)
            if value is None:
                continue
            self.assertIsInstance(
                value,
                (int, float),
                "{} has nonnumeric {}".format(context, field),
            )
            self.assertNotIsInstance(value, bool, context)
            self.assertTrue(
                math.isfinite(value),
                "{} has non-finite {}".format(context, field),
            )


if __name__ == "__main__":
    unittest.main()
