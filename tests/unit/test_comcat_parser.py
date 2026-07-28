# -*- coding: utf-8 -*-
"""
Deterministically verify the provider-specific USGS ComCat parser.

The tests cover preferred-product ordering, refusal to substitute alternate
content, parsing into the existing scientific models, preservation of native
units and uncertainty, and deliberate handling of optional provider values.
"""

import copy
import io
import json
import os
import unittest

from paramws.clients.services.feltreport_data import FeltReportIntensityData
from paramws.clients.services.shakemap_data import (
    ShakeMapComponentNode,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
)
from paramws.clients.services.usgs.comcat_parser import USGSComCatParser
from paramws.clients.services.usgs.exceptions import (
    DatasetNotAvailableError,
)


FIXTURE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "fixtures",
)


def fixture_bytes(filename):
    """Return one representative USGS fixture as bytes."""
    with open(os.path.join(FIXTURE_DIRECTORY, filename), "rb") as fixture:
        return fixture.read()


def fixture_json(filename):
    """Return one representative USGS fixture as a mutable JSON object."""
    return json.loads(fixture_bytes(filename))


def minimal_event(properties=None):
    """Build the required ComCat event structure around selected properties."""
    if properties is None:
        properties = {}
    return {
        "type": "Feature",
        "id": "event-one",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [1.0, 2.0, 3.0],
        },
    }


def minimal_station(properties=None):
    """Build one required station feature around selected properties."""
    station_properties = {
        "network": "NW",
        "code": "ONE",
        "station_type": "seismic",
    }
    if properties is not None:
        station_properties.update(properties)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [1.0, 2.0],
        },
        "properties": station_properties,
    }


def feature_collection(features):
    """Build a GeoJSON FeatureCollection with the supplied records."""
    return {
        "type": "FeatureCollection",
        "features": features,
    }


