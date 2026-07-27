# -*- coding: utf-8 -*-
import unittest

from paramws.clients.services.basedatastructure import BaseDataStructure
from paramws.clients.services.feltreport_data import FeltReportEventData
from paramws.utils.nested_get import nested_get


class TestBaseDataStructureSubscripts(unittest.TestCase):
    """Test dictionary-style and attribute access to stored data."""

    def test_missing_subscript_raises_key_error_for_empty_and_non_empty_data(self):
        for data in ({}, {"present": 1}):
            with self.subTest(data=data):
                with self.assertRaises(KeyError):
                    BaseDataStructure(data)["missing"]

    def test_subscript_inserts_into_empty_data(self):
        data = BaseDataStructure()

        data["new"] = 3

        self.assertEqual(data["new"], 3)

    def test_subscript_replaces_existing_value(self):
        data = BaseDataStructure({"value": 1})

        data["value"] = 2

        self.assertEqual(data["value"], 2)

    def test_subscript_deletes_existing_key(self):
        data = BaseDataStructure({"value": 1})

        del data["value"]

        self.assertNotIn("value", data.get_data())

    def test_deleting_missing_subscript_raises_key_error(self):
        for data in ({}, {"present": 1}):
            with self.subTest(data=data):
                with self.assertRaises(KeyError):
                    del BaseDataStructure(data)["missing"]

    def test_existing_data_key_supports_dot_access_and_assignment(self):
        data = BaseDataStructure({"value": 1})

        self.assertEqual(data.value, 1)
        data.value = 2

        self.assertEqual(data["value"], 2)

    def test_missing_attribute_names_the_requested_attribute(self):
        data = BaseDataStructure()

        with self.assertRaisesRegex(AttributeError, "actual_missing_name"):
            data.actual_missing_name

    def test_new_attribute_remains_an_object_attribute(self):
        data = BaseDataStructure()

        data.description = "metadata"

        self.assertEqual(data.description, "metadata")
        self.assertNotIn("description", data.get_data())


class TestNestedGet(unittest.TestCase):
    """Test explicit traversal of dictionaries and lists."""

    def setUp(self):
        self.data = {
            "features": [
                {"properties": {"time": 0, "enabled": False}},
                {"properties": {"time": 12, "label": ""}},
            ],
            "zero_float": 0.0,
        }

    def test_final_list_is_returned_intact(self):
        self.assertIs(nested_get(self.data, "features"), self.data["features"])

    def test_bracket_index_returns_explicitly_selected_item(self):
        self.assertEqual(
            nested_get(self.data, "features[1].properties.time"),
            12,
        )
        self.assertIs(
            nested_get(self.data, "features[0]"),
            self.data["features"][0],
        )

    def test_dot_number_returns_explicitly_selected_item(self):
        self.assertEqual(
            nested_get(self.data, "features.1.properties.time"),
            12,
        )

    def test_list_traversal_without_index_returns_default(self):
        self.assertEqual(
            nested_get(
                self.data,
                "features.properties.time",
                default="not selected",
            ),
            "not selected",
        )

    def test_invalid_accesses_return_provided_default(self):
        paths = (
            "missing",
            "features[not-an-index].properties.time",
            "features[-1].properties.time",
            "features.properties.time",
            "zero_float.value",
            "features[9].properties.time",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(
                    nested_get(self.data, path, default="unavailable"),
                    "unavailable",
                )

    def test_invalid_accesses_raise_key_error_when_required(self):
        paths = (
            "missing",
            "features[not-an-index].properties.time",
            "features[-1].properties.time",
            "features.properties.time",
            "zero_float.value",
            "features[9].properties.time",
        )

        for path in paths:
            with self.subTest(path=path):
                with self.assertRaisesRegex(KeyError, "path"):
                    nested_get(self.data, path, required=True)

    def test_falsey_values_are_returned_unchanged(self):
        expected_values = {
            "features[0].properties.time": 0,
            "zero_float": 0.0,
            "features[0].properties.enabled": False,
            "features[1].properties.label": "",
        }

        for path, expected in expected_values.items():
            with self.subTest(path=path):
                actual = nested_get(self.data, path)
                self.assertEqual(actual, expected)
                self.assertIs(type(actual), type(expected))


class TestFeltReportEventDataFallbacks(unittest.TestCase):
    """Test that provider values fall back only when absent or None."""

    def _event_data(self, **primary_values):
        data = {
            "features": [
                {
                    "properties": {
                        "lon": 15.5,
                        "lat": 46.5,
                        "time": "fallback time",
                        "mag": 4.2,
                        "magtype": "Mw",
                        "depth": 8.0,
                        "region": "fallback region",
                        "last_update": "fallback update",
                        "feltreportCount": 23,
                        "eventid": "fallback id",
                    }
                }
            ]
        }
        data.update(primary_values)
        return FeltReportEventData(data)

    def test_numeric_zero_primary_value_does_not_fall_through(self):
        self.assertEqual(self._event_data(ev_longitude=0).get_longitude(), 0)

    def test_boolean_false_primary_value_does_not_fall_through(self):
        self.assertIs(
            self._event_data(ev_nbtestimonies=False).get_event_nbtestimonies(),
            False,
        )

    def test_empty_string_primary_value_does_not_fall_through(self):
        self.assertEqual(
            self._event_data(ev_region="").get_event_region(),
            "",
        )

    def test_missing_primary_value_uses_explicit_indexed_fallback(self):
        self.assertEqual(self._event_data().get_latitude(), 46.5)

    def test_none_primary_value_uses_explicit_indexed_fallback(self):
        self.assertEqual(
            self._event_data(ev_mag_value=None).get_magnitude(),
            4.2,
        )

    def test_indexed_fallback_uses_first_feature(self):
        event_data = self._event_data()
        event_data.get_data()["features"].append(
            {"properties": {"eventid": "second id"}}
        )

        self.assertEqual(event_data.get_event_id(), "fallback id")


if __name__ == "__main__":
    unittest.main()
