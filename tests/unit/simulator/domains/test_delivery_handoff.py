"""Tests for the handoff between Fulfillment and Delivery."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _create_handoff_flow(seed: int = 42) -> tuple[SimulatedEvent, ...]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)
    event_factory = CloudEventFactory(
        clock,
        DeterministicUuid7Generator(clock, streams.get("event_ids")),
    )
    order_generator = OrderEventGenerator(event_factory, streams.get("orders"))
    payment_generator = PaymentEventGenerator(event_factory, streams.get("payments"))
    fulfillment_generator = FulfillmentEventGenerator(event_factory, streams.get("fulfillment"))
    delivery_generator = DeliveryEventGenerator(event_factory, streams.get("delivery"))

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
    delivery_requested = delivery_generator.create_delivery_requested(order_created, order_ready)
    courier_search = delivery_generator.create_courier_search_started(delivery_requested)
    courier_assigned = delivery_generator.create_courier_assigned(courier_search)
    courier_arrived = delivery_generator.create_courier_arrived_at_restaurant(courier_assigned)
    order_handed = fulfillment_generator.create_order_handed_to_courier(
        order_ready, courier_arrived
    )
    order_picked_up = delivery_generator.create_order_picked_up(courier_arrived, order_handed)
    delivery_started = delivery_generator.create_delivery_started(order_picked_up)
    return courier_arrived, order_handed, order_picked_up, delivery_started


def test_handoff_connects_fulfillment_to_the_assigned_delivery() -> None:
    """Preserve courier and delivery identities across domain boundaries."""
    courier_arrived, order_handed, order_picked_up, _ = _create_handoff_flow()

    assert order_handed.causation_id == courier_arrived.event_id
    assert order_handed.data["delivery_id"] == courier_arrived.aggregate_id
    assert order_handed.data["courier_id"] == courier_arrived.data["courier_id"]
    assert order_picked_up.causation_id == order_handed.event_id
    assert order_picked_up.data["courier_id"] == order_handed.data["courier_id"]


def test_pickup_and_start_continue_the_delivery_aggregate() -> None:
    """Advance the Delivery aggregate without creating a new delivery."""
    courier_arrived, _, order_picked_up, delivery_started = _create_handoff_flow()

    assert order_picked_up.aggregate_id == courier_arrived.aggregate_id
    assert delivery_started.aggregate_id == courier_arrived.aggregate_id
    assert order_picked_up.aggregate_version == 5
    assert delivery_started.aggregate_version == 6
    assert delivery_started.causation_id == order_picked_up.event_id


def test_same_seed_generates_the_same_handoff_flow() -> None:
    """Repeat the cross-domain flow when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_handoff_flow())
    second = tuple(event.to_dict() for event in _create_handoff_flow())

    assert first == second
