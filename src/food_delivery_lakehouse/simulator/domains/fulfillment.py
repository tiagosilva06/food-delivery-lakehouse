"""Deterministic event generation for the Fulfillment domain."""

import random
from dataclasses import dataclass, field
from datetime import timedelta

from food_delivery_lakehouse.simulator.events import (
    CloudEventFactory,
    JsonObject,
    SimulatedEvent,
)
from food_delivery_lakehouse.simulator.identifiers import SequenceIdGenerator

_ORDER_CREATED = "com.fooddelivery.order.created.v1"
_PAYMENT_AUTHORIZED = "com.fooddelivery.payment.authorized.v1"
_FULFILLMENT_REQUESTED = "com.fooddelivery.fulfillment.requested.v1"


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
