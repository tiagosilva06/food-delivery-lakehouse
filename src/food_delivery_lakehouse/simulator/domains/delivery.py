"""Deterministic event generation for the Delivery domain."""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from food_delivery_lakehouse.simulator.events import (
    CloudEventFactory,
    JsonObject,
    SimulatedEvent,
)
from food_delivery_lakehouse.simulator.identifiers import SequenceIdGenerator

_ORDER_CREATED = "com.fooddelivery.order.created.v1"
_ORDER_READY = "com.fooddelivery.fulfillment.order-ready-for-pickup.v1"
_DELIVERY_REQUESTED = "com.fooddelivery.delivery.requested.v1"
_COURIER_SEARCH_STARTED = "com.fooddelivery.delivery.courier-search-started.v1"
_COURIER_ASSIGNED = "com.fooddelivery.delivery.courier-assigned.v1"
_COURIER_ARRIVED = "com.fooddelivery.delivery.courier-arrived-at-restaurant.v1"
_ORDER_HANDED_TO_COURIER = "com.fooddelivery.fulfillment.order-handed-to-courier.v1"
_ORDER_PICKED_UP = "com.fooddelivery.delivery.order-picked-up.v1"
_DELIVERY_STARTED = "com.fooddelivery.delivery.started.v1"


def _require_event_type(event: SimulatedEvent, expected_type: str) -> None:
    """Reject an invalid predecessor in the Delivery lifecycle."""
    if event.event_type != expected_type:
        msg = f"expected predecessor {expected_type}, got {event.event_type}"
        raise ValueError(msg)


