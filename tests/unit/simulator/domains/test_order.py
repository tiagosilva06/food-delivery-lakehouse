"""Tests for deterministic Order event generation."""

from datetime import UTC, datetime
from typing import Any, cast

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _build_generator(seed: int = 42) -> OrderEventGenerator:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    return OrderEventGenerator(CloudEventFactory(clock, event_ids), streams.get("orders"))


def test_same_seed_generates_the_same_order() -> None:
    """Repeat business data as well as the technical event envelope."""
    first = _build_generator().create_order_created().to_dict()
    second = _build_generator().create_order_created().to_dict()

    assert first == second


def test_order_amounts_are_derived_from_items() -> None:
    """Keep subtotal and total consistent with item, fee, and discount values."""
    event = _build_generator().create_order_created().to_dict()
    data = cast(dict[str, Any], event["data"])
    items = cast(list[dict[str, Any]], data["items"])

    expected_subtotal = sum(
        cast(int, item["quantity"]) * cast(int, item["unit_price_minor"]) for item in items
    )
    assert data["subtotal_amount_minor"] == expected_subtotal
    assert data["total_amount_minor"] == (
        expected_subtotal
        + cast(int, data["delivery_fee_amount_minor"])
        - cast(int, data["discount_amount_minor"])
    )


def test_consecutive_orders_receive_sequential_business_ids() -> None:
    """Give business entities readable IDs independent from event UUIDs."""
    generator = _build_generator()

    first = generator.create_order_created().to_dict()
    second = generator.create_order_created().to_dict()

    assert first["orderid"] == "order-000000000001"
    assert second["orderid"] == "order-000000000002"


def test_order_created_starts_the_order_aggregate() -> None:
    """Create the first version of the Order aggregate with the order as correlation."""
    event = _build_generator().create_order_created().to_dict()

    assert event["type"] == "com.fooddelivery.order.created.v1"
    assert event["aggregateversion"] == 1
    assert event["aggregateid"] == event["orderid"]
    assert event["correlationid"] == event["orderid"]
