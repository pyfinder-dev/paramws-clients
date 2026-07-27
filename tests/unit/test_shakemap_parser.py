# -*- coding: utf-8 -*-
import datetime
import os
import unittest

from paramws.clients.services.esm.shakemap_parser import ESMShakeMapParser
from paramws.clients.services.rrsm.shakemap_parser import RRSMShakeMapParser
from paramws.clients.services.shakemap_data import ShakeMapComponentNode
from paramws.clients.services.shakemap_data import ShakeMapEventData
from paramws.clients.services.shakemap_data import ShakeMapStationAmplitudes
from paramws.clients.services.shakemap_data import ShakeMapStationNode


module_path = os.path.dirname(os.path.abspath(__file__))


class TestESMShakeMapParser(unittest.TestCase):
    """Test the parser for the ESM ShakeMap web service."""

    def test_event_response_uses_established_model_and_numeric_types(self):
        xml_path = os.path.join(
            module_path, '..', 'fixtures', 'esmws-event.xml')
        with open(xml_path, 'r') as xmlfile:
            eq_data = ESMShakeMapParser().parse_earthquake(xmlfile.read())

        self.assertIsInstance(eq_data, ShakeMapEventData)
        self.assertEqual(eq_data['id'], '20170524_0000045')
        self.assertAlmostEqual(eq_data['lat'], 41.422832)
        self.assertAlmostEqual(eq_data['lon'], 20.155666)
        self.assertAlmostEqual(eq_data['depth'], 9.28)
        self.assertAlmostEqual(eq_data['mag'], 4.5)
        self.assertEqual(eq_data['year'], 2017)
        self.assertEqual(eq_data['time'], '2017-05-24T10:30:59Z')

    def test_multiple_station_and_component_records_are_preserved(self):
        xml_path = os.path.join(
            module_path, '..', 'fixtures', 'esmws-eventdata.xml')
        with open(xml_path, 'r') as xmlfile:
            shakemap_data = ESMShakeMapParser().parse(xmlfile.read())

        self.assertIsInstance(shakemap_data, ShakeMapStationAmplitudes)
        self.assertEqual(
            [station.get_station_id()
             for station in shakemap_data.get_stations()],
            ['HI.KRK1', 'HI.LMS2', 'HL.JAN', 'HL.KASA'],
        )
        station = shakemap_data.get_stations()[0]
        self.assertIsInstance(station, ShakeMapStationNode)
        self.assertEqual(len(station.get_components()), 3)
        expected_components = {
            ".HNE": {
                "acc": 0.016794504,
                "vel": 0.008192,
                "psa03": 0.0394178840307,
                "psa10": 0.00614489465695,
                "psa30": 0.00123846427919,
            },
            ".HNN": {
                "acc": 0.016320204,
                "vel": 0.008136,
                "psa03": 0.0418339631881,
                "psa10": 0.007030790348,
                "psa30": 0.000478741610816,
            },
            ".HNZ": {
                "acc": 0.018035436,
                "vel": 0.002963,
                "psa03": 0.0272927460371,
                "psa10": 0.00361203834029,
                "psa30": 0.000409391190557,
            },
        }
        visited_components = set()
        for component in station.get_components():
            self.assertIsInstance(component, ShakeMapComponentNode)
            component_name = component.get_component_name()
            visited_components.add(component_name)
            expected = expected_components[component_name]
            for field_name, expected_value in expected.items():
                self.assertAlmostEqual(
                    component.get(field_name),
                    expected_value,
                )
                self.assertEqual(component.get(field_name + "flag"), "0")
            self.assertEqual(component.get_component_depth(), 0.0)
        self.assertEqual(visited_components, set(expected_components))

    def test_singleton_station_and_component_are_normalized_to_lists(self):
        xml = """
        <stationlist created="1685534294">
          <station code="ONE" netid="NW">
            <comp name="HNZ" depth="1.5">
              <acc value="0.25" flag="1"/>
            </comp>
          </station>
        </stationlist>
        """

        data = ESMShakeMapParser().parse(xml)

        self.assertEqual(len(data.get_stations()), 1)
        station = data.get_stations()[0]
        self.assertEqual(station.get_station_id(), "NW.ONE")
        self.assertEqual(len(station.get_components()), 1)
        component = station.get_components()[0]
        self.assertEqual(component.get_component_name(), "HNZ")
        self.assertEqual(component.get_component_depth(), 1.5)
        self.assertEqual(component.get_acceleration(), 0.25)
        self.assertEqual(component.get_acceleration_flag(), "1")
        self.assertIsNone(component.get_velocity())

    def test_optional_station_fields_and_components_may_be_absent(self):
        xml = """
        <stationlist created="1685534294">
          <station code="ONE" netid="NW"/>
        </stationlist>
        """

        station = ESMShakeMapParser().parse(xml).get_stations()[0]

        self.assertEqual(station.get_station_id(), "NW.ONE")
        self.assertIsNone(station.get_station_name())
        self.assertIsNone(station.get_latitude())
        self.assertIsNone(station.get_longitude())
        self.assertEqual(station.get_components(), [])

    def test_optional_creation_time_and_zero_timestamp_are_preserved(self):
        optional_creation_attributes = ("", ' created=""', ' created="   "')
        for creation_attribute in optional_creation_attributes:
            with self.subTest(creation_attribute=creation_attribute):
                xml = (
                    "<stationlist{}>"
                    '<station code="ONE" netid="NW"/>'
                    "</stationlist>"
                ).format(creation_attribute)

                data = ESMShakeMapParser().parse(xml)

                self.assertIsNone(data.get_creation_time())
                self.assertEqual(data.get_station_codes(), ["ONE"])

        zero_timestamp_xml = (
            '<stationlist created="0">'
            '<station code="ONE" netid="NW"/>'
            "</stationlist>"
        )
        data = ESMShakeMapParser().parse(zero_timestamp_xml)

        self.assertEqual(
            data.get_creation_time(),
            datetime.datetime.fromtimestamp(0),
        )
        self.assertEqual(data.get_station_codes(), ["ONE"])

    def test_malformed_and_incompatible_xml_are_rejected(self):
        cases = (
            ("<stationlist>", "station-amplitude XML"),
            ("<earthquake/>", "station-amplitude XML"),
        )
        for xml, expected in cases:
            with self.subTest(xml=xml):
                with self.assertRaisesRegex(ValueError, "ESM.*" + expected):
                    ESMShakeMapParser().parse(xml)

        event_cases = ("<earthquake>", "<stationlist/>")
        for xml in event_cases:
            with self.subTest(xml=xml):
                with self.assertRaisesRegex(
                        ValueError, "ESM.*ShakeMap event XML"):
                    ESMShakeMapParser().parse_earthquake(xml)

    def test_missing_required_record_identity_fields_are_rejected(self):
        station_cases = (
            '<station code="ONE"/>',
            '<station netid="NW"/>',
            '<station code="ONE" netid="NW"><comp depth="0"/></station>',
        )
        for station_xml in station_cases:
            with self.subTest(station_xml=station_xml):
                xml = (
                    '<stationlist created="1685534294">'
                    + station_xml
                    + '</stationlist>'
                )
                with self.assertRaisesRegex(
                        ValueError, "ESM.*station-amplitude XML"):
                    ESMShakeMapParser().parse(xml)

        event_without_id = (
            '<earthquake catalog="EMSC" lat="1" lon="2" depth="3" mag="4" '
            'year="2026" month="7" day="27" hour="1" minute="2" second="3"/>'
        )
        with self.assertRaisesRegex(ValueError, "ESM.*event XML.*@id"):
            ESMShakeMapParser().parse_earthquake(event_without_id)

    def test_missing_measurement_structure_is_rejected(self):
        xml = """
        <stationlist created="1685534294">
          <station code="ONE" netid="NW">
            <comp name="HNZ"><acc value="0.25"/></comp>
          </station>
        </stationlist>
        """

        with self.assertRaisesRegex(
                ValueError, "ESM.*station-amplitude XML.*@value and @flag"):
            ESMShakeMapParser().parse(xml)

    def test_malformed_required_numeric_values_are_rejected(self):
        malformed_event = (
            '<earthquake id="event-one" lat="north" lon="2" depth="3" '
            'mag="4" year="2026" month="7" day="27" hour="1" minute="2" '
            'second="3"/>'
        )
        with self.assertRaisesRegex(
                ValueError, "ESM.*event XML.*numeric.*@lat"):
            ESMShakeMapParser().parse_earthquake(malformed_event)

        malformed_component = """
        <stationlist created="1685534294">
          <station code="ONE" netid="NW">
            <comp name="HNZ"><acc value="high" flag="0"/></comp>
          </station>
        </stationlist>
        """
        with self.assertRaisesRegex(
                ValueError, "ESM.*station-amplitude XML.*numeric"):
            ESMShakeMapParser().parse(malformed_component)

    def test_invalid_provider_creation_timestamp_is_rejected(self):
        xml = """
        <stationlist created="not-a-timestamp">
          <station code="ONE" netid="NW"/>
        </stationlist>
        """

        with self.assertRaisesRegex(
                ValueError, "ESM.*creation timestamp.*not-a-timestamp"):
            ESMShakeMapParser().parse(xml)


