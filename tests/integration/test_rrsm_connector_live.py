# -*- coding: utf-8 -*-
"""Live checks for the RRSM ShakeMap connector."""
import unittest

from paramws.clients.services import RRSMShakeMapConnector


class TestRRSMShakeMapConnectorLive(unittest.TestCase):
    """Exercise connector requests against the real RRSM service."""

    def test_query_with_supported_options(self):
        # Request the provider's station representation.
        client = RRSMShakeMapConnector()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        url = client.build_url(eventid='20170524_0000045')
        code, data = client.query(url=url)

        # Check the query against common error codes.
        if code != 503:
            # Service is available, so these errors should not be returned
            # if data is not removed from the RRSM server. In that case, the
            # error code will be 404.
            for _code in [400, 404, 500, 501, 502]:
                self.assertNotEqual(code, _code)

        # Check the data.
        self.assertIsNotNone(data)

        # Check the data content.
        self.assertEqual(data.get_stations()[0].get('code'), 'KBN')

        # Check the URL.
        self.assertEqual(
            url,
            "http://orfeus-eu.org/odcws/rrsm/1/"
            "shakemap?eventid=20170524_0000045")

    def test_query_with_unsupported_options(self):
        # This request also verifies that unsupported options are removed.
        client = RRSMShakeMapConnector()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        url = client.build_url(
            eventid='20170524_0000045',
            catalog='EMSC',
            format='event_dat')
        code, data = client.query(url=url)

        # Check the query against common error codes.
        if code != 503:
            # Service is available, so these errors should not be returned
            # if data is not removed from the RRSM server. In that case, the
            # error code will be 404.
            for _code in [400, 404, 500, 501, 502]:
                self.assertNotEqual(code, _code)

        # Check the data.
        self.assertIsNotNone(data)

        # Check the data content.
        self.assertEqual(data.get_stations()[0].get('code'), 'KBN')

        # Check if unsupported options are removed from the URL.
        self.assertEqual(
            url,
            "http://orfeus-eu.org/odcws/rrsm/1/"
            "shakemap?eventid=20170524_0000045")

    def test_query_event_data(self):
        # Request the provider's event representation.
        client = RRSMShakeMapConnector()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        url = client.build_url(
            eventid='20170524_0000045',
            type='event')
        code, data = client.query(url=url)

        # Check the event-selection URL.
        self.assertEqual(
            url,
            "http://orfeus-eu.org/odcws/rrsm/1/"
            "shakemap?eventid=20170524_0000045&type=event")

        # Check the query against common error codes.
        if code != 503:
            # Service is available, so these errors should not be returned
            # if data is not removed from the RRSM server. In that case, the
            # error code will be 404.
            for _code in [400, 404, 500, 501, 502]:
                self.assertNotEqual(code, _code)

        # Check the data.
        self.assertIsNotNone(data)

        # The id and coordinates differ from EMSC, and no catalog key exists.
        self.assertAlmostEqual(data.get('lat'), 41.53)
        self.assertAlmostEqual(data.get('lon'), 20.22)
        self.assertAlmostEqual(data.get('depth'), 14)
        self.assertAlmostEqual(data.get('mag'), 4.6)
