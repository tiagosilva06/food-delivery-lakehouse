"""Tests for successful delivery and order completion."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _create_completed_flow(seed: int = 42) -> tuple[SimulatedEvent, ...]:
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
    order_delivered = delivery_generator.create_order_delivered(delivery_started)
    order_completed = order_generator.create_order_completed(order_confirmed, order_delivered)
    return order_confirmed, delivery_started, order_delivered, order_completed


def test_delivery_finishes_at_its_estimated_time() -> None:
    """Move virtual time to the estimate before emitting OrderDelivered."""
    _, delivery_started, order_delivered, _ = _create_completed_flow()

    assert delivery_started.data["estimated_delivery_at"] == order_delivered.to_dict()["time"]
    assert order_delivered.aggregate_id == delivery_started.aggregate_id
    assert order_delivered.aggregate_version == 7
    assert order_delivered.data["confirmation_type"] in {
        "CUSTOMER_RECEIVED",
        "LEFT_AT_DOOR",
    }


def test_delivered_order_completes_the_order_aggregate() -> None:
    """Connect the final Delivery event back to the original Order."""
    order_confirmed, _, order_delivered, order_completed = _create_completed_flow()

    assert order_completed.aggregate_id == order_confirmed.aggregate_id
    assert order_completed.aggregate_version == 3
    assert order_completed.causation_id == order_delivered.event_id
    assert order_completed.data["delivery_id"] == order_delivered.aggregate_id


def test_same_seed_generates_the_same_completed_flow() -> None:
    """Repeat completion events when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_completed_flow())
    second = tuple(event.to_dict() for event in _create_completed_flow())

    assert first == second
