"""Tests for deterministic courier assignment and restaurant arrival."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams


def _create_delivery_flow(seed: int = 42) -> tuple[SimulatedEvent, ...]:
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
    courier_search_started = delivery_generator.create_courier_search_started(delivery_requested)
    courier_assigned = delivery_generator.create_courier_assigned(courier_search_started)
    courier_arrived = delivery_generator.create_courier_arrived_at_restaurant(courier_assigned)
    return delivery_requested, courier_search_started, courier_assigned, courier_arrived


def test_delivery_request_starts_a_new_delivery_aggregate() -> None:
    """Create a Delivery aggregate connected to the ready order."""
    delivery_requested, _, _, _ = _create_delivery_flow()

    assert delivery_requested.aggregate_id == "delivery-000000000001"
    assert delivery_requested.aggregate_version == 1
    assert delivery_requested.data["restaurant_id"]
    assert delivery_requested.data["dropoff_location"]


def test_assignment_data_is_preserved_until_restaurant_arrival() -> None:
    """Keep assignment and courier identities throughout the same delivery."""
    requested, search, assigned, arrived = _create_delivery_flow()

    assert {event.aggregate_id for event in (requested, search, assigned, arrived)} == {
        requested.aggregate_id
    }
    assert search.data["assignment_attempt_id"] == assigned.data["assignment_attempt_id"]
    assert assigned.data["assignment_attempt_id"] == arrived.data["assignment_attempt_id"]
    assert assigned.data["courier_id"] == arrived.data["courier_id"]
    assert [event.aggregate_version for event in (requested, search, assigned, arrived)] == [
        1,
        2,
        3,
        4,
    ]


def test_courier_arrives_at_the_estimated_time() -> None:
    """Advance virtual time exactly to the estimated restaurant arrival."""
    _, _, assigned, arrived = _create_delivery_flow()

    assert assigned.data["estimated_arrival_at"] == arrived.to_dict()["time"]


def test_same_seed_generates_the_same_delivery_flow() -> None:
    """Repeat delivery events when deterministic inputs match."""
    first = tuple(event.to_dict() for event in _create_delivery_flow())
    second = tuple(event.to_dict() for event in _create_delivery_flow())

    assert first == second
