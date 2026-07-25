# -*- coding: utf-8 -*-
import unittest
from paramws.clients import RRSMShakeMapClient
    
class TestRRSMClient(unittest.TestCase):
    def test_default_contructor(self):
        # Test the constructor with default values. 
        client = RRSMShakeMapClient()
        
        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), 
                         "http://orfeus-eu.org/odcws/rrsm/")

    def test_set_url_attributes(self):
        # Test the parts of the query url. 
        client = RRSMShakeMapClient()
        client.set_agency("ORFEUS")
        client.set_version("1")
        client.set_end_point("shakemap")
        client.set_base_url("http://orfeus-eu.org/odcws/rrsm/")
        self.assertEqual(client.get_agency(), "ORFEUS")
        self.assertEqual(client.get_version(), "1")
        self.assertEqual(client.get_end_point(), "shakemap")
        self.assertEqual(client.get_base_url(), 
                         "http://orfeus-eu.org/odcws/rrsm/")

    def test_query_null_event_id(self):
        # Test the query method. 
        client = RRSMShakeMapClient()
        self.assertRaises(ValueError, client.query, event_id=None)
    