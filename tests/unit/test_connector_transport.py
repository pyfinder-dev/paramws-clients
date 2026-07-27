"""Deterministic unit tests for connector HTTP transport behavior."""
import socket
import ssl
import unittest
import urllib.error
import urllib.request
from unittest import mock
from urllib.parse import urlencode

from paramws.clients.services import httphelpers
from paramws.clients.services.baseconnector import (
    BaseWebServiceConnector,
    InvalidOptionValue,
)
from paramws.utils.customlogger import logger
from request_double import ScriptedRequest


class DeterministicValidationError(Exception):
    """Represent a parser validation failure unrelated to transport."""


class TransportConnector(BaseWebServiceConnector):
    """Small concrete connector that exposes transport results to tests."""

    def __init__(self, parser=None):
        self._parser = parser
        super().__init__(
            agency="TEST",
            base_url="https://service.example.test/",
            end_point="transport",
            version="1",
        )

    def build_url(self, **options):
        options = self.validate_options(**options)
        self.combined_url = (
            "{}{}/{}/query?{}"
            .format(self.base_url, self.end_point, self.version,
                    urlencode(options))
        )
        return self.combined_url

    def parse_response(self, file_like_obj=None, options=None):
        if self._parser is not None:
            return self._parser(file_like_obj, options)
        return file_like_obj

    def get_supported_options(self):
        return ["dataset", "eventid"]

    def is_value_valid(self, option, value):
        return option != "dataset" or value in {"event", "stations"}


