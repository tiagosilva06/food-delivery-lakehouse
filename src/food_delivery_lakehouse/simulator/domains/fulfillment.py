"""Deterministic event generation for the Fulfillment domain."""

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
_PAYMENT_AUTHORIZED = "com.fooddelivery.payment.authorized.v1"
_FULFILLMENT_REQUESTED = "com.fooddelivery.fulfillment.requested.v1"
_ORDER_ACCEPTED = "com.fooddelivery.fulfillment.order-accepted-by-restaurant.v1"
_ORDER_CONFIRMED = "com.fooddelivery.order.confirmed.v1"
_PREPARATION_STARTED = "com.fooddelivery.fulfillment.preparation-started.v1"
_ORDER_READY = "com.fooddelivery.fulfillment.order-ready-for-pickup.v1"
_COURIER_ARRIVED = "com.fooddelivery.delivery.courier-arrived-at-restaurant.v1"


@dataclass(slots=True)
class FulfillmentEventGenerator:
    """Generate events for restaurant order processing."""

    event_factory: CloudEventFactory
    random_stream: random.Random
    fulfillment_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("fulfillment")
    )

    def create_fulfillment_requested(
        self,
        order_created: SimulatedEvent,
        payment_authorized: SimulatedEvent,
    ) -> SimulatedEvent:
        """Request the restaurant to process an authorized order."""
        if order_created.event_type != _ORDER_CREATED:
            msg = f"expected {_ORDER_CREATED}, got {order_created.event_type}"
            raise ValueError(msg)

        if payment_authorized.event_type != _PAYMENT_AUTHORIZED:
            msg = f"expected {_PAYMENT_AUTHORIZED}, got {payment_authorized.event_type}"
            raise ValueError(msg)

        if order_created.order_id != payment_authorized.order_id:
            msg = "order and payment must belong to the same order"
            raise ValueError(msg)

        restaurant_id = order_created.data.get("restaurant_id")
        if not isinstance(restaurant_id, str):
            msg = "restaurant_id must be str"
            raise ValueError(msg)

        delay_ms = self.random_stream.randint(100, 500)
        self.event_factory.clock.advance(timedelta(milliseconds=delay_ms))

        acceptance_deadline = self.event_factory.clock.now() + timedelta(minutes=2)

        data: JsonObject = {
            "restaurant_id": restaurant_id,
            "acceptance_deadline_at": (
                acceptance_deadline.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            ),
        }

        return self.event_factory.create(
            domain="fulfillment",
            event_name="requested",
            schema_name="fulfillment-requested",
            order_id=order_created.order_id,
            causation_id=payment_authorized.event_id,
            aggregate_id=self.fulfillment_ids.next_id(),
            aggregate_version=1,
            data=data,
        )

    def create_order_accepted(
        self,
        fulfillment_requested: SimulatedEvent,
    ) -> SimulatedEvent:
        """Accept a fulfillment request on behalf of the restaurant."""
        if fulfillment_requested.event_type != _FULFILLMENT_REQUESTED:
            msg = f"expected {_FULFILLMENT_REQUESTED}, got {fulfillment_requested.event_type}"
            raise ValueError(msg)

        response_seconds = self.random_stream.randint(5, 60)
        self.event_factory.clock.advance(timedelta(seconds=response_seconds))

        estimated_preparation_seconds = self.random_stream.randint(10, 40) * 60

        data: JsonObject = {
            "estimated_preparation_seconds": estimated_preparation_seconds,
        }

        return self.event_factory.create(
            domain="fulfillment",
            event_name="order-accepted-by-restaurant",
            schema_name="order-accepted-by-restaurant",
            order_id=fulfillment_requested.order_id,
            causation_id=fulfillment_requested.event_id,
            aggregate_id=fulfillment_requested.aggregate_id,
            aggregate_version=fulfillment_requested.aggregate_version + 1,
            data=data,
        )

    def create_preparation_started(
        self,
        order_accepted: SimulatedEvent,
        order_confirmed: SimulatedEvent,
    ) -> SimulatedEvent:
        """Start restaurant preparation after the order is confirmed."""
        if order_accepted.event_type != _ORDER_ACCEPTED:
            msg = f"expected {_ORDER_ACCEPTED}, got {order_accepted.event_type}"
            raise ValueError(msg)
        if order_confirmed.event_type != _ORDER_CONFIRMED:
            msg = f"expected {_ORDER_CONFIRMED}, got {order_confirmed.event_type}"
            raise ValueError(msg)
        if order_accepted.order_id != order_confirmed.order_id:
            msg = "acceptance and confirmation must belong to the same order"
            raise ValueError(msg)

        estimated_seconds = order_accepted.data.get("estimated_preparation_seconds")
        if not isinstance(estimated_seconds, int) or isinstance(estimated_seconds, bool):
            msg = "estimated_preparation_seconds must be int"
            raise ValueError(msg)

        delay_ms = self.random_stream.randint(100, 500)
        self.event_factory.clock.advance(timedelta(milliseconds=delay_ms))
        estimated_ready_at = self.event_factory.clock.now() + timedelta(seconds=estimated_seconds)
        data: JsonObject = {
            "estimated_ready_at": (
                estimated_ready_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            ),
        }
        return self.event_factory.create(
            domain="fulfillment",
            event_name="preparation-started",
            schema_name="preparation-started",
            order_id=order_accepted.order_id,
            causation_id=order_confirmed.event_id,
            aggregate_id=order_accepted.aggregate_id,
            aggregate_version=order_accepted.aggregate_version + 1,
            data=data,
        )

    def create_order_ready_for_pickup(
        self,
        preparation_started: SimulatedEvent,
    ) -> SimulatedEvent:
        """Finish preparation at the deterministic estimated ready time."""
        if preparation_started.event_type != _PREPARATION_STARTED:
            msg = f"expected {_PREPARATION_STARTED}, got {preparation_started.event_type}"
            raise ValueError(msg)

        estimated_ready_value = preparation_started.data.get("estimated_ready_at")
        if not isinstance(estimated_ready_value, str):
            msg = "estimated_ready_at must be str"
            raise ValueError(msg)
        estimated_ready_at = datetime.fromisoformat(estimated_ready_value.replace("Z", "+00:00"))
        remaining_time = estimated_ready_at - self.event_factory.clock.now()
        if remaining_time < timedelta(0):
            msg = "estimated_ready_at cannot be before the current virtual time"
            raise ValueError(msg)
        self.event_factory.clock.advance(remaining_time)

        return self.event_factory.create(
            domain="fulfillment",
            event_name="order-ready-for-pickup",
            schema_name="order-ready-for-pickup",
            order_id=preparation_started.order_id,
            causation_id=preparation_started.event_id,
            aggregate_id=preparation_started.aggregate_id,
            aggregate_version=preparation_started.aggregate_version + 1,
            data={},
        )

    def create_order_handed_to_courier(
        self,
        order_ready: SimulatedEvent,
        courier_arrived: SimulatedEvent,
    ) -> SimulatedEvent:
        """Hand a ready order to the courier waiting at the restaurant."""
        if order_ready.event_type != _ORDER_READY:
            msg = f"expected {_ORDER_READY}, got {order_ready.event_type}"
            raise ValueError(msg)
        if courier_arrived.event_type != _COURIER_ARRIVED:
            msg = f"expected {_COURIER_ARRIVED}, got {courier_arrived.event_type}"
            raise ValueError(msg)
        if order_ready.order_id != courier_arrived.order_id:
            msg = "ready order and courier arrival must belong to the same order"
            raise ValueError(msg)

        courier_id = courier_arrived.data.get("courier_id")
        if not isinstance(courier_id, str):
            msg = "courier_id must be str"
            raise ValueError(msg)

        self.event_factory.clock.advance(timedelta(minutes=self.random_stream.randint(1, 5)))
        data: JsonObject = {
            "delivery_id": courier_arrived.aggregate_id,
            "courier_id": courier_id,
        }
        return self.event_factory.create(
            domain="fulfillment",
            event_name="order-handed-to-courier",
            schema_name="order-handed-to-courier",
            order_id=order_ready.order_id,
            causation_id=courier_arrived.event_id,
            aggregate_id=order_ready.aggregate_id,
            aggregate_version=order_ready.aggregate_version + 1,
            data=data,
        )
