"""Tests for deterministic Order confirmation."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _create_confirmed_order(seed: int = 42) -> tuple[SimulatedEvent, ...]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    event_factory = CloudEventFactory(clock, event_ids)
    order_generator = OrderEventGenerator(event_factory, streams.get("orders"))
    payment_generator = PaymentEventGenerator(event_factory, streams.get("payments"))
    fulfillment_generator = FulfillmentEventGenerator(event_factory, streams.get("fulfillment"))

    order_created = order_generator.create_order_created()
    payment_initiated = payment_generator.create_payment_initiated(order_created)
    payment_authorized = payment_generator.create_payment_authorized(payment_initiated)
    fulfillment_requested = fulfillment_generator.create_fulfillment_requested(
        order_created, payment_authorized
    )
    order_accepted = fulfillment_generator.create_order_accepted(fulfillment_requested)
    payment_captured = payment_generator.create_payment_captured(payment_authorized)
    order_confirmed = order_generator.create_order_confirmed(
        order_created,
        payment_captured,
        order_accepted,
    )
    return order_created, payment_captured, order_accepted, order_confirmed


def test_order_confirmation_links_payment_and_fulfillment() -> None:
    """Store both completed prerequisites in the confirmed Order event."""
    order_created, payment_captured, order_accepted, order_confirmed = _create_confirmed_order()

    assert order_confirmed.order_id == order_created.order_id
    assert order_confirmed.aggregate_id == order_created.aggregate_id
    assert order_confirmed.aggregate_version == 2
    assert order_confirmed.causation_id == payment_captured.event_id
    assert order_confirmed.data == {
        "payment_attempt_id": payment_captured.aggregate_id,
        "fulfillment_id": order_accepted.aggregate_id,
    }


def test_same_seed_generates_the_same_confirmed_order() -> None:
    """Repeat the confirmed Order event when deterministic inputs match."""
    first = _create_confirmed_order()[3].to_dict()
    second = _create_confirmed_order()[3].to_dict()

    assert first == second


def test_order_confirmation_rejects_mixed_orders() -> None:
    """Prevent prerequisites from different orders from being combined."""
    first_order, payment_captured, order_accepted, _ = _create_confirmed_order()
    second_acceptance = replace(order_accepted, order_id="order-000000000002")
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(42)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    generator = OrderEventGenerator(
        CloudEventFactory(clock, event_ids),
        streams.get("orders"),
    )

    with pytest.raises(ValueError, match="same order"):
        generator.create_order_confirmed(first_order, payment_captured, second_acceptance)
