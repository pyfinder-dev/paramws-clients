# -*- coding: utf-8 -*-
"""Unit tests for the RRSM ShakeMap connector."""
import unittest
from paramws.clients.services import RRSMShakeMapConnector

class TestRRSMShakeMapWebService(unittest.TestCase):
    """Unit tests for the RRSM ShakeMap web service connector."""
    def test_url_build(self):
        # Test the build_url method.
        client = RRSMShakeMapConnector()
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        url = client.build_url()
        self.assertEqual(url, "http://orfeus-eu.org/odcws/rrsm/1/shakemap?")

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
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        url = client.build_url(eventid="test_id")
        self.assertEqual(
            url, "http://orfeus-eu.org/odcws/rrsm/1/shakemap?eventid=test_id")
