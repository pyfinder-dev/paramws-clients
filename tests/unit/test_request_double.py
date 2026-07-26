"""Unit tests for the deterministic scripted request helper."""
import socket
import unittest
from unittest import mock

from request_double import ScriptedRequest


class TestScriptedRequest(unittest.TestCase):
    """Verify ordered request outcomes and recorded transport inputs."""

    def test_returns_status_and_body_outcomes_unchanged_in_order(self):
        first = (200, b"first body")
        second = (503, {"provider": "body"})
        scripted = ScriptedRequest([first, second])

        self.assertIs(scripted.request("https://example.test/first", 10), first)
        self.assertIs(scripted.request("https://example.test/second", 10), second)

    def test_raises_ordered_exception_and_continues_with_next_outcome(self):
        failure = TimeoutError("provider timed out")
        success = (200, object())
        scripted = ScriptedRequest([failure, success])

        with self.assertRaises(TimeoutError) as raised:
            scripted.request("https://example.test/retry", 10)

        self.assertIs(raised.exception, failure)
        self.assertIs(scripted.request("https://example.test/retry", 10), success)

    def test_records_urls_and_timeouts_for_successes_and_exceptions(self):
        resolved_url = (
            "https://products.example.test/download/stationlist.json?"
            "eventid=ci38443183&format=geojson"
        )
        failure = ConnectionError("connection failed")
        scripted = ScriptedRequest([(200, b"event"), failure])

        scripted.request("https://example.test/event?id=one", 10)
        with self.assertRaises(ConnectionError):
            scripted.request(resolved_url, 7.5)

        self.assertEqual(
            scripted.requested_urls,
            ["https://example.test/event?id=one", resolved_url],
        )
        self.assertEqual(scripted.recorded_timeouts, [10, 7.5])

    def test_delay_records_values_without_sleeping(self):
        scripted = ScriptedRequest([])

        with mock.patch("time.sleep", side_effect=AssertionError("real sleep called")):
            result = scripted.delay(2)
            scripted.delay(0.25)

        self.assertIsNone(result)
        self.assertEqual(scripted.recorded_delays, [2, 0.25])

    def test_exhaustion_raises_clear_assertion(self):
        scripted = ScriptedRequest([(200, b"only outcome")])
        scripted.request("https://example.test/first", 10)

        with self.assertRaisesRegex(
            AssertionError,
            "more requests than the configured outcomes",
        ):
            scripted.request("https://example.test/unexpected", 10)

    def test_requests_do_not_use_network_operations(self):
        scripted = ScriptedRequest([(200, b"offline")])

        with mock.patch(
            "socket.create_connection",
            side_effect=AssertionError("network connection attempted"),
        ), mock.patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("socket connection attempted"),
        ):
            result = scripted.request("https://example.test/offline", 10)

        self.assertEqual(result, (200, b"offline"))


if __name__ == "__main__":
    unittest.main()
