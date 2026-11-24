"""GIVEN: clocks. Not part of the exercise.

PeerPay never reads the time by itself; it asks the clock it was given (DESIGN.md §9).
"""
from datetime import datetime, timedelta


class SystemClock:
    """The real time."""

    def __call__(self) -> datetime:
        return datetime.now()


class FakeClock:
    """A clock for tests: starts at the real current time and moves only when told to."""

    def __init__(self, start: datetime | None = None):
        self._now = start if start is not None else datetime.now()

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **delta) -> None:
        """clock.advance(days=31), clock.advance(minutes=5), ..."""
        self._now += timedelta(**delta)
