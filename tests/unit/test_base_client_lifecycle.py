# -*- coding: utf-8 -*-
import unittest

from paramws.clients import (
    EMSCFeltReportClient,
    ESMShakeMapClient,
    RRSMPeakMotionClient,
    RRSMShakeMapClient,
)
from paramws.clients.base_client import BaseClient


class ConnectorDouble:
    """Small connector stand-in for BaseClient lifecycle tests."""

    def __init__(self, agency=None, base_url=None, end_point=None, version=None):
        self.agency = agency
        self.base_url = base_url
        self.end_point = end_point
        self.version = version
        self.data = None

    def set_agency(self, agency):
        self.agency = agency

    def get_agency(self):
        return self.agency

    def set_base_url(self, base_url):
        self.base_url = base_url

    def get_base_url(self):
        return self.base_url

    def set_end_point(self, end_point):
        self.end_point = end_point

    def get_end_point(self):
        return self.end_point

    def set_version(self, version):
        self.version = version

    def get_version(self):
        return self.version

    def set_data(self, data):
        self.data = data

    def get_data(self):
        return self.data


class LifecycleClient(BaseClient):
    """Exercise shared behavior without imposing a concrete result shape."""

    def create_web_service(self):
        self.ws_client = ConnectorDouble(
            agency=self.agency,
            base_url=self.base_url,
            end_point=self.end_point,
            version=self.version,
        )
        return self.ws_client

    def query(self, requested_dataset_keys=(), **options):
        self._reset_query_state(requested_dataset_keys)
        # Per-call options stay local so a later call starts independently.
        query_options = dict(options)
        return query_options.get("provider_result")


class TestBaseClientLifecycle(unittest.TestCase):
    def test_initial_result_state_has_no_generic_amplitude_storage(self):
        client = LifecycleClient()

        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {})
        self.assertFalse(hasattr(client, "amplitude_data"))
        self.assertNotIn("amplitude_data", BaseClient.__dict__)

    def test_reset_creates_only_requested_keys_in_a_fresh_dictionary(self):
        client = LifecycleClient()
        first_datasets = client.get_datasets()

        client._reset_query_state(("station_amplitudes", "felt_intensities"))

        self.assertEqual(
            client.get_datasets(),
            {
                "station_amplitudes": None,
                "felt_intensities": None,
            },
        )
        self.assertNotIn("peak_motion", client.get_datasets())
        self.assertIsNot(first_datasets, client.get_datasets())

    def test_second_reset_removes_previous_results_and_connector_data(self):
        client = LifecycleClient()
        connector = client.create_web_service()
        connector.set_data(object())
        client.set_event_data(object())
        client._reset_query_state(("station_amplitudes",))
        client.get_datasets()["station_amplitudes"] = object()
        first_reset_datasets = client.get_datasets()
        connector.set_data(object())

        client._reset_query_state(("peak_motion",))

        self.assertIsNone(client.get_event_data())
        self.assertEqual(client.get_datasets(), {"peak_motion": None})
        self.assertIsNot(first_reset_datasets, client.get_datasets())
        self.assertIsNone(connector.get_data())

    def test_query_options_and_provider_specific_result_do_not_persist(self):
        client = LifecycleClient()

        first_result = client.query(
            ("station_amplitudes",),
            provider_result="provider-specific result",
            temporary_option=["mutable"],
        )
        second_result = client.query(("felt_intensities",))

        self.assertEqual(first_result, "provider-specific result")
        self.assertIsNone(second_result)
        self.assertEqual(client.get_datasets(), {"felt_intensities": None})

    def test_configuration_setters_are_safe_before_connector_creation(self):
        client = LifecycleClient()

        client.set_agency("TEST")
        client.set_base_url("https://example.test/service")
        client.set_end_point("events")
        client.set_version("9")
        connector = client.create_web_service()

        self.assertEqual(client.get_agency(), "TEST")
        self.assertEqual(client.get_base_url(),
                         "https://example.test/service/")
        self.assertEqual(client.get_end_point(), "events")
        self.assertEqual(client.get_version(), "9")
        self.assertEqual(connector.get_agency(), "TEST")
        self.assertEqual(connector.get_base_url(),
                         "https://example.test/service/")
        self.assertEqual(connector.get_end_point(), "events")
        self.assertEqual(connector.get_version(), "9")

    def test_base_client_owns_no_provider_specific_semantic_methods(self):
        for method_name in (
                "set_station_amplitudes",
                "get_station_amplitudes",
                "set_feltreports",
                "get_feltreports"):
            with self.subTest(method_name=method_name):
                self.assertFalse(hasattr(BaseClient, method_name))


