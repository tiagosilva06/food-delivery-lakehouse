"""Tests for the simulator CloudEvents primitives."""

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.events import CloudEventFactory, JsonObject
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _build_factory(seed: int = 42) -> tuple[VirtualClock, CloudEventFactory]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    event_ids = DeterministicUuid7Generator(clock, RandomStreams(seed).get("event_ids"))
    return clock, CloudEventFactory(clock, event_ids)


def _create_order_event(factory: CloudEventFactory, version: int = 1) -> JsonObject:
    return factory.create(
        domain="order",
        event_name="created",
        schema_name="order-created",
        order_id="order-000001",
        causation_id="command-000001",
        aggregate_id="order-000001",
        aggregate_version=version,
        data={"currency": "BRL"},
    ).to_dict()


def test_same_seed_clock_and_input_create_the_same_event() -> None:
    """Repeat the complete envelope when all deterministic inputs match."""
    _, first_factory = _build_factory()
    _, second_factory = _build_factory()

    assert _create_order_event(first_factory) == _create_order_event(second_factory)


def test_factory_builds_the_expected_order_envelope() -> None:
    """Derive common CloudEvents fields instead of repeating them per domain."""
    _, factory = _build_factory()

    event = _create_order_event(factory)

    assert event["source"] == "/simulator/orders"
    assert event["type"] == "com.fooddelivery.order.created.v1"
    assert event["subject"] == "orders/order-000001"
    assert event["correlationid"] == "order-000001"
    assert event["aggregateversion"] == 1
    assert event["time"] == "2026-10-28T00:00:00.000Z"
    assert event["publishedat"] == event["time"]


def test_advancing_virtual_time_changes_the_next_event() -> None:
    """Use virtual time in both the envelope timestamp and UUIDv7."""
    clock, factory = _build_factory()
    first = _create_order_event(factory)
    clock.advance(timedelta(milliseconds=1))
    second = _create_order_event(factory)

    assert first["id"] != second["id"]
    assert cast(str, first["time"]) < cast(str, second["time"])


def test_factory_rejects_non_positive_aggregate_version() -> None:
    """Prevent events that cannot belong to a valid aggregate history."""
    _, factory = _build_factory()

    with pytest.raises(ValueError, match="aggregate_version must be positive"):
        _create_order_event(factory, version=0)