def _parse_timestamp(value: object, field_name: str) -> datetime:
    """Parse an RFC 3339 timestamp stored in event data."""
    if not isinstance(value, str):
        msg = f"{field_name} must be str"
        raise ValueError(msg)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_timestamp(value: datetime) -> str:
    """Format a timestamp in the representation expected by the contracts."""
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class DeliveryEventGenerator:
    """Generate events for courier assignment and delivery execution."""

    event_factory: CloudEventFactory
    random_stream: random.Random
    delivery_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("delivery")
    )
    assignment_attempt_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("assignment-attempt")
    )
    courier_ids: SequenceIdGenerator = field(default_factory=lambda: SequenceIdGenerator("courier"))

    def create_delivery_requested(
        self,
        order_created: SimulatedEvent,
        order_ready: SimulatedEvent,
    ) -> SimulatedEvent:
        """Request delivery after the restaurant finishes the order."""
        _require_event_type(order_created, _ORDER_CREATED)
        _require_event_type(order_ready, _ORDER_READY)
        if order_created.order_id != order_ready.order_id:
            msg = "created and ready events must belong to the same order"
            raise ValueError(msg)

        restaurant_id = order_created.data.get("restaurant_id")
        dropoff_location = order_created.data.get("delivery_location")
        if not isinstance(restaurant_id, str):
            msg = "restaurant_id must be str"
            raise ValueError(msg)
        if not isinstance(dropoff_location, dict):
            msg = "delivery_location must be dict"
            raise ValueError(msg)

        self.event_factory.clock.advance(
            timedelta(milliseconds=self.random_stream.randint(100, 500))
        )
        delivery_deadline = self.event_factory.clock.now() + timedelta(minutes=60)
        pickup_location: JsonObject = {
            "latitude": round(self.random_stream.uniform(-23.70, -23.40), 6),
            "longitude": round(self.random_stream.uniform(-46.80, -46.40), 6),
        }
        data: JsonObject = {
            "restaurant_id": restaurant_id,
            "pickup_location": pickup_location,
            "dropoff_location": dict(dropoff_location),
            "delivery_deadline_at": _format_timestamp(delivery_deadline),
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="requested",
            schema_name="delivery-requested",
            order_id=order_created.order_id,
            causation_id=order_ready.event_id,
            aggregate_id=self.delivery_ids.next_id(),
            aggregate_version=1,
            data=data,
        )

    def create_courier_search_started(
        self,
        delivery_requested: SimulatedEvent,
    ) -> SimulatedEvent:
        """Start the first courier assignment attempt."""
        _require_event_type(delivery_requested, _DELIVERY_REQUESTED)

        self.event_factory.clock.advance(
            timedelta(milliseconds=self.random_stream.randint(100, 500))
        )
        assignment_deadline = self.event_factory.clock.now() + timedelta(seconds=90)
        data: JsonObject = {
            "assignment_attempt_id": self.assignment_attempt_ids.next_id(),
            "search_radius_meters": self.random_stream.randint(3_000, 8_000),
            "assignment_deadline_at": _format_timestamp(assignment_deadline),
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="courier-search-started",
            schema_name="courier-search-started",
            order_id=delivery_requested.order_id,
            causation_id=delivery_requested.event_id,
            aggregate_id=delivery_requested.aggregate_id,
            aggregate_version=delivery_requested.aggregate_version + 1,
            data=data,
        )

    def create_courier_assigned(
        self,
        courier_search_started: SimulatedEvent,
    ) -> SimulatedEvent:
        """Assign a courier before the search deadline."""
        _require_event_type(courier_search_started, _COURIER_SEARCH_STARTED)

        assignment_attempt_id = courier_search_started.data.get("assignment_attempt_id")
        if not isinstance(assignment_attempt_id, str):
            msg = "assignment_attempt_id must be str"
            raise ValueError(msg)

        self.event_factory.clock.advance(timedelta(seconds=self.random_stream.randint(5, 45)))
        estimated_arrival = self.event_factory.clock.now() + timedelta(
            minutes=self.random_stream.randint(3, 12)
        )
        data: JsonObject = {
            "assignment_attempt_id": assignment_attempt_id,
            "courier_id": self.courier_ids.next_id(),
            "estimated_arrival_at": _format_timestamp(estimated_arrival),
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="courier-assigned",
            schema_name="courier-assigned",
            order_id=courier_search_started.order_id,
            causation_id=courier_search_started.event_id,
            aggregate_id=courier_search_started.aggregate_id,
            aggregate_version=courier_search_started.aggregate_version + 1,
            data=data,
        )

    def create_courier_arrived_at_restaurant(
        self,
        courier_assigned: SimulatedEvent,
    ) -> SimulatedEvent:
        """Move virtual time to the courier's estimated restaurant arrival."""
        _require_event_type(courier_assigned, _COURIER_ASSIGNED)

        assignment_attempt_id = courier_assigned.data.get("assignment_attempt_id")
        courier_id = courier_assigned.data.get("courier_id")
        if not isinstance(assignment_attempt_id, str):
            msg = "assignment_attempt_id must be str"
            raise ValueError(msg)
        if not isinstance(courier_id, str):
            msg = "courier_id must be str"
            raise ValueError(msg)

        estimated_arrival = _parse_timestamp(
            courier_assigned.data.get("estimated_arrival_at"),
            "estimated_arrival_at",
        )
        remaining_time = estimated_arrival - self.event_factory.clock.now()
        if remaining_time < timedelta(0):
            msg = "estimated_arrival_at cannot be before the current virtual time"
            raise ValueError(msg)
        self.event_factory.clock.advance(remaining_time)

        data: JsonObject = {
            "assignment_attempt_id": assignment_attempt_id,
            "courier_id": courier_id,
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="courier-arrived-at-restaurant",
            schema_name="courier-arrived-at-restaurant",
            order_id=courier_assigned.order_id,
            causation_id=courier_assigned.event_id,
            aggregate_id=courier_assigned.aggregate_id,
            aggregate_version=courier_assigned.aggregate_version + 1,
            data=data,
        )

    def create_order_picked_up(
        self,
        courier_arrived: SimulatedEvent,
        order_handed_to_courier: SimulatedEvent,
    ) -> SimulatedEvent:
        """Record the courier pickup after the restaurant handoff."""
        _require_event_type(courier_arrived, _COURIER_ARRIVED)
        _require_event_type(order_handed_to_courier, _ORDER_HANDED_TO_COURIER)
        if courier_arrived.order_id != order_handed_to_courier.order_id:
            msg = "courier arrival and handoff must belong to the same order"
            raise ValueError(msg)
        if courier_arrived.aggregate_id != order_handed_to_courier.data.get("delivery_id"):
            msg = "handoff must reference the same delivery"
            raise ValueError(msg)

        assignment_attempt_id = courier_arrived.data.get("assignment_attempt_id")
        courier_id = courier_arrived.data.get("courier_id")
        if not isinstance(assignment_attempt_id, str):
            msg = "assignment_attempt_id must be str"
            raise ValueError(msg)
        if not isinstance(courier_id, str):
            msg = "courier_id must be str"
            raise ValueError(msg)
        if courier_id != order_handed_to_courier.data.get("courier_id"):
            msg = "handoff must reference the assigned courier"
            raise ValueError(msg)

        self.event_factory.clock.advance(
            timedelta(milliseconds=self.random_stream.randint(100, 500))
        )
        data: JsonObject = {
            "assignment_attempt_id": assignment_attempt_id,
            "courier_id": courier_id,
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="order-picked-up",
            schema_name="order-picked-up",
            order_id=courier_arrived.order_id,
            causation_id=order_handed_to_courier.event_id,
            aggregate_id=courier_arrived.aggregate_id,
            aggregate_version=courier_arrived.aggregate_version + 1,
            data=data,
        )

    def create_delivery_started(
        self,
        order_picked_up: SimulatedEvent,
    ) -> SimulatedEvent:
        """Start transit from the restaurant to the customer."""
        _require_event_type(order_picked_up, _ORDER_PICKED_UP)

        assignment_attempt_id = order_picked_up.data.get("assignment_attempt_id")
        courier_id = order_picked_up.data.get("courier_id")
        if not isinstance(assignment_attempt_id, str):
            msg = "assignment_attempt_id must be str"
            raise ValueError(msg)
        if not isinstance(courier_id, str):
            msg = "courier_id must be str"
            raise ValueError(msg)

        self.event_factory.clock.advance(
            timedelta(milliseconds=self.random_stream.randint(100, 500))
        )
        estimated_delivery = self.event_factory.clock.now() + timedelta(
            minutes=self.random_stream.randint(10, 45)
        )
        data: JsonObject = {
            "assignment_attempt_id": assignment_attempt_id,
            "courier_id": courier_id,
            "estimated_delivery_at": _format_timestamp(estimated_delivery),
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="started",
            schema_name="delivery-started",
            order_id=order_picked_up.order_id,
            causation_id=order_picked_up.event_id,
            aggregate_id=order_picked_up.aggregate_id,
            aggregate_version=order_picked_up.aggregate_version + 1,
            data=data,
        )

    def create_order_delivered(
        self,
        delivery_started: SimulatedEvent,
    ) -> SimulatedEvent:
        """Complete a successful delivery at its estimated arrival time."""
        _require_event_type(delivery_started, _DELIVERY_STARTED)

        assignment_attempt_id = delivery_started.data.get("assignment_attempt_id")
        courier_id = delivery_started.data.get("courier_id")
        if not isinstance(assignment_attempt_id, str):
            msg = "assignment_attempt_id must be str"
            raise ValueError(msg)
        if not isinstance(courier_id, str):
            msg = "courier_id must be str"
            raise ValueError(msg)

        estimated_delivery = _parse_timestamp(
            delivery_started.data.get("estimated_delivery_at"),
            "estimated_delivery_at",
        )
        remaining_time = estimated_delivery - self.event_factory.clock.now()
        if remaining_time < timedelta(0):
            msg = "estimated_delivery_at cannot be before the current virtual time"
            raise ValueError(msg)
        self.event_factory.clock.advance(remaining_time)

        data: JsonObject = {
            "assignment_attempt_id": assignment_attempt_id,
            "courier_id": courier_id,
            "confirmation_type": self.random_stream.choice(("CUSTOMER_RECEIVED", "LEFT_AT_DOOR")),
        }
        return self.event_factory.create(
            domain="delivery",
            event_name="order-delivered",
            schema_name="order-delivered",
            order_id=delivery_started.order_id,
            causation_id=delivery_started.event_id,
            aggregate_id=delivery_started.aggregate_id,
            aggregate_version=delivery_started.aggregate_version + 1,
            data=data,
        )
