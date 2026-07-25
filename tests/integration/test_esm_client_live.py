# -*- coding: utf-8 -*-
import unittest

from paramws.clients import ESMShakeMapClient


class TestESMClientLive(unittest.TestCase):
    """Exercise the ESM client against the real provider service."""

    def test_query(self):
        # This historical event has event metadata and station amplitudes.
        client = ESMShakeMapClient()
        client.query(event_id="20170524_0000045")
        self.assertIsNotNone(client.get_event_data())
        self.assertIsNotNone(client.get_station_amplitudes())

        # Assert some values from the event data.
        event_data = client.get_event_data()
        self.assertEqual(event_data.get_event_id(), '20170524_0000045')
        self.assertEqual(event_data.get_catalog(), 'EMSC')
        self.assertEqual(event_data.get_network_desc(), 'ESM database')
        self.assertEqual(event_data.get_network_code(), 'ESM')

        # Check some station information.
        for _sta in client.get_stations():
            # Check the components for each field.
            for _comp in _sta.get_components():
                self.assertIsNotNone(_comp.get_component_name())
                self.assertIsNotNone(_comp.get_acceleration())
                self.assertIsNotNone(_comp.get_velocity())
                self.assertIsNotNone(_comp.get_psa03())
                self.assertIsNotNone(_comp.get_psa10())
                self.assertIsNotNone(_comp.get_psa30())
                self.assertIsNotNone(_comp.get_acceleration_flag())
                self.assertIsNotNone(_comp.get_velocity_flag())
                self.assertIsNotNone(_comp.get_psa03_flag())
                self.assertIsNotNone(_comp.get_psa10_flag())
                self.assertIsNotNone(_comp.get_psa30_flag())
