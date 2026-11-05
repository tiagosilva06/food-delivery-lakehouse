"""Tests for the simulator virtual clock."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock


def test_clock_normalizes_time_to_utc_and_advances_explicitly() -> None:
    """Keep logical time in UTC and move only by the requested duration."""
    sao_paulo = timezone(timedelta(hours=-3))
    clock = VirtualClock(datetime(2026, 10, 27, 21, 0, tzinfo=sao_paulo))

    assert clock.now() == datetime(2026, 10, 28, 0, 0, tzinfo=UTC)
    assert clock.advance(timedelta(minutes=5)) == datetime(2026, 10, 28, 0, 5, tzinfo=UTC)


def test_clock_rejects_naive_datetime() -> None:
    """Reject logical start times without timezone information."""
    with pytest.raises(ValueError, match="timezone-aware"):
        VirtualClock(datetime(2026, 10, 28))


def test_clock_cannot_move_backwards() -> None:
    """Prevent accidental reversal of logical time."""
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))

    with pytest.raises(ValueError, match="cannot move backwards"):
        clock.advance(timedelta(seconds=-1))
