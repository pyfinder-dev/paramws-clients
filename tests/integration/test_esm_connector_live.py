# -*- coding: utf-8 -*-
"""Live checks for the ESM ShakeMap connector."""
import unittest

from paramws.clients.services import ESMShakeMapConnector


class TestESMShakeMapConnectorLive(unittest.TestCase):
    """Exercise connector requests against the real ESM service."""

    def test_query_format_eventdat(self):
        # Request the provider's station-amplitude representation.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        url = client.build_url(
            eventid='20170524_0000045',
            catalog='EMSC',
            format='event_dat')
        code, data = client.query(url=url)

        # Check against common error codes.
        if code != 503:
            # Service is available, so these errors should not be returned
            # if data is not removed from the ESM server. In that case, the
            # error code will be 404.
            for _code in [400, 404, 500, 501, 502]:
                self.assertNotEqual(code, _code)

        # Check the data.
        self.assertIsNotNone(data)

    def test_query_format_event(self):
        # Request the provider's event representation.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        url = client.build_url(
            eventid='20170524_0000045',
            catalog='EMSC',
            format='event')
        code, data = client.query(url=url)

        # Check against common error codes.
        if code != 503:
            # Service is available, so these errors should not be returned
            # if data is not removed from the ESM server. In that case, the
            # error code will be 404.
            for _code in [400, 404, 500, 501, 502]:
                self.assertNotEqual(code, _code)

        # Check the data.
        self.assertIsNotNone(data)

        # Check the data content.
        self.assertEqual(data.get('id'), '20170524_0000045')
        self.assertAlmostEqual(data.get('catalog'), 'EMSC')
        self.assertIsInstance(data.get('lat'), float)
        self.assertGreaterEqual(data.get('lat'), -90.0)
        self.assertLessEqual(data.get('lat'), 90.0)
        self.assertIsInstance(data.get('lon'), float)
        self.assertGreaterEqual(data.get('lon'), -180.0)
        self.assertLessEqual(data.get('lon'), 180.0)
        self.assertIsInstance(data.get('depth'), float)
        self.assertIsInstance(data.get('mag'), float)