class TestConcreteClientConfiguration(unittest.TestCase):
    client_classes = (
        ESMShakeMapClient,
        RRSMShakeMapClient,
        RRSMPeakMotionClient,
        EMSCFeltReportClient,
    )

    def test_setters_update_client_and_connector_and_survive_recreation(self):
        expected_values = {
            "agency": "TEST",
            "base_url": "https://example.test/service/",
            "end_point": "events",
            "version": "9",
        }

        for client_class in self.client_classes:
            with self.subTest(client_class=client_class.__name__):
                client = client_class()
                original_connector = client.get_web_service()

                client.set_agency(expected_values["agency"])
                self.assertEqual(
                    original_connector.get_agency(),
                    expected_values["agency"],
                )
                client.set_base_url("https://example.test/service")
                self.assertEqual(
                    original_connector.get_base_url(),
                    expected_values["base_url"],
                )
                client.set_end_point(expected_values["end_point"])
                self.assertEqual(
                    original_connector.get_end_point(),
                    expected_values["end_point"],
                )
                client.set_version(expected_values["version"])
                self.assertEqual(
                    original_connector.get_version(),
                    expected_values["version"],
                )

                replacement_connector = client.create_web_service()

                self.assertIsNot(replacement_connector, original_connector)
                for field_name, expected_value in expected_values.items():
                    client_getter = getattr(client, "get_" + field_name)
                    connector_getter = getattr(
                        replacement_connector,
                        "get_" + field_name,
                    )
                    self.assertEqual(client_getter(), expected_value)
                    self.assertEqual(connector_getter(), expected_value)

    def test_connector_only_changes_do_not_replace_client_configuration(self):
        for client_class in self.client_classes:
            with self.subTest(client_class=client_class.__name__):
                client = client_class()
                expected_values = {
                    "agency": client.get_agency(),
                    "base_url": client.get_base_url(),
                    "end_point": client.get_end_point(),
                    "version": client.get_version(),
                }
                connector = client.get_web_service()
                connector.set_agency("CONNECTOR")
                connector.set_base_url("https://connector.test/")
                connector.set_end_point("connector-events")
                connector.set_version("connector-version")

                for field_name, expected_value in expected_values.items():
                    self.assertEqual(
                        getattr(client, "get_" + field_name)(),
                        expected_value,
                    )

                replacement_connector = client.create_web_service()
                for field_name, expected_value in expected_values.items():
                    self.assertEqual(
                        getattr(replacement_connector,
                                "get_" + field_name)(),
                        expected_value,
                    )


class TestConcreteSemanticDatasets(unittest.TestCase):
    def test_semantic_methods_remain_on_relevant_concrete_clients(self):
        client_methods = {
            ESMShakeMapClient: (
                "set_station_amplitudes",
                "get_station_amplitudes",
            ),
            RRSMShakeMapClient: (
                "set_station_amplitudes",
                "get_station_amplitudes",
            ),
            RRSMPeakMotionClient: (
                "set_station_amplitudes",
                "get_station_amplitudes",
            ),
            EMSCFeltReportClient: (
                "set_feltreports",
                "get_feltreports",
            ),
        }

        for client_class, method_names in client_methods.items():
            for method_name in method_names:
                with self.subTest(
                        client_class=client_class.__name__,
                        method_name=method_name):
                    self.assertIn(method_name, client_class.__dict__)

    def test_station_data_uses_each_client_semantic_key(self):
        client_keys = (
            (ESMShakeMapClient, "station_amplitudes"),
            (RRSMShakeMapClient, "station_amplitudes"),
            (RRSMPeakMotionClient, "peak_motion"),
        )

        for client_class, dataset_key in client_keys:
            with self.subTest(client_class=client_class.__name__):
                client = client_class()
                self.assertIsNone(client.get_station_amplitudes())
                station_data = object()

                client.set_station_amplitudes(station_data)

                self.assertEqual(
                    client.get_datasets(),
                    {dataset_key: station_data},
                )
                self.assertIs(client.get_station_amplitudes(), station_data)

    def test_felt_reports_use_felt_intensities_key(self):
        client = EMSCFeltReportClient()
        self.assertIsNone(client.get_feltreports())
        client.set_event_id("event-id")
        felt_reports = {
            "event-id": {
                "unid": "event-id",
                "intensities": [],
                "comments": "",
            },
        }

        client.set_feltreports(felt_reports)

        self.assertEqual(
            client.get_datasets(),
            {"felt_intensities": felt_reports},
        )
        self.assertEqual(client.get_feltreports().get_event_id(), "event-id")


if __name__ == "__main__":
    unittest.main()