class TestUSGSComCatEventParser(unittest.TestCase):
    """Test detailed event parsing into the established event model."""

    def setUp(self):
        self.parser = USGSComCatParser()

    def test_text_bytes_and_file_like_event_inputs_are_supported(self):
        content = fixture_bytes("usgs-comcat-event-detail.json")
        inputs = (
            content.decode("utf-8"),
            content,
            io.BytesIO(content),
        )

        for supplied_data in inputs:
            with self.subTest(input_type=type(supplied_data).__name__):
                event = USGSComCatParser().parse_event_detail(supplied_data)
                self.assertIsInstance(event, ShakeMapEventData)
                self.assertEqual(event.get_event_id(), "ci38457511")

    def test_event_geometry_and_provider_properties_keep_native_meaning(self):
        event = self.parser.parse(
            fixture_bytes("usgs-comcat-event-detail.json"))

        self.assertEqual(event.get_longitude(), -117.5993333)
        self.assertEqual(event.get_latitude(), 35.7695)
        self.assertEqual(event.get_depth(), 8.0)
        self.assertEqual(event.get_magnitude(), 7.1)
        self.assertEqual(event.get_origin_time(), 1562383193040)
        self.assertEqual(
            event.get_place(),
            "2019 Ridgecrest Earthquake Sequence",
        )
        self.assertEqual(event.get_status(), "reviewed")
        self.assertEqual(event.get_contributor_network(), "ci")
        self.assertEqual(event.get_network_code(), "ci")
        self.assertEqual(event.get_contributor_code(), "38457511")
        self.assertEqual(event.get_contributor_sources(), ",ci,us,")
        self.assertEqual(
            event.get_loc_string(),
            "2019 Ridgecrest Earthquake Sequence",
        )
        self.assertEqual(event.get("tsunami"), 0)
        self.assertIsInstance(event.get_product_index(), dict)
        self.assertEqual(
            event.get_geometry(),
            {
                "type": "Point",
                "coordinates": [-117.5993333, 35.7695, 8.0],
            },
        )

    def test_optional_falsey_empty_and_null_event_values_are_preserved(self):
        event_json = minimal_event({
            "mag": "0.0",
            "time": 0,
            "place": "",
            "alert": None,
            "reviewed": False,
            "products": {},
        })

        event = self.parser.parse_event_detail(event_json)

        self.assertEqual(event.get_magnitude(), "0.0")
        self.assertEqual(event.get_origin_time(), 0)
        self.assertEqual(event.get_place(), "")
        self.assertIsNone(event.get("alert"))
        self.assertIs(event.get("reviewed"), False)
        self.assertEqual(event.get_product_index(), {})

    def test_event_without_product_index_remains_valid(self):
        event = self.parser.parse_event_detail(minimal_event({"mag": None}))

        self.assertIsInstance(event, ShakeMapEventData)
        self.assertIsNone(event.get_product_index())
        with self.assertRaisesRegex(
                DatasetNotAvailableError, "shakemap"):
            self.parser.select_product_content(event, "shakemap")

    def test_omitted_and_empty_usgs_event_fields_keep_optional_boundary(self):
        event = self.parser.parse_event_detail(minimal_event({"place": ""}))

        self.assertEqual(event.get_place(), "")
        self.assertIsNone(event.get_status())
        self.assertIsNone(event.get_contributor_network())
        self.assertIsNone(event.get_contributor_code())
        self.assertIsNone(event.get_contributor_sources())
        self.assertIsNone(event.get_product_index())

    def test_malformed_json_and_required_event_structure_are_rejected(self):
        malformed_cases = (
            "{",
            [],
            {"type": "Feature", "properties": {}, "geometry": None},
            minimal_event(properties=[]),
            {
                "type": "Feature",
                "id": "",
                "properties": {},
                "geometry": {
                    "type": "Point",
                    "coordinates": [1, 2, 3],
                },
            },
            {
                "type": "Feature",
                "id": "event-one",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [1, 2, 3],
                },
            },
        )
        for supplied_data in malformed_cases:
            with self.subTest(supplied_data=supplied_data):
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*single-event GeoJSON Feature"):
                    self.parser.parse_event_detail(supplied_data)

    def test_malformed_non_empty_event_scientific_values_are_rejected(self):
        for field_name in ("mag", "time"):
            with self.subTest(field_name=field_name):
                event_json = minimal_event({field_name: "not-numeric"})
                with self.assertRaisesRegex(
                        ValueError, "USGS/ComCat.*" + field_name):
                    self.parser.parse_event_detail(event_json)


