# -*- coding: utf-8 -*-
"""Unit tests for the ESM ShakeMap connector."""
import unittest
from paramws.clients.services import InvalidOptionValue
from paramws.clients.services import ESMShakeMapConnector

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
        # Test the build_url with invalid flags.
        client = ESMShakeMapConnector()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        options = dict(eventid="test_id", format="event_dat", 
                       catalog="ESM", uknown_flag="not_a_valid_value")
        
        # build_url does an internal clean-up for invalid options.
        # So, the uknown_flag should be removed from the url. An 
        # InvalidQueryOption exception will be raised if something 
        # goes wrong with the clean-up at the end.
        url = client.build_url(**options)
       
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
    

    def test_query_options(self):
        # Test the get_supported_options method.
        client = ESMShakeMapConnector()
        options = client.get_supported_options()
        self.assertEqual(options, ['eventid', 'catalog', 'format', 'flag', 'encoding'])
