"""Tests for complete order journey coordination."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, JsonObject, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.journey import OrderJourneySimulator
from food_delivery_lakehouse.simulator.randomness import RandomStreams

EXPECTED_SUCCESSFUL_TYPES = (
    "com.fooddelivery.order.created.v1",
    "com.fooddelivery.payment.initiated.v1",
    "com.fooddelivery.payment.authorized.v1",
    "com.fooddelivery.fulfillment.requested.v1",
    "com.fooddelivery.fulfillment.order-accepted-by-restaurant.v1",
    "com.fooddelivery.payment.captured.v1",
    "com.fooddelivery.order.confirmed.v1",
    "com.fooddelivery.fulfillment.preparation-started.v1",
    "com.fooddelivery.fulfillment.order-ready-for-pickup.v1",
    "com.fooddelivery.delivery.requested.v1",
    "com.fooddelivery.delivery.courier-search-started.v1",
    "com.fooddelivery.delivery.courier-assigned.v1",
    "com.fooddelivery.delivery.courier-arrived-at-restaurant.v1",
    "com.fooddelivery.fulfillment.order-handed-to-courier.v1",
    "com.fooddelivery.delivery.order-picked-up.v1",
    "com.fooddelivery.delivery.started.v1",
    "com.fooddelivery.delivery.order-delivered.v1",
    "com.fooddelivery.order.completed.v1",
)


def _create_simulator(seed: int = 42) -> OrderJourneySimulator:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(seed)
    event_factory = CloudEventFactory(
        clock,
        DeterministicUuid7Generator(clock, streams.get("event_ids")),
    )
    return OrderJourneySimulator(
        order=OrderEventGenerator(event_factory, streams.get("orders")),
        payment=PaymentEventGenerator(event_factory, streams.get("payments")),
        fulfillment=FulfillmentEventGenerator(event_factory, streams.get("fulfillment")),
        delivery=DeliveryEventGenerator(event_factory, streams.get("delivery")),
    )


def _serialize(events: tuple[SimulatedEvent, ...]) -> tuple[JsonObject, ...]:
    """Serialize a journey for deterministic comparison."""
    return tuple(event.to_dict() for event in events)


def test_successful_journey_contains_the_complete_ordered_flow() -> None:
    """Return every successful event in business order."""
    events = _create_simulator().generate_successful_order()

    assert len(events) == 18
    assert tuple(event.event_type for event in events) == EXPECTED_SUCCESSFUL_TYPES
    assert len({event.order_id for event in events}) == 1


def test_successful_journey_preserves_event_causality() -> None:
    """Link each generated consequence to the event that caused it."""
    events = _create_simulator().generate_successful_order()
    expected_parent_indexes = (0, 1, 2, 3, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)

    for event, parent_index in zip(events[1:], expected_parent_indexes, strict=True):
        assert event.causation_id == events[parent_index].event_id


def test_same_seed_generates_the_same_successful_journey() -> None:
    """Reproduce the entire journey from the same seed and start time."""
    first = _serialize(_create_simulator(20261028).generate_successful_order())
    second = _serialize(_create_simulator(20261028).generate_successful_order())

    assert first == second
