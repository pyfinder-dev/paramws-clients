# -*- coding: utf-8 -*-
"""Unit tests for the ESM ShakeMap connector."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from paramws.clients.services import InvalidOptionValue
from paramws.clients.services import ESMShakeMapConnector
from paramws.utils.customlogger import logger

class TestESMShakeMapWebService(unittest.TestCase):
    """Unit tests for the ESM ShakeMap web service connector."""
    def test_url_build(self):
        # Test the build_url method.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        url = client.build_url()
        self.assertEqual(url, "https://esm-db.eu/esmws/shakemap/1/query?")


    def test_url_build_with_valid_options(self):
        # Test the build_url method with valid, several options.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        url = client.build_url(eventid="test_id")
        self.assertEqual(url, "https://esm-db.eu/esmws/shakemap/1/query?"
                         "eventid=test_id")

        # Test with several valid flags
        url = client.build_url(eventid="test_id", format="event_dat", catalog="ESM")
        self.assertEqual(url, "https://esm-db.eu/esmws/shakemap/1/query?"
                         "eventid=test_id&format=event_dat&catalog=ESM")


    def test_url_build_invalid_options(self):
        # Unsupported names are ignored explicitly rather than silently.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        options = dict(eventid="test_id", format="event_dat",
                       catalog="ESM", uknown_flag="not_a_valid_value")

        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(**options)

        self.assertNotIn("uknown_flag", url)
        self.assertEqual(options["uknown_flag"], "not_a_valid_value")
        warning = captured.output[0]
        for context in ("ESM", "shakemap", "uknown_flag",
                        "not_a_valid_value"):
            self.assertIn(context, warning)

    def test_url_build_invalid_value(self):
        # Test the build_url with invalid flags.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        options = dict(
            eventid="test_id", format="event_dat", catalog="Unknown")

        # Should throw and InvalidOptionValue exception because of the
        # catalog="Unknown" is not in the allowed values.
        self.assertRaises(InvalidOptionValue, client.build_url, **options)

    def test_event_identifier_delimiters_round_trip_as_one_value(self):
        client = ESMShakeMapConnector()
        event_id = "test&catalog=USGS=extra"

        url = client.build_url(eventid=event_id)
        parsed_options = parse_qs(urlsplit(url).query)

        self.assertEqual(parsed_options, {"eventid": [event_id]})
        self.assertIn("%26", url)
        self.assertIn("%3D", url)

    def test_valid_options_do_not_warn(self):
        client = ESMShakeMapConnector()

        with patch.object(logger, "warning") as warning:
            client.build_url(
                eventid="test_id",
                format="event_dat",
                catalog="ESM",
            )

        warning.assert_not_called()

    def test_query_options(self):
        # Test the get_supported_options method.
        client = ESMShakeMapConnector()
        options = client.get_supported_options()
        self.assertEqual(options, ['eventid', 'catalog', 'format', 'flag', 'encoding'])
