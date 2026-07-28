# -*- coding: utf-8 -*-
"""Deterministically verify the live-provider outcome classification."""

import socket
import ssl
import unittest

from tests.live_result import require_live_result


def raise_error(error):
    """Return a callable that raises the selected request error."""
    def request():
        raise error

    return request


class TestLiveResultClassification(unittest.TestCase):
    """Keep temporary availability distinct from contract failures."""

    def test_timeout_connection_and_dns_failures_skip_with_context(self):
        cases = (
            (TimeoutError("response timed out"), "timeout"),
            (ConnectionError("connection refused"), "connection failure"),
            (socket.gaierror(-2, "name not known"), "DNS failure"),
        )

        for error, category in cases:
            with self.subTest(category=category):
                with self.assertRaises(unittest.SkipTest) as caught:
                    require_live_result(
                        "ExampleProvider",
                        "event dataset",
                        raise_error(error),
                    )

                reason = str(caught.exception)
                self.assertIn("ExampleProvider", reason)
                self.assertIn("event dataset", reason)
                self.assertIn(category, reason)
                self.assertIn(str(error), reason)

    def test_rate_limit_and_server_errors_skip_with_status(self):
        for status in (429, 500, 503, 599):
            with self.subTest(status=status):
                with self.assertRaises(unittest.SkipTest) as caught:
                    require_live_result(
                        "ExampleProvider",
                        "station dataset",
                        lambda status=status: (status, None),
                    )

                reason = str(caught.exception)
                self.assertIn("ExampleProvider", reason)
                self.assertIn("station dataset", reason)
                self.assertIn("status={}".format(status), reason)

    def test_tls_and_parsing_errors_remain_failures(self):
        tls_error = ssl.SSLError("certificate verification failed")
        with self.assertRaises(ssl.SSLError) as caught_tls:
            require_live_result(
                "ExampleProvider",
                "event dataset",
                raise_error(tls_error),
            )
        self.assertIs(caught_tls.exception, tls_error)

        parsing_error = ValueError("malformed successful content")
        with self.assertRaises(ValueError) as caught_parsing:
            require_live_result(
                "ExampleProvider",
                "event dataset",
                raise_error(parsing_error),
            )
        self.assertIs(caught_parsing.exception, parsing_error)

    def test_unexpected_statuses_and_result_shapes_remain_failures(self):
        for status in (None, 200.0, 201, 400, 404, 499, 600):
            with self.subTest(status=status):
                with self.assertRaisesRegex(
                        AssertionError, "unexpected HTTP status"):
                    require_live_result(
                        "ExampleProvider",
                        "event dataset",
                        lambda status=status: (status, None),
                    )

        for result in (None, [], (), {"status": 200}):
            with self.subTest(result=result):
                with self.assertRaisesRegex(
                        AssertionError, "public result shape"):
                    require_live_result(
                        "ExampleProvider",
                        "event dataset",
                        lambda result=result: result,
                    )

    def test_successful_result_passes_through_unchanged(self):
        result = (200, object(), {"dataset": object()})

        returned = require_live_result(
            "ExampleProvider",
            "event dataset",
            lambda: result,
        )

        self.assertIs(returned, result)


if __name__ == "__main__":
    unittest.main()
