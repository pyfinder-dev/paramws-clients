"""Deterministic request behavior for transport unit tests."""
from collections import deque


class ScriptedRequest:
    """Return or raise outcomes in the order configured by a test."""

    def __init__(self, outcomes):
        self._outcomes = deque(outcomes)
        # Calls are recorded before their outcomes are handled so failures remain
        # visible when tests verify attempt order and the timeout used each time.
        self.requested_urls = []
        self.recorded_timeouts = []
        self.recorded_delays = []

    def request(self, url, timeout):
        """Consume one outcome while preserving the supplied URL and timeout."""
        self.requested_urls.append(url)
        self.recorded_timeouts.append(timeout)

        if not self._outcomes:
            raise AssertionError(
                "The test made more requests than the configured outcomes."
            )

        outcome = self._outcomes.popleft()
        if isinstance(outcome, BaseException):
            raise outcome

        # Bodies remain opaque because interpreting provider data belongs to
        # provider-specific parsing code, not this request helper.
        return outcome

    def delay(self, seconds):
        """Record a retry delay without making deterministic tests sleep."""
        self.recorded_delays.append(seconds)

