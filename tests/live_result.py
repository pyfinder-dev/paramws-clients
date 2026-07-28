# -*- coding: utf-8 -*-
"""
Apply the accepted outcome classification to one live provider operation.

Only temporary reachability and provider-availability failures become skips.
TLS verification, unexpected client statuses, and successful-content parsing
or validation errors deliberately remain visible test failures because they
indicate a contract problem that requires investigation.
"""

import socket
import unittest


def require_live_result(provider, operation, request):
    """
    Execute one live request and return its unchanged successful result.

    ``request`` is kept as a callable so transport exceptions and returned
    HTTP statuses pass through the same classification. The helper assumes the
    project's established tuple result with HTTP status in its first position.
    """
    try:
        result = request()
    except TimeoutError as error:
        raise unittest.SkipTest(
            "{} {} unavailable: category=timeout; detail={}: {}"
            .format(provider, operation, type(error).__name__, error)
        ) from error
    except socket.gaierror as error:
        raise unittest.SkipTest(
            "{} {} unavailable: category=DNS failure; detail={}: {}"
            .format(provider, operation, type(error).__name__, error)
        ) from error
    except ConnectionError as error:
        raise unittest.SkipTest(
            "{} {} unavailable: category=connection failure; detail={}: {}"
            .format(provider, operation, type(error).__name__, error)
        ) from error

    if not isinstance(result, tuple) or not result:
        raise AssertionError(
            "{} {} returned an incompatible public result shape: {!r}"
            .format(provider, operation, result)
        )

    status = result[0]
    if status == 429:
        raise unittest.SkipTest(
            "{} {} unavailable: category=rate limiting; status=429"
            .format(provider, operation)
        )
    if (
            isinstance(status, int)
            and not isinstance(status, bool)
            and 500 <= status <= 599):
        raise unittest.SkipTest(
            "{} {} unavailable: category=provider server error; status={}"
            .format(provider, operation, status)
        )
    if (
            status != 200
            or not isinstance(status, int)
            or isinstance(status, bool)):
        raise AssertionError(
            "{} {} returned unexpected HTTP status {!r}; expected 200"
            .format(provider, operation, status)
        )

    return result