class TestUSGSComCatProductSelection(unittest.TestCase):
    """Test deterministic preferred-product and exact-content selection."""

    def setUp(self):
        self.parser = USGSComCatParser()
        self.event_json = fixture_json("usgs-comcat-event-detail.json")

    def _parsed_event(self):
        return self.parser.parse_event_detail(self.event_json)

    def test_greatest_preferred_weight_wins_over_newer_update(self):
        products = self.event_json["properties"]["products"]["shakemap"]
        products[0]["preferredWeight"] = 10
        products[0]["updateTime"] = 1
        products[1]["preferredWeight"] = 9
        products[1]["updateTime"] = 9999999999999
        del products[2]

        selected_url = self.parser.select_product_content(
            self._parsed_event(), "shakemap")

        self.assertIn("/us/1750000000000/", selected_url)

    def test_newest_update_time_breaks_equal_weight_tie(self):
        products = self.event_json["properties"]["products"]["shakemap"]
        products[0]["preferredWeight"] = 6
        products[0]["updateTime"] = 1760000000001
        products[1]["preferredWeight"] = 6
        products[1]["updateTime"] = 1760000000000
        del products[2]

        selected_url = self.parser.select_product_content(
            self._parsed_event(), "shakemap")

        self.assertIn("/us/1750000000000/", selected_url)

    def test_status_is_applied_only_after_preference_selection(self):
        products = self.event_json["properties"]["products"]["shakemap"]
        products[0]["status"] = "DELETE"
        products[0]["preferredWeight"] = 5
        products[2]["preferredWeight"] = 6

        selected_url = self.parser.select_product_content(
            self._parsed_event(), "shakemap")

        self.assertIn("/atlas/1760000000000/", selected_url)

    def test_deleted_preferred_product_raises_without_fallback_url(self):
        products = self.event_json["properties"]["products"]["shakemap"]
        products[2]["status"] = "DELETE"

        with self.assertRaisesRegex(
                DatasetNotAvailableError, "shakemap.*deleted"):
            self.parser.select_product_content(
                self._parsed_event(), "shakemap")

    def test_missing_requested_product_names_the_dataset(self):
        del self.event_json["properties"]["products"]["dyfi"]

        with self.assertRaisesRegex(DatasetNotAvailableError, "dyfi"):
            self.parser.select_product_content(self._parsed_event(), "dyfi")

    def test_missing_exact_content_does_not_use_alternate_or_older_content(self):
        preferred = (
            self.event_json["properties"]["products"]["shakemap"][2]
        )
        preferred["contents"] = {
            "download/stationlist.xml": {
                "url": "https://example.test/preferred/stationlist.xml",
            }
        }

        with self.assertRaisesRegex(
                DatasetNotAvailableError,
                "shakemap.*download/stationlist.json"):
            self.parser.select_product_content(
                self._parsed_event(), "shakemap")

    def test_dyfi_requires_one_kilometre_content_without_ten_kilometre_fallback(
            self):
        dyfi = self.event_json["properties"]["products"]["dyfi"][0]
        del dyfi["contents"]["dyfi_geo_1km.geojson"]

        with self.assertRaisesRegex(
                DatasetNotAvailableError,
                "dyfi.*dyfi_geo_1km.geojson"):
            self.parser.select_product_content(self._parsed_event(), "dyfi")

    def test_discovered_exact_urls_are_returned_unchanged(self):
        event = self._parsed_event()

        self.assertEqual(
            self.parser.select_product_content(event, "shakemap"),
            "https://earthquake.usgs.gov/product/shakemap/"
            "ci38457511/atlas/1760000000000/download/stationlist.json",
        )
        self.assertEqual(
            self.parser.select_product_content(event, "dyfi"),
            "https://earthquake.usgs.gov/product/dyfi/"
            "ci38457511/us/1760000001000/dyfi_geo_1km.geojson",
        )

    def test_malformed_preference_values_are_not_reported_as_absence(self):
        products = self.event_json["properties"]["products"]["shakemap"]
        cases = (
            ("preferredWeight", None),
            ("preferredWeight", "6"),
            ("updateTime", False),
            ("updateTime", "newest"),
        )
        for field_name, malformed_value in cases:
            with self.subTest(
                    field_name=field_name,
                    malformed_value=malformed_value):
                event_json = copy.deepcopy(self.event_json)
                candidate = (
                    event_json["properties"]["products"]["shakemap"][0]
                )
                candidate[field_name] = malformed_value
                event = self.parser.parse_event_detail(event_json)
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*preferred-product metadata.*"
                        + field_name):
                    self.parser.select_product_content(event, "shakemap")

    def test_missing_preference_field_is_malformed_selection_metadata(self):
        candidate = (
            self.event_json["properties"]["products"]["shakemap"][0]
        )
        del candidate["preferredWeight"]

        with self.assertRaisesRegex(
                ValueError,
                "USGS/ComCat.*preferred-product metadata.*preferredWeight"):
            self.parser.select_product_content(
                self._parsed_event(), "shakemap")

    def test_malformed_selected_content_metadata_is_not_simple_absence(self):
        preferred = (
            self.event_json["properties"]["products"]["shakemap"][2]
        )
        preferred["contents"]["download/stationlist.json"] = "not-an-object"

        with self.assertRaisesRegex(
                ValueError,
                "USGS/ComCat.*preferred-product metadata.*Content metadata"):
            self.parser.select_product_content(
                self._parsed_event(), "shakemap")


