# -*- coding: utf-8 -*-
import unittest

from paramws.clients import EMSCFeltReportClient


class TestEMSCClientLive(unittest.TestCase):
    """Exercise the EMSC client against the real provider service."""

    def test_query(self):
        # This historical event provides both event details and felt reports.
        client = EMSCFeltReportClient()
        code, _, _ = client.query(event_id='20161030_0000029')

        if code != 200:
            self.skipTest("The web service is not available.")

        event_data = client.get_event_data()

        self.assertIsNotNone(event_data.get_event_deltatime())
        self.assertIsNotNone(event_data.get_event_id())
        self.assertIsNotNone(event_data.get_latitude())
        self.assertIsNotNone(event_data.get_longitude())
        self.assertIsNotNone(event_data.get_magnitude())
        self.assertIsNotNone(event_data.get_magnitude_type())
        self.assertIsNotNone(event_data.get_event_time())
        self.assertIsNotNone(event_data.get_depth())
        self.assertIsNotNone(event_data.get_event_nbtestimonies())
        self.assertIsNotNone(event_data.get_event_region())
        self.assertIsNotNone(event_data.get_event_last_update())

        intensities = client.get_feltreports()
        self.assertIsNotNone(intensities)
        self.assertEqual(intensities.get_event_id(), "20161030_0000029")
        self.assertIsNotNone(intensities.get_intensities())
