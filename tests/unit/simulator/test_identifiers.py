"""Tests for deterministic simulator identifiers."""

from datetime import UTC, datetime, timedelta
from uuid import RFC_4122, UUID

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.identifiers import (
    DeterministicUuid7Generator,
    SequenceIdGenerator,
)
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def test_sequence_ids_are_readable_and_repeatable() -> None:
    """Generate predictable identifiers for business entities."""
    generator = SequenceIdGenerator("order", width=6)

    assert [generator.next_id() for _ in range(3)] == [
        "order-000001",
        "order-000002",
        "order-000003",
    ]


def test_uuid7_values_repeat_with_the_same_clock_and_seed() -> None:
    """Generate the same event identifiers for an identical run."""
    start = datetime(2026, 10, 28, tzinfo=UTC)
    first = DeterministicUuid7Generator(VirtualClock(start), RandomStreams(42).get("event_ids"))
    second = DeterministicUuid7Generator(VirtualClock(start), RandomStreams(42).get("event_ids"))

    assert [first.next_id() for _ in range(3)] == [second.next_id() for _ in range(3)]


def test_uuid7_values_are_valid_and_time_ordered() -> None:
    """Create RFC 4122 UUIDv7 values ordered by virtual timestamp."""
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    generator = DeterministicUuid7Generator(clock, RandomStreams(42).get("event_ids"))

    first = UUID(generator.next_id())
    clock.advance(timedelta(milliseconds=1))
    second = UUID(generator.next_id())

    assert first.version == 7
    assert first.variant == RFC_4122
    assert first.int < second.int
