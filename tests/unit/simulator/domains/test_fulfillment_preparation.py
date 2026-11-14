"""Tests for deterministic restaurant preparation."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _create_ready_order(seed: int = 42) -> tuple[SimulatedEvent, ...]:
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
        order_created, payment_captured, order_accepted
    )
    preparation_started = fulfillment_generator.create_preparation_started(
        order_accepted, order_confirmed
    )
    order_ready = fulfillment_generator.create_order_ready_for_pickup(preparation_started)
    return order_accepted, order_confirmed, preparation_started, order_ready


def test_preparation_starts_after_order_confirmation() -> None:
    """Use the confirmed Order as the cause of restaurant preparation."""
    order_accepted, order_confirmed, preparation_started, _ = _create_ready_order()

    assert preparation_started.causation_id == order_confirmed.event_id
    assert preparation_started.aggregate_id == order_accepted.aggregate_id
    assert preparation_started.aggregate_version == 3
    assert preparation_started.order_id == order_confirmed.order_id


def test_order_becomes_ready_at_its_estimated_time() -> None:
    """Advance virtual time to the estimate before emitting OrderReadyForPickup."""
    _, _, preparation_started, order_ready = _create_ready_order()

    assert preparation_started.data["estimated_ready_at"] == order_ready.to_dict()["time"]
    assert order_ready.aggregate_id == preparation_started.aggregate_id
    assert order_ready.aggregate_version == 4
    assert order_ready.causation_id == preparation_started.event_id
    assert order_ready.data == {}


def test_same_seed_generates_the_same_preparation_flow() -> None:
    """Repeat preparation events when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_ready_order()[2:])
    second = tuple(event.to_dict() for event in _create_ready_order()[2:])

    assert first == second
