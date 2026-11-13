"""Tests for deterministic Fulfillment event generation."""

from datetime import UTC, datetime

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _build_generators(
    seed: int = 42,
) -> tuple[
    OrderEventGenerator,
    PaymentEventGenerator,
    FulfillmentEventGenerator,
]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)

    event_ids = DeterministicUuid7Generator(
        clock,
        streams.get("event_ids"),
    )
    event_factory = CloudEventFactory(clock, event_ids)

    return (
        OrderEventGenerator(
            event_factory,
            streams.get("orders"),
        ),
        PaymentEventGenerator(
            event_factory,
            streams.get("payments"),
        ),
        FulfillmentEventGenerator(
            event_factory,
            streams.get("fulfillment"),
        ),
    )


def _create_accepted_fulfillment(
    seed: int = 42,
) -> tuple[SimulatedEvent, SimulatedEvent, SimulatedEvent]:
    (
        order_generator,
        payment_generator,
        fulfillment_generator,
    ) = _build_generators(seed)

    order_created = order_generator.create_order_created()

    payment_initiated = payment_generator.create_payment_initiated(order_created)
    payment_authorized = payment_generator.create_payment_authorized(payment_initiated)

    fulfillment_requested = fulfillment_generator.create_fulfillment_requested(
        order_created,
        payment_authorized,
    )
    order_accepted = fulfillment_generator.create_order_accepted(fulfillment_requested)

    return (
        order_created,
        fulfillment_requested,
        order_accepted,
    )


def test_same_seed_generates_the_same_fulfillment() -> None:
    """Repeat Fulfillment events when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_accepted_fulfillment())
    second = tuple(event.to_dict() for event in _create_accepted_fulfillment())

    assert first == second


def test_fulfillment_preserves_order_and_restaurant() -> None:
    """Connect the restaurant request to the original order."""
    order_created, requested, accepted = _create_accepted_fulfillment()

    assert requested.order_id == order_created.order_id
    assert accepted.order_id == order_created.order_id
    assert requested.data["restaurant_id"] == order_created.data["restaurant_id"]


def test_fulfillment_versions_and_causation_are_correct() -> None:
    """Keep both events in the same Fulfillment aggregate."""
    _, requested, accepted = _create_accepted_fulfillment()

    assert requested.aggregate_version == 1
    assert accepted.aggregate_version == 2
    assert requested.aggregate_id == accepted.aggregate_id
    assert accepted.causation_id == requested.event_id


def test_restaurant_acceptance_has_valid_preparation_time() -> None:
    """Generate a preparation estimate between 10 and 40 minutes."""
    _, requested, accepted = _create_accepted_fulfillment()
    estimated_seconds = accepted.data["estimated_preparation_seconds"]

    assert isinstance(estimated_seconds, int)
    assert 600 <= estimated_seconds <= 2400
    assert estimated_seconds % 60 == 0
    assert requested.occurred_at < accepted.occurred_at


def test_acceptance_rejects_the_wrong_predecessor() -> None:
    """Prevent restaurant acceptance without a Fulfillment request."""
    order_generator, _, fulfillment_generator = _build_generators()
    order_created = order_generator.create_order_created()

    with pytest.raises(ValueError, match="expected"):
        fulfillment_generator.create_order_accepted(order_created)