class TestUSGSShakeMapStationListParser(unittest.TestCase):
    """Test exact ShakeMap station-list parsing into existing model types."""

    def setUp(self):
        self.parser = USGSComCatParser()

    def test_seismic_station_components_preserve_measurement_metadata(self):
        data = self.parser.parse_shakemap_station_list(
            fixture_bytes("usgs-shakemap-stationlist.json"))

        self.assertIsInstance(data, ShakeMapStationAmplitudes)
        self.assertEqual(len(data.get_stations()), 2)
        station = data.get_stations()[0]
        self.assertIsInstance(station, ShakeMapStationNode)
        self.assertEqual(station.get_station_id(), "CI.CLC")
        self.assertEqual(station.get_station_type(), "seismic")
        self.assertEqual(station.get_geometry()["type"], "Point")
        self.assertEqual(station.get_longitude(), -117.59751)
        self.assertEqual(station.get_latitude(), 35.81574)
        self.assertEqual(station.get_intensity(), 7.1)
        self.assertEqual(station.get_intensity_uncertainty(), 0.32)
        self.assertIsNone(station.get_response_count())
        self.assertEqual(station.get_distance(), 5.18)
        self.assertIs(station.get("predicted"), False)
        self.assertEqual(len(station.get_components()), 2)

        component = station.get_components()[0]
        self.assertIsInstance(component, ShakeMapComponentNode)
        self.assertEqual(component.get_component_name(), "--.HNZ")
        self.assertEqual(component.get_acceleration(), 75.4)
        self.assertEqual(component.get_acceleration_units(), "%g")
        self.assertEqual(component.get_acceleration_flag(), "0")
        self.assertEqual(component.get_acceleration_uncertainty(), 0.12)
        self.assertEqual(component.get_velocity(), 58.2)
        self.assertEqual(component.get_velocity_units(), "cm/s")
        self.assertEqual(component.get_velocity_flag(), "0")
        self.assertEqual(component.get_velocity_uncertainty(), 0.15)
        self.assertEqual(component.get_psa03(), 138.8)
        self.assertEqual(component.get_psa03_units(), "%g")
        self.assertEqual(component.get_psa03_uncertainty(), 0.18)
        self.assertEqual(component.get_psa10(), 96.1)
        self.assertEqual(component.get_psa10_units(), "%g")
        self.assertEqual(component.get_psa10_uncertainty(), 0.2)
        self.assertEqual(component.get_psa30(), 41.7)
        self.assertEqual(component.get_psa30_units(), "%g")
        self.assertEqual(component.get_psa30_uncertainty(), 0.24)

    def test_macroseismic_station_without_components_keeps_native_fields(self):
        data = self.parser.parse_shakemap_station_list(
            fixture_bytes("usgs-shakemap-stationlist.json"))
        station = data.get_stations()[1]

        self.assertIsInstance(station, ShakeMapStationNode)
        self.assertEqual(station.get_station_id(), "DYFI.91052")
        self.assertEqual(station.get_station_type(), "macroseismic")
        self.assertEqual(station.get_components(), [])
        self.assertEqual(station.get_intensity(), 7.4)
        self.assertEqual(station.get_intensity_uncertainty(), 0.58)
        self.assertEqual(station.get_response_count(), 139)
        self.assertEqual(station.get_distance(), 1.1)
        self.assertEqual(station.get("pga"), "null")
        self.assertEqual(station.get("pgv"), "")
        self.assertIs(station.get("predicted"), False)

    def test_singleton_station_and_file_like_input_remain_a_list(self):
        fixture = fixture_json("usgs-shakemap-stationlist.json")
        fixture["features"] = fixture["features"][:1]
        content = json.dumps(fixture).encode("utf-8")

        data = self.parser.parse_shakemap_station_list(io.BytesIO(content))

        self.assertEqual(len(data.get_stations()), 1)
        self.assertIsInstance(data.get_stations()[0], ShakeMapStationNode)
        self.assertEqual(len(data.get_stations()[0].get_components()), 2)

    def test_missing_optional_station_metadata_and_channels_are_allowed(self):
        station = minimal_station({
            "name": "",
            "intensity": None,
            "intensity_stddev": "null",
            "nresp": "0",
            "distance": "",
            "channels": None,
        })

        parsed = self.parser.parse_shakemap_station_list(
            feature_collection([station])).get_stations()[0]

        self.assertEqual(parsed.get_station_name(), "")
        self.assertIsNone(parsed.get_intensity())
        self.assertEqual(parsed.get_intensity_uncertainty(), "null")
        self.assertEqual(parsed.get_response_count(), "0")
        self.assertEqual(parsed.get_distance(), "")
        self.assertEqual(parsed.get_components(), [])

    def test_zero_false_empty_and_null_measurement_metadata_is_preserved(self):
        station = minimal_station({
            "channels": [{
                "name": "HNZ",
                "amplitudes": [{
                    "name": "pga",
                    "value": 0,
                    "units": "",
                    "flag": False,
                    "ln_sigma": None,
                }],
            }],
        })

        component = self.parser.parse_shakemap_station_list(
            feature_collection([station])
        ).get_stations()[0].get_components()[0]

        self.assertEqual(component.get_acceleration(), 0)
        self.assertEqual(component.get_acceleration_units(), "")
        self.assertIs(component.get_acceleration_flag(), False)
        self.assertIsNone(component.get_acceleration_uncertainty())

    def test_missing_usgs_measurement_and_station_metadata_returns_none(self):
        station = minimal_station({
            "name": "",
            "channels": [{
                "name": "HNZ",
                "amplitudes": [{
                    "name": "pga",
                    "value": 1.25,
                }],
            }],
        })

        parsed_station = self.parser.parse_shakemap_station_list(
            feature_collection([station])).get_stations()[0]
        component = parsed_station.get_components()[0]

        self.assertEqual(component.get_acceleration(), 1.25)
        self.assertIsNone(component.get_acceleration_units())
        self.assertIsNone(component.get_acceleration_uncertainty())
        self.assertIsNone(parsed_station.get_intensity())
        self.assertIsNone(parsed_station.get_intensity_uncertainty())
        self.assertIsNone(parsed_station.get_response_count())
        self.assertIsNone(parsed_station.get_distance())
        self.assertEqual(parsed_station.get_station_name(), "")

    def test_empty_station_collection_is_valid_provider_content(self):
        data = self.parser.parse_shakemap_station_list(feature_collection([]))

        self.assertIsInstance(data, ShakeMapStationAmplitudes)
        self.assertEqual(data.get_stations(), [])

    def test_malformed_station_json_and_required_structure_are_rejected(self):
        malformed_cases = (
            "{",
            {},
            {"type": "FeatureCollection"},
            feature_collection([{}]),
            feature_collection([minimal_station({"network": ""})]),
            feature_collection([minimal_station({"station_type": None})]),
        )
        for supplied_data in malformed_cases:
            with self.subTest(supplied_data=supplied_data):
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*stationlist.json"):
                    self.parser.parse_shakemap_station_list(supplied_data)

    def test_malformed_non_empty_station_scientific_values_are_rejected(self):
        cases = (
            minimal_station({"intensity": "strong"}),
            minimal_station({
                "channels": [{
                    "name": "HNZ",
                    "amplitudes": [{
                        "name": "pga",
                        "value": "large",
                    }],
                }],
            }),
            minimal_station({
                "channels": [{
                    "name": "HNZ",
                    "amplitudes": [{
                        "name": "pga",
                        "value": 1.0,
                        "ln_sigma": "wide",
                    }],
                }],
            }),
        )
        for station in cases:
            with self.subTest(station=station):
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*stationlist.json.*Scientific"):
                    self.parser.parse_shakemap_station_list(
                        feature_collection([station]))


