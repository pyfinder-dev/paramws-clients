"""Unit tests for the deterministic scripted request helper."""
import socket
import unittest
from unittest import mock

from request_double import ScriptedRequest


class TestScriptedRequest(unittest.TestCase):
    """Keep the request double offline, delay-free, and strict about exhaustion."""

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
