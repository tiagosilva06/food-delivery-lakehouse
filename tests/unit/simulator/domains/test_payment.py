"""Tests for deterministic Payment event generation."""

from datetime import UTC, datetime

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, JsonObject, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _build_generators(seed: int = 42) -> tuple[OrderEventGenerator, PaymentEventGenerator]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    event_factory = CloudEventFactory(clock, event_ids)
    return (
        OrderEventGenerator(event_factory, streams.get("orders")),
        PaymentEventGenerator(event_factory, streams.get("payments")),
    )


def _create_successful_payment(seed: int = 42) -> tuple[SimulatedEvent, ...]:
    order_generator, payment_generator = _build_generators(seed)
    order_created = order_generator.create_order_created()
    payment_initiated = payment_generator.create_payment_initiated(order_created)
    payment_authorized = payment_generator.create_payment_authorized(payment_initiated)
    payment_captured = payment_generator.create_payment_captured(payment_authorized)
    return order_created, payment_initiated, payment_authorized, payment_captured


def test_same_seed_generates_the_same_payment_sequence() -> None:
    """Repeat all successful payment events when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_successful_payment())
    second = tuple(event.to_dict() for event in _create_successful_payment())

    assert first == second


def test_payment_events_preserve_order_amount_and_currency() -> None:
    """Carry the order total unchanged through authorization and capture."""
    order_created, *payment_events = _create_successful_payment()
    order_data: JsonObject = order_created.data

    for event in payment_events:
        assert event.order_id == order_created.order_id
        assert event.data["amount_minor"] == order_data["total_amount_minor"]
        assert event.data["currency"] == order_data["currency"]


def test_payment_versions_and_causation_form_one_chain() -> None:
    """Link every payment transition to its direct predecessor."""
    order_created, initiated, authorized, captured = _create_successful_payment()

    assert [
        initiated.aggregate_version,
        authorized.aggregate_version,
        captured.aggregate_version,
    ] == [
        1,
        2,
        3,
    ]
    assert initiated.aggregate_id == authorized.aggregate_id == captured.aggregate_id
    assert initiated.causation_id == order_created.event_id
    assert authorized.causation_id == initiated.event_id
    assert captured.causation_id == authorized.event_id


def test_payment_events_have_distinct_ids_and_increasing_times() -> None:
    """Advance virtual time between different payment facts."""
    _, initiated, authorized, captured = _create_successful_payment()
    payment_events = (initiated, authorized, captured)

    assert len({event.event_id for event in payment_events}) == 3
    assert [event.occurred_at for event in payment_events] == sorted(
        event.occurred_at for event in payment_events
    )
    assert len({event.occurred_at for event in payment_events}) == 3


def test_payment_transition_rejects_the_wrong_predecessor() -> None:
    """Prevent authorization from skipping PaymentInitiated."""
    order_generator, payment_generator = _build_generators()
    order_created = order_generator.create_order_created()

    with pytest.raises(ValueError, match="expected predecessor"):
        payment_generator.create_payment_authorized(order_created)