class TestRRSMShakeMapParser(unittest.TestCase):
    """Test RRSM parsing through the shared ESM-compatible implementation."""

    def test_parser_retains_required_inheritance(self):
        self.assertTrue(issubclass(RRSMShakeMapParser, ESMShakeMapParser))

    def test_event_fixture_uses_established_model_and_numeric_types(self):
        xml_path = os.path.join(
            module_path, '..', 'fixtures', 'rrsm-shakemap-event.xml')
        with open(xml_path, 'r') as xmlfile:
            event_data = RRSMShakeMapParser().parse_earthquake(xmlfile.read())

        self.assertIsInstance(event_data, ShakeMapEventData)
        self.assertEqual(event_data.get_event_id(), "rrsm-event-one")
        self.assertAlmostEqual(event_data.get_latitude(), 38.742)
        self.assertAlmostEqual(event_data.get_longitude(), 20.615)
        self.assertAlmostEqual(event_data.get_depth(), 12.4)
        self.assertAlmostEqual(event_data.get_magnitude(), 4.8)
        self.assertEqual(event_data["year"], 2026)
        self.assertEqual(event_data.get_network_code(), "ORFEUS")

    def test_multiple_station_and_component_records_preserve_string_flags(self):
        xml_path = os.path.join(
            module_path, '..', 'fixtures', 'rrsm-shakemap-stations.xml')
        with open(xml_path, 'r') as xmlfile:
            station_data = RRSMShakeMapParser().parse(xmlfile.read())

        self.assertIsInstance(station_data, ShakeMapStationAmplitudes)
        self.assertEqual(station_data.get_station_codes(), ["AAA", "BBB"])
        first_station = station_data.get_stations()[0]
        self.assertIsInstance(first_station, ShakeMapStationNode)
        self.assertEqual(first_station.get_station_id(), "NW.AAA")
        self.assertEqual(len(first_station.get_components()), 2)
        first_component = first_station.get_components()[0]
        self.assertIsInstance(first_component, ShakeMapComponentNode)
        self.assertEqual(first_component.get_component_name(), "HNZ")
        self.assertAlmostEqual(first_component.get_acceleration(), 0.125)
        self.assertEqual(first_component.get_acceleration_flag(), "0")
        self.assertAlmostEqual(first_component.get_velocity(), 0.045)
        self.assertEqual(first_component.get_velocity_flag(), "1")

    def test_singleton_station_and_component_are_normalized_to_lists(self):
        xml = """
        <stationlist created="1785057300">
          <station code="ONE" netid="NW">
            <comp name="HNZ" depth="1.5">
              <acc value="0.25" flag="1"/>
            </comp>
          </station>
        </stationlist>
        """

        station_data = RRSMShakeMapParser().parse(xml)

        self.assertEqual(len(station_data.get_stations()), 1)
        station = station_data.get_stations()[0]
        self.assertEqual(station.get_station_id(), "NW.ONE")
        self.assertEqual(len(station.get_components()), 1)
        component = station.get_components()[0]
        self.assertEqual(component.get_component_name(), "HNZ")
        self.assertEqual(component.get_component_depth(), 1.5)
        self.assertEqual(component.get_acceleration(), 0.25)
        self.assertEqual(component.get_acceleration_flag(), "1")

    def test_blank_creation_time_preserves_rrsm_station_data(self):
        xml = """
        <stationlist created="" xmlns="ch.ethz.sed.shakemap.usgs.xml">
          <station code="ONE" netid="NW">
            <comp name="HNZ" depth="0">
              <acc value="0.25" flag="0"/>
            </comp>
          </station>
        </stationlist>
        """

        station_data = RRSMShakeMapParser().parse(xml)

        self.assertIsNone(station_data.get_creation_time())
        self.assertEqual(station_data.get_station_codes(), ["ONE"])
        component = station_data.get_stations()[0].get_components()[0]
        self.assertEqual(component.get_component_name(), "HNZ")
        self.assertEqual(component.get_acceleration(), 0.25)
        self.assertEqual(component.get_acceleration_flag(), "0")

    def test_missing_required_fields_use_rrsm_provider_diagnostics(self):
        station_cases = (
            '<station code="ONE"/>',
            '<station netid="NW"/>',
            '<station code="ONE" netid="NW"><comp depth="0"/></station>',
        )
        for station_xml in station_cases:
            with self.subTest(station_xml=station_xml):
                xml = (
                    '<stationlist created="1785057300">'
                    + station_xml
                    + '</stationlist>'
                )
                with self.assertRaisesRegex(
                        ValueError,
                        "RRSM/ORFEUS.*station-amplitude XML"):
                    RRSMShakeMapParser().parse(xml)

        event_without_id = (
            '<earthquake lat="1" lon="2" depth="3" mag="4" year="2026" '
            'month="7" day="27" hour="1" minute="2" second="3"/>'
        )
        with self.assertRaisesRegex(
                ValueError, "RRSM/ORFEUS.*event XML.*@id"):
            RRSMShakeMapParser().parse_earthquake(event_without_id)

    def test_malformed_numeric_values_use_rrsm_provider_diagnostics(self):
        malformed_event = (
            '<earthquake id="rrsm-event-one" lat="north" lon="2" depth="3" '
            'mag="4" year="2026" month="7" day="27" hour="1" minute="2" '
            'second="3"/>'
        )
        with self.assertRaisesRegex(
                ValueError, "RRSM/ORFEUS.*event XML.*numeric.*@lat"):
            RRSMShakeMapParser().parse_earthquake(malformed_event)

        malformed_component = """
        <stationlist created="1785057300">
          <station code="ONE" netid="NW">
            <comp name="HNZ"><acc value="high" flag="0"/></comp>
          </station>
        </stationlist>
        """
        with self.assertRaisesRegex(
                ValueError,
                "RRSM/ORFEUS.*station-amplitude XML.*numeric"):
            RRSMShakeMapParser().parse(malformed_component)

    def test_malformed_and_incompatible_xml_identify_rrsm_expected_content(self):
        self.assertFalse(RRSMShakeMapParser().validate("<stationlist>"))

        station_cases = ("<stationlist>", "<earthquake/>")
        for xml in station_cases:
            with self.subTest(xml=xml):
                with self.assertRaisesRegex(
                        ValueError,
                        "RRSM/ORFEUS.*station-amplitude XML") as raised:
                    RRSMShakeMapParser().parse(xml)
                self.assertNotIn("ESM", str(raised.exception))

        event_cases = ("<earthquake>", "<stationlist/>")
        for xml in event_cases:
            with self.subTest(xml=xml):
                with self.assertRaisesRegex(
                        ValueError,
                        "RRSM/ORFEUS.*ShakeMap event XML") as raised:
                    RRSMShakeMapParser().parse_earthquake(xml)
                self.assertNotIn("ESM", str(raised.exception))

    def test_invalid_provider_creation_timestamp_is_rejected(self):
        xml = """
        <stationlist created="not-a-timestamp">
          <station code="ONE" netid="NW"/>
        </stationlist>
        """

        with self.assertRaisesRegex(
                ValueError,
                "RRSM/ORFEUS.*creation timestamp.*not-a-timestamp"):
            RRSMShakeMapParser().parse(xml)


if __name__ == "__main__":
    unittest.main()
