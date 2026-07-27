# -*- coding: utf-8 -*-
"""Unit tests for the EMSC felt-report connector."""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from paramws.clients.services import EMSCFeltReportConnector, InvalidOptionValue
from paramws.utils.customlogger import logger

class TestEMSCFeltReportWebService(unittest.TestCase):
    """Unit tests for the EMSC felt-report web service connector."""
    def test_supported_options(self):
        # Test the get_supported_options method.
        client = EMSCFeltReportConnector()
        options = client.get_supported_options()
        self.assertEqual(options, ['unids', 'includeTestimonies'])

    def test_url_build(self):
        # Test the build_url method.
        client = EMSCFeltReportConnector()
        client.set_version("1.1")
        client.set_end_point("api")
        client.set_base_url("https://www.seismicportal.eu/testimonies-ws")
        url = client.build_url()
        self.assertEqual(url, "https://www.seismicportal.eu/testimonies-ws/api/search?")

    def test_legacy_spellings_normalize_to_canonical_option(self):
        for alias in (
                "includetestimonies",
                "IncludeTestimonies",
                "Includetestimonies"):
            with self.subTest(alias=alias):
                client = EMSCFeltReportConnector()
                with patch.object(logger, "warning") as warning:
                    url = client.build_url(**{alias: "true"})

                self.assertEqual(
                    parse_qs(urlsplit(url).query),
                    {"includeTestimonies": ["true"]},
                )
                warning.assert_not_called()

    def test_canonical_spelling_takes_precedence_over_aliases(self):
        client = EMSCFeltReportConnector()

        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(
                includeTestimonies="true",
                includetestimonies="false",
                IncludeTestimonies="false",
                Includetestimonies="false",
            )

        self.assertEqual(
            parse_qs(urlsplit(url).query),
            {"includeTestimonies": ["true"]},
        )
        self.assertEqual(len(captured.output), 3)
        for alias, warning in zip(
                ("includetestimonies",
                 "IncludeTestimonies",
                 "Includetestimonies"),
                captured.output):
            for context in ("EMSC", "api", alias, "false"):
                self.assertIn(context, warning)

    def test_alias_priority_is_deterministic_when_spellings_collide(self):
        client = EMSCFeltReportConnector()

        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(
                includetestimonies="true",
                IncludeTestimonies="false",
                Includetestimonies="false",
            )

        self.assertEqual(
            parse_qs(urlsplit(url).query),
            {"includeTestimonies": ["true"]},
        )
        self.assertEqual(len(captured.output), 2)
        for alias, warning in zip(
                ("IncludeTestimonies", "Includetestimonies"),
                captured.output):
            for context in ("EMSC", "api", alias, "false"):
                self.assertIn(context, warning)

    def test_unsupported_option_is_warned_about_and_removed(self):
        client = EMSCFeltReportConnector()

        with self.assertLogs(logger, level="WARNING") as captured:
            url = client.build_url(
                unids="event_id",
                unexpected="ignored_value",
            )

        self.assertNotIn("unexpected", url)
        warning = captured.output[0]
        for context in ("EMSC", "api", "unexpected", "ignored_value"):
            self.assertIn(context, warning)

    def test_invalid_include_testimonies_value_is_rejected(self):
        client = EMSCFeltReportConnector()

        with self.assertRaises(InvalidOptionValue):
            client.build_url(
                unids="event_id",
                includeTestimonies="sometimes",
            )

    def test_unids_delimiters_round_trip_as_one_bracketed_value(self):
        client = EMSCFeltReportConnector()
        event_id = "event&includeTestimonies=false=extra"

        url = client.build_url(unids=event_id)
        parsed_options = parse_qs(urlsplit(url).query)

        self.assertEqual(parsed_options, {"unids": ["[{}]".format(event_id)]})
        self.assertIn("unids=[", url)
        self.assertIn("%26", url)
        self.assertIn("%3D", url)

    def test_valid_options_do_not_warn(self):
        client = EMSCFeltReportConnector()

        with patch.object(logger, "warning") as warning:
            client.build_url(
                unids="event_id",
                includeTestimonies="true",
            )

        warning.assert_not_called()