class TestConnectorTransport(unittest.TestCase):
    """Verify resolved requests, retries, errors, and diagnostic context."""

    def make_connector(self, outcomes, parser=None):
        connector = TransportConnector(parser=parser)
        scripted = ScriptedRequest(outcomes)
        connector._request_callable = scripted.request
        connector._delay_callable = scripted.delay
        return connector, scripted

    def test_resolved_url_is_requested_as_the_exact_supplied_string(self):
        resolved_url = (
            "https://products.example.test/content/stationlist.json?"
            "second=a%2Fb&first=x%20y&second=c%2Bd&opaque=%252F"
        )
        connector, scripted = self.make_connector([(200, b"content")])

        code, data = connector.query(url=resolved_url)

        self.assertEqual((code, data), (200, b"content"))
        self.assertEqual(scripted.requested_urls, [resolved_url])
        self.assertEqual(scripted.recorded_timeouts, [10])
        self.assertEqual(scripted.recorded_delays, [])

    def test_keyword_options_still_validate_and_build_provider_url(self):
        connector, scripted = self.make_connector([(200, b"content")])

        code, data = connector.query(eventid="event&catalog=other")

        self.assertEqual((code, data), (200, b"content"))
        self.assertEqual(
            scripted.requested_urls,
            [
                "https://service.example.test/transport/1/query?"
                "eventid=event%26catalog%3Dother"
            ],
        )

    def test_invalid_keyword_option_value_fails_before_transport(self):
        connector, scripted = self.make_connector([(200, b"unused")])

        with self.assertRaises(InvalidOptionValue):
            connector.query(dataset="unsupported")

        self.assertEqual(scripted.requested_urls, [])
        self.assertEqual(scripted.recorded_delays, [])

    def test_exhausted_timeout_uses_three_attempts_and_two_delays(self):
        failures = [
            TimeoutError("connect timed out"),
            socket.timeout("response timed out"),
            urllib.error.URLError(TimeoutError("final timeout")),
        ]
        connector, scripted = self.make_connector(failures)

        with self.assertRaises(TimeoutError) as raised:
            connector.query(url="https://service.example.test/timeout")

        self.assertEqual(len(scripted.requested_urls), 3)
        self.assertEqual(scripted.recorded_timeouts, [10, 10, 10])
        self.assertEqual(scripted.recorded_delays, [2, 2])
        self.assertIs(raised.exception.__cause__, failures[-1])
        self.assertNotIsInstance(raised.exception, urllib.error.HTTPError)

    def test_timeout_followed_by_success_returns_success(self):
        connector, scripted = self.make_connector([
            TimeoutError("temporary timeout"),
            (200, b"recovered"),
        ])

        result = connector.query(url="https://service.example.test/recover")

        self.assertEqual(result, (200, b"recovered"))
        self.assertEqual(scripted.recorded_timeouts, [10, 10])
        self.assertEqual(scripted.recorded_delays, [2])

    def test_exhausted_dns_failure_maps_to_connection_error(self):
        failures = [
            socket.gaierror(-2, "name not known"),
            urllib.error.URLError(
                socket.gaierror(-2, "temporary resolution failure")),
            socket.gaierror(-2, "final name failure"),
        ]
        connector, scripted = self.make_connector(failures)

        with self.assertRaises(ConnectionError) as raised:
            connector.query(url="https://missing.example.test/data")

        self.assertEqual(len(scripted.requested_urls), 3)
        self.assertEqual(scripted.recorded_timeouts, [10, 10, 10])
        self.assertEqual(scripted.recorded_delays, [2, 2])
        self.assertIs(raised.exception.__cause__, failures[-1])

    def test_connection_failure_followed_by_success_returns_success(self):
        connector, scripted = self.make_connector([
            ConnectionRefusedError("connection refused"),
            (200, b"recovered"),
        ])

        result = connector.query(url="https://service.example.test/recover")

        self.assertEqual(result, (200, b"recovered"))
        self.assertEqual(scripted.recorded_timeouts, [10, 10])
        self.assertEqual(scripted.recorded_delays, [2])

    def test_direct_and_wrapped_tls_failures_are_not_retried(self):
        direct_error = ssl.SSLError("certificate verify failed")
        wrapped_reason = ssl.SSLError("hostname mismatch")
        wrapped_error = urllib.error.URLError(wrapped_reason)

        for configured, expected, expected_cause in (
                (direct_error, direct_error, None),
                (wrapped_error, wrapped_reason, wrapped_error)):
            with self.subTest(error=configured):
                connector, scripted = self.make_connector([
                    configured,
                    (200, b"must not be requested"),
                ])

                with self.assertRaises(ssl.SSLError) as raised:
                    connector.query(
                        url="https://service.example.test/tls")

                self.assertIs(raised.exception, expected)
                self.assertIs(raised.exception.__cause__, expected_cause)
                self.assertEqual(len(scripted.requested_urls), 1)
                self.assertEqual(scripted.recorded_timeouts, [10])
                self.assertEqual(scripted.recorded_delays, [])

    def test_each_retryable_http_status_uses_exact_attempt_policy(self):
        url = "https://service.example.test/status"

        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                connector, scripted = self.make_connector([
                    (status, b"failure"),
                    (status, b"failure"),
                    (status, b"failure"),
                ])

                result = connector.query(url=url)

                self.assertEqual(result, (status, None))
                self.assertEqual(scripted.requested_urls, [url, url, url])
                self.assertEqual(scripted.recorded_timeouts, [10, 10, 10])
                self.assertEqual(scripted.recorded_delays, [2, 2])

    def test_retryable_http_error_followed_by_success_returns_success(self):
        url = "https://service.example.test/status"
        http_error = urllib.error.HTTPError(
            url, 503, "service unavailable", None, None)
        connector, scripted = self.make_connector([
            http_error,
            (200, b"recovered"),
        ])

        result = connector.query(url=url)

        self.assertEqual(result, (200, b"recovered"))
        self.assertEqual(scripted.recorded_timeouts, [10, 10])
        self.assertEqual(scripted.recorded_delays, [2])

    def test_exhausted_retryable_http_response_retains_final_status(self):
        connector, scripted = self.make_connector([
            (500, b"first"),
            (502, b"second"),
            (504, b"final"),
        ])

        result = connector.query(
            url="https://service.example.test/changing-status")

        self.assertEqual(result, (504, None))
        self.assertEqual(len(scripted.requested_urls), 3)
        self.assertEqual(scripted.recorded_delays, [2, 2])

    def test_non_retryable_http_statuses_return_after_one_attempt(self):
        for status in (301, 400, 404, 418, 501):
            with self.subTest(status=status):
                connector, scripted = self.make_connector([
                    (status, b"provider response"),
                    (200, b"must not be requested"),
                ])

                result = connector.query(
                    url="https://service.example.test/non-retryable")

                self.assertEqual(result, (status, None))
                self.assertEqual(len(scripted.requested_urls), 1)
                self.assertEqual(scripted.recorded_timeouts, [10])
                self.assertEqual(scripted.recorded_delays, [])

    def test_empty_success_content_raises_value_error_without_retry(self):
        connector, scripted = self.make_connector([
            (200, b""),
            (200, b"must not be requested"),
        ])

        with self.assertRaisesRegex(
                ValueError, "TEST returned an empty successful response"):
            connector.query(url="https://service.example.test/empty")

        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_timeouts, [10])
        self.assertEqual(scripted.recorded_delays, [])

    def test_invalid_success_content_raises_value_error_without_retry(self):
        def reject_invalid_content(_body, _options):
            raise ValueError(
                "TEST expected structured transport content; validation failed")

        connector, scripted = self.make_connector(
            [(200, b"invalid"), (200, b"must not be requested")],
            parser=reject_invalid_content,
        )

        with self.assertRaisesRegex(ValueError, "validation failed"):
            connector.query(url="https://service.example.test/invalid")

        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_delays, [])

    def test_none_parser_result_is_invalid_and_not_retried(self):
        connector, scripted = self.make_connector(
            [(200, b"invalid"), (200, b"must not be requested")],
            parser=lambda _body, _options: None,
        )

        with self.assertRaisesRegex(
                ValueError, "TEST returned invalid successful content"):
            connector.query(url="https://service.example.test/invalid")

        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_delays, [])

    def test_deterministic_parser_failure_is_not_retried(self):
        failure = DeterministicValidationError("required field is missing")

        def reject_content(_body, _options):
            raise failure

        connector, scripted = self.make_connector(
            [(200, b"invalid"), (200, b"must not be requested")],
            parser=reject_content,
        )

        with self.assertRaises(DeterministicValidationError) as raised:
            connector.query(url="https://service.example.test/parser")

        self.assertIs(raised.exception, failure)
        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_delays, [])

    def test_unrelated_request_exception_is_not_retried_or_mapped(self):
        failure = RuntimeError("unexpected request implementation failure")
        connector, scripted = self.make_connector([
            failure,
            (200, b"must not be requested"),
        ])

        with self.assertRaises(RuntimeError) as raised:
            connector.query(url="https://service.example.test/unrelated")

        self.assertIs(raised.exception, failure)
        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_delays, [])

    def test_unrelated_url_error_is_not_retried_or_mapped(self):
        failure = urllib.error.URLError("unknown url type: custom")
        connector, scripted = self.make_connector([
            failure,
            (200, b"must not be requested"),
        ])

        with self.assertLogs(logger, level="ERROR") as captured:
            with self.assertRaises(urllib.error.URLError) as raised:
                connector.query(
                    url="custom://service.example.test/unrelated")

        self.assertIs(raised.exception, failure)
        self.assertNotIsInstance(raised.exception, ConnectionError)
        self.assertEqual(len(scripted.requested_urls), 1)
        self.assertEqual(scripted.recorded_timeouts, [10])
        self.assertEqual(scripted.recorded_delays, [])
        self.assertIn("outcome=not-retryable", captured.output[-1])

    def test_retry_and_terminal_logs_include_required_context(self):
        url = (
            "https://service.example.test/data?"
            "dataset=stations&eventid=event%2Fone"
        )
        connector, scripted = self.make_connector([
            TimeoutError("response stalled"),
            (503, b"temporarily unavailable"),
            (404, b"not found"),
        ])

        with self.assertLogs(logger, level="WARNING") as captured:
            result = connector.query(url=url)

        self.assertEqual(result, (404, None))
        self.assertEqual(scripted.recorded_delays, [2, 2])
        retry_timeout, retry_status, terminal = captured.output

        for context in (
                "provider='TEST'", url, "status=None", "attempt=1/3",
                "outcome=retry", "transport", "stations",
                "response stalled", "retry_delay=2"):
            self.assertIn(context, retry_timeout)

        for context in (
                "provider='TEST'", url, "status=503", "attempt=2/3",
                "outcome=retry", "transport", "stations",
                "HTTP status 503", "retry_delay=2"):
            self.assertIn(context, retry_status)

        for context in (
                "provider='TEST'", url, "status=404", "attempt=3/3",
                "outcome=not-retryable", "transport", "stations",
                "HTTP status 404"):
            self.assertIn(context, terminal)

    def test_exhausted_exception_log_contains_underlying_reason(self):
        url = "https://service.example.test/data?dataset=event"
        connector, _scripted = self.make_connector([
            ConnectionResetError("first reset"),
            ConnectionResetError("second reset"),
            ConnectionResetError("final connection reset"),
        ])

        with self.assertLogs(logger, level="ERROR") as captured:
            with self.assertRaises(ConnectionError):
                connector.query(url=url)

        terminal = captured.output[-1]
        for context in (
                "provider='TEST'", url, "status=None", "attempt=3/3",
                "outcome=exhausted", "transport", "event",
                "final connection reset"):
            self.assertIn(context, terminal)

    def test_url_user_information_is_removed_from_success_logs(self):
        url = (
            "https://url-user:url-password@service.example.test/"
            "private/data?dataset=event"
        )
        connector, scripted = self.make_connector([(200, b"content")])

        with self.assertLogs(logger, level="DEBUG") as captured:
            result = connector.query(url=url)

        self.assertEqual(result, (200, b"content"))
        self.assertEqual(scripted.requested_urls, [url])
        output = "\n".join(captured.output)
        self.assertNotIn("url-user", output)
        self.assertNotIn("url-password", output)
        self.assertIn(
            "[redacted]@service.example.test/private/data", output)

    def test_url_user_information_is_removed_from_failure_logs(self):
        url = (
            "https://url-user:url-password@service.example.test/"
            "private/data?dataset=event"
        )
        cases = (
            ("non-retryable", [(404, b"not found")], 1),
            (
                "retry-and-exhausted",
                [(503, b"unavailable")] * 3,
                3,
            ),
        )

        for _name, outcomes, attempts in cases:
            with self.subTest(outcome=_name):
                connector, scripted = self.make_connector(outcomes)

                with self.assertLogs(logger, level="WARNING") as captured:
                    connector.query(url=url)

                self.assertEqual(scripted.requested_urls, [url] * attempts)
                output = "\n".join(captured.output)
                self.assertNotIn("url-user", output)
                self.assertNotIn("url-password", output)
                for record in captured.output:
                    self.assertIn(
                        "[redacted]@service.example.test/private/data",
                        record,
                    )

    def test_authentication_and_redirect_handlers_remain_intact(self):
        cases = (
            (None, None, False, (httphelpers.CustomRedirectHandler,)),
            (
                "request-user",
                "request-password",
                False,
                (
                    urllib.request.HTTPDigestAuthHandler,
                    httphelpers.NoRedirectionHandler,
                ),
            ),
            (
                "request-user",
                "request-password",
                True,
                (
                    urllib.request.HTTPDigestAuthHandler,
                    httphelpers.CustomRedirectHandler,
                ),
            ),
        )

        for user, password, force_redirect, expected_types in cases:
            with self.subTest(
                    user=user, force_redirect=force_redirect):
                connector, _scripted = self.make_connector([(200, b"ok")])
                connector.set_force_redirect(force_redirect)

                with mock.patch(
                        "paramws.clients.services.baseconnector."
                        "urlrequest.build_opener",
                        return_value=mock.Mock()) as build_opener:
                    connector.query(
                        url="https://service.example.test/auth",
                        user=user,
                        password=password,
                    )

                handlers = build_opener.call_args.args
                self.assertEqual(
                    tuple(type(handler) for handler in handlers),
                    expected_types,
                )

    def test_credentials_are_not_written_to_failure_logs(self):
        connector, _scripted = self.make_connector([
            (404, b"not found"),
        ])

        with self.assertLogs(logger, level="ERROR") as captured:
            connector.query(
                url="https://service.example.test/auth",
                user="secret-user",
                password="secret-password",
            )

        output = "\n".join(captured.output)
        self.assertNotIn("secret-user", output)
        self.assertNotIn("secret-password", output)


if __name__ == "__main__":
    unittest.main()