class TestUSGSDYFIParser(unittest.TestCase):
    """Test exact 1 km DYFI parsing into existing felt-intensity data."""

    def setUp(self):
        self.parser = USGSComCatParser()

    def test_features_preserve_complete_geometry_and_supplied_properties(self):
        fixture = fixture_json("usgs-dyfi-1km.geojson")
        data = self.parser.parse_dyfi_1km(
            fixture_bytes("usgs-dyfi-1km.geojson"))

        self.assertIsInstance(data, FeltReportIntensityData)
        self.assertEqual(data.get("bbox"), fixture["bbox"])
        self.assertEqual(len(data.get_intensities()), 2)
        intensity = data.get_intensities()[0]
        self.assertEqual(intensity["cdi"], 7.4)
        self.assertEqual(intensity["stddev"], 0.0)
        self.assertEqual(intensity["nresp"], 1)
        self.assertEqual(intensity["name"], "Ridgecrest, CA")
        self.assertEqual(intensity["dist"], 0.0)
        self.assertEqual(
            intensity["geometry"],
            fixture["features"][0]["geometry"],
        )
        self.assertEqual(intensity["geometry"]["type"], "Polygon")
        self.assertEqual(intensity["id"], "91052-1")

    def test_singleton_dyfi_feature_and_file_like_input_remain_a_list(self):
        fixture = fixture_json("usgs-dyfi-1km.geojson")
        fixture["features"] = fixture["features"][:1]
        content = json.dumps(fixture).encode("utf-8")

        data = self.parser.parse_dyfi_1km(io.BytesIO(content))

        self.assertEqual(len(data.get_intensities()), 1)
        self.assertEqual(data.get_intensities()[0]["name"], "Ridgecrest, CA")

    def test_optional_absent_empty_null_and_zero_values_are_preserved(self):
        feature = {
            "type": "Feature",
            "properties": {
                "cdi": None,
                "stddev": "",
                "nresp": "0",
                "name": "",
                "dist": 0,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [0, 0]]],
            },
        }

        intensity = self.parser.parse_dyfi_1km(
            feature_collection([feature])).get_intensities()[0]

        self.assertIsNone(intensity["cdi"])
        self.assertEqual(intensity["stddev"], "")
        self.assertEqual(intensity["nresp"], "0")
        self.assertEqual(intensity["name"], "")
        self.assertEqual(intensity["dist"], 0)

    def test_optional_scientific_properties_may_be_absent(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [0, 0]]],
            },
        }

        intensity = self.parser.parse_dyfi_1km(
            feature_collection([feature])).get_intensities()[0]

        self.assertEqual(
            intensity,
            {
                "geometry": feature["geometry"],
                "feature_type": "Feature",
            },
        )

    def test_empty_dyfi_collection_is_valid_provider_content(self):
        data = self.parser.parse_dyfi_1km(feature_collection([]))

        self.assertIsInstance(data, FeltReportIntensityData)
        self.assertEqual(data.get_intensities(), [])

    def test_malformed_dyfi_json_and_required_structure_are_rejected(self):
        malformed_cases = (
            "{",
            {},
            {"type": "FeatureCollection"},
            feature_collection([{}]),
            feature_collection([{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "",
                    "coordinates": [],
                },
            }]),
            feature_collection([{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, "east"], [1, 0], [0, 0]]],
                },
            }]),
        )
        for supplied_data in malformed_cases:
            with self.subTest(supplied_data=supplied_data):
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*dyfi_geo_1km.geojson"):
                    self.parser.parse_dyfi_1km(supplied_data)

    def test_malformed_non_empty_dyfi_scientific_values_are_rejected(self):
        for field_name in ("cdi", "stddev", "nresp", "dist"):
            with self.subTest(field_name=field_name):
                feature = {
                    "type": "Feature",
                    "properties": {field_name: "malformed"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [0, 0]]],
                    },
                }
                with self.assertRaisesRegex(
                        ValueError,
                        "USGS/ComCat.*dyfi_geo_1km.geojson.*"
                        + field_name):
                    self.parser.parse_dyfi_1km(
                        feature_collection([feature]))


if __name__ == "__main__":
    unittest.main()
