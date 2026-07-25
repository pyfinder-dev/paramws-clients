# -*- coding: utf-8 -*-
import unittest
from paramws.clients import ESMShakeMapClient
    
class TestESMClient(unittest.TestCase):
    def test_default_contructor(self):
        # Test the constructor with default values. 
        client = ESMShakeMapClient()
        
        self.assertEqual(client.get_agency(), "ESM")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), "https://esm-db.eu/esmws/")

    def test_set_url_attributes(self):
        # Test the parts of the query url. 
        client = ESMShakeMapClient()
        client.set_agency("ESM")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("https://esm-db.eu/esmws")
        self.assertEqual(client.get_agency(), "ESM")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), "https://esm-db.eu/esmws/")

    def test_query_null_event_id(self):
        # Test the query method. 
        client = ESMShakeMapClient()
        self.assertRaises(ValueError, client.query, event_id=None)
