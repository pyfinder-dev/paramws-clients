# -*- coding: utf-8 -*-
"""Live public-client coverage for supported USGS ComCat products."""

import math
import unittest

from paramws.clients import (
    FeltReportIntensityData,
    ShakeMapComponentNode,
    ShakeMapEventData,
    ShakeMapStationAmplitudes,
    ShakeMapStationNode,
    USGSComCatClient,
)
from tests.live_result import require_live_result


EVENT_ID = "ci38457511"


def is_finite_native_number(value):
    """
    Return whether a provider-native scalar represents a finite number.

    ComCat occasionally represents optional scientific values as numeric text.
    Live tests preserve that representation instead of imposing conversion.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not isinstance(value, float) or math.isfinite(value)
    if isinstance(value, str) and value.strip():
        try:
            return math.isfinite(float(value))
        except ValueError:
            return False
    return False


class TestUSGSComCatClientLive(unittest.TestCase):
    """Validate ComCat selection and essential public-model invariants."""

    def assert_event_result(self, code, event_data, datasets, expected_keys,
                            operation):
        """Validate the public event result shared by all product selections."""
        context = "USGS ComCat {}".format(operation)
        self.assertEqual(code, 200, context)
        self.assertIs(type(event_data), ShakeMapEventData, context)
        self.assertEqual(event_data.get_event_id(), EVENT_ID, context)
        self.assertIsInstance(datasets, dict, context)
        self.assertEqual(set(datasets), set(expected_keys), context)

        geometry = event_data.get_geometry()
        self.assertIsInstance(
            geometry,
            dict,
            "{} missing event geometry".format(context),
        )
        self.assertEqual(geometry.get("type"), "Point", context)
        coordinates = geometry.get("coordinates")
        self.assertIsInstance(coordinates, list, context)
        self.assertGreaterEqual(len(coordinates), 3, context)
        self.assertTrue(
            all(is_finite_native_number(value)
                for value in coordinates[:3]),
            "{} has malformed event coordinates".format(context),
        )
        self.assertGreaterEqual(float(coordinates[1]), -90.0, context)
        self.assertLessEqual(float(coordinates[1]), 90.0, context)
        self.assertGreaterEqual(float(coordinates[0]), -180.0, context)
        self.assertLessEqual(float(coordinates[0]), 180.0, context)

    def assert_station_point(self, station, context):
        """Validate one complete ComCat ShakeMap station point."""
        self.assertIs(type(station), ShakeMapStationNode, context)
        self.assertIsInstance(station.get_station_id(), str, context)
        self.assertTrue(station.get_station_id().strip(), context)
        self.assertIsInstance(station.get_network_code(), str, context)
        self.assertTrue(station.get_network_code().strip(), context)
        self.assertIsInstance(station.get_station_code(), str, context)
        self.assertTrue(station.get_station_code().strip(), context)

        geometry = station.get_geometry()
        self.assertIsInstance(
            geometry,
            dict,
            "{} missing station geometry".format(context),
        )
        self.assertEqual(geometry.get("type"), "Point", context)
        coordinates = geometry.get("coordinates")
        self.assertIsInstance(coordinates, list, context)
        self.assertGreaterEqual(len(coordinates), 2, context)
        self.assertTrue(
            all(is_finite_native_number(value)
                for value in coordinates[:2]),
            "{} has malformed station coordinates".format(context),
        )
        self.assertGreaterEqual(float(coordinates[1]), -90.0, context)
        self.assertLessEqual(float(coordinates[1]), 90.0, context)
        self.assertGreaterEqual(float(coordinates[0]), -180.0, context)
        self.assertLessEqual(float(coordinates[0]), 180.0, context)

    def test_shakemap_only(self):
        code, event_data, datasets = require_live_result(
            "USGS ComCat",
            "shakemap",
            lambda: USGSComCatClient().query(
                event_id=EVENT_ID,
                producttype="shakemap",
            ),
        )
        context = "USGS ComCat shakemap"
        self.assert_event_result(
            code,
            event_data,
            datasets,
            {"shakemap"},
            "shakemap",
        )
        self.assertNotIn("dyfi", datasets, context)

        amplitudes = datasets["shakemap"]
        self.assertIs(type(amplitudes), ShakeMapStationAmplitudes, context)
        stations = amplitudes.get_stations()
        self.assertIsInstance(stations, list, context)
        self.assertTrue(stations, "{} returned no stations".format(context))
        for station in stations:
            self.assert_station_point(station, context)

        seismic_station = next(
            (
                station
                for station in stations
                if (
                    station.get_station_type() == "seismic"
                    and isinstance(station.get_components(), list)
                    and station.get_components()
                )
            ),
            None,
        )
        self.assertIsNotNone(
            seismic_station,
            "{} has no seismic station with components".format(context),
        )

        component = next(
            (
                item
                for item in seismic_station.get_components()
                if any(
                    value is not None
                    for value in (
                        item.get_acceleration(),
                        item.get_velocity(),
                        item.get_psa03(),
                        item.get_psa10(),
                        item.get_psa30(),
                    )
                )
            ),
            None,
        )
        self.assertIsNotNone(
            component,
            "{} has no supported supplied measurement".format(context),
        )
        self.assertIs(type(component), ShakeMapComponentNode, context)
        self.assertIsInstance(component.get_component_name(), str, context)
        self.assertTrue(component.get_component_name().strip(), context)

        measurement_groups = (
            (
                component.get_acceleration(),
                component.get_acceleration_units(),
                component.get_acceleration_flag(),
                component.get_acceleration_uncertainty(),
            ),
            (
                component.get_velocity(),
                component.get_velocity_units(),
                component.get_velocity_flag(),
                component.get_velocity_uncertainty(),
            ),
            (
                component.get_psa03(),
                component.get_psa03_units(),
                component.get_psa03_flag(),
                component.get_psa03_uncertainty(),
            ),
            (
                component.get_psa10(),
                component.get_psa10_units(),
                component.get_psa10_flag(),
                component.get_psa10_uncertainty(),
            ),
            (
                component.get_psa30(),
                component.get_psa30_units(),
                component.get_psa30_flag(),
                component.get_psa30_uncertainty(),
            ),
        )
        supplied_measurements = 0
        for measurement, units, flag, uncertainty in measurement_groups:
            if measurement is not None:
                supplied_measurements += 1
                self.assertTrue(
                    is_finite_native_number(measurement),
                    "{} has a malformed measurement".format(context),
                )
            if units is not None:
                self.assertIsInstance(
                    units,
                    (str, int, float),
                    "{} cannot represent native units".format(context),
                )
            if flag is not None:
                self.assertIsInstance(
                    flag,
                    (str, int, float, bool),
                    "{} cannot represent a native flag".format(context),
                )
            if uncertainty is not None:
                self.assertTrue(
                    is_finite_native_number(uncertainty),
                    "{} cannot represent native uncertainty".format(context),
                )
        self.assertGreater(supplied_measurements, 0, context)

    def test_dyfi_only(self):
        code, event_data, datasets = require_live_result(
            "USGS ComCat",
            "dyfi",
            lambda: USGSComCatClient().query(
                event_id=EVENT_ID,
                producttype="dyfi",
            ),
        )
        context = "USGS ComCat dyfi"
        self.assert_event_result(
            code,
            event_data,
            datasets,
            {"dyfi"},
            "dyfi",
        )
        self.assertNotIn("shakemap", datasets, context)

        intensity_data = datasets["dyfi"]
        self.assertIs(type(intensity_data), FeltReportIntensityData, context)
        intensities = intensity_data.get_intensities()
        self.assertIsInstance(intensities, list, context)
        self.assertTrue(
            intensities,
            "{} returned no intensity records".format(context),
        )

        for intensity in intensities:
            self.assertIsInstance(intensity, dict, context)
            geometry = intensity.get("geometry")
            self.assertIsInstance(
                geometry,
                dict,
                "{} intensity is missing geometry".format(context),
            )
            self.assertIn(
                geometry.get("type"),
                {"Polygon", "MultiPolygon"},
                context,
            )
            self.assertIsInstance(geometry.get("coordinates"), list, context)
            self.assertTrue(geometry["coordinates"], context)

        representative = next(
            (
                intensity
                for intensity in intensities
                if (
                    intensity.get("cdi") is not None
                    and intensity.get("nresp") is not None
                    and intensity.get("name") is not None
                    and intensity.get("dist") is not None
                )
            ),
            None,
        )
        self.assertIsNotNone(
            representative,
            "{} lacks essential provider intensity properties".format(
                context),
        )
        self.assertTrue(
            is_finite_native_number(representative["cdi"]),
            "{} has malformed cdi".format(context),
        )
        self.assertGreaterEqual(float(representative["cdi"]), 0.0, context)
        self.assertLessEqual(float(representative["cdi"]), 10.0, context)
        self.assertTrue(
            is_finite_native_number(representative["nresp"]),
            "{} has malformed nresp".format(context),
        )
        self.assertGreaterEqual(float(representative["nresp"]), 0.0, context)
        self.assertIsInstance(representative["name"], str, context)
        self.assertTrue(representative["name"].strip(), context)
        self.assertTrue(
            is_finite_native_number(representative["dist"]),
            "{} has malformed dist".format(context),
        )
        if representative.get("stddev") is not None:
            self.assertTrue(
                is_finite_native_number(representative["stddev"]),
                "{} has malformed stddev".format(context),
            )
            self.assertGreaterEqual(
                float(representative["stddev"]),
                0.0,
                context,
            )

    def test_omitted_producttype_returns_both(self):
        code, event_data, datasets = require_live_result(
            "USGS ComCat",
            "shakemap and dyfi",
            lambda: USGSComCatClient().query(event_id=EVENT_ID),
        )
        context = "USGS ComCat shakemap and dyfi"
        self.assert_event_result(
            code,
            event_data,
            datasets,
            {"shakemap", "dyfi"},
            "shakemap and dyfi",
        )

        shakemap = datasets["shakemap"]
        dyfi = datasets["dyfi"]
        self.assertIs(type(shakemap), ShakeMapStationAmplitudes, context)
        self.assertIs(type(dyfi), FeltReportIntensityData, context)
        self.assertIsInstance(shakemap.get_stations(), list, context)
        self.assertTrue(shakemap.get_stations(), context)
        self.assertIsInstance(dyfi.get_intensities(), list, context)
        self.assertTrue(dyfi.get_intensities(), context)


if __name__ == "__main__":
    unittest.main()
