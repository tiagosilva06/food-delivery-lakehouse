"""Deterministic event generation for the Order domain."""

import random
from dataclasses import dataclass, field
from datetime import timedelta

from food_delivery_lakehouse.simulator.events import (
    CloudEventFactory,
    JsonObject,
    JsonValue,
    SimulatedEvent,
)
from food_delivery_lakehouse.simulator.identifiers import SequenceIdGenerator

_ORDER_CREATED = "com.fooddelivery.order.created.v1"
_PAYMENT_CAPTURED = "com.fooddelivery.payment.captured.v1"
_ORDER_ACCEPTED = "com.fooddelivery.fulfillment.order-accepted-by-restaurant.v1"
_ORDER_CONFIRMED = "com.fooddelivery.order.confirmed.v1"
_ORDER_DELIVERED = "com.fooddelivery.delivery.order-delivered.v1"


def _require_event_type(event: SimulatedEvent, expected_type: str) -> None:
    """Reject an invalid predecessor in the Order lifecycle."""
    if event.event_type != expected_type:
        msg = f"expected predecessor {expected_type}, got {event.event_type}"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class OrderItem:
    """Represent one priced item in an order."""

    order_item_id: str
    menu_item_id: str
    quantity: int
    unit_price_minor: int

    def __post_init__(self) -> None:
        """Keep quantities and monetary values positive."""
        if self.quantity < 1:
            msg = "quantity must be positive"
            raise ValueError(msg)
        if self.unit_price_minor < 1:
            msg = "unit_price_minor must be positive"
            raise ValueError(msg)

    @property
    def line_amount_minor(self) -> int:
        """Calculate the item total in minor currency units."""
        return self.quantity * self.unit_price_minor

    def to_dict(self) -> JsonObject:
        """Serialize the item to the OrderCreated contract shape."""
        return {
            "order_item_id": self.order_item_id,
            "menu_item_id": self.menu_item_id,
            "quantity": self.quantity,
            "unit_price_minor": self.unit_price_minor,
            "line_amount_minor": self.line_amount_minor,
        }


@dataclass(frozen=True, slots=True)
class DeliveryLocation:
    """Represent the customer drop-off location."""

    delivery_zone_id: str
    latitude: float
    longitude: float

    def to_dict(self) -> JsonObject:
        """Serialize the location to the OrderCreated contract shape."""
        return {
            "delivery_zone_id": self.delivery_zone_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass(slots=True)
class OrderEventGenerator:
    """Generate deterministic Order domain events."""

    event_factory: CloudEventFactory
    random_stream: random.Random
    order_ids: SequenceIdGenerator = field(default_factory=lambda: SequenceIdGenerator("order"))
    order_item_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("order-item")
    )
    command_ids: SequenceIdGenerator = field(default_factory=lambda: SequenceIdGenerator("command"))

    def create_order_created(self) -> SimulatedEvent:
        """Create the first event of a successful order journey."""
        order_id = self.order_ids.next_id()
        command_id = self.command_ids.next_id()
        items = self._create_items()
        subtotal_amount_minor = sum(item.line_amount_minor for item in items)
        delivery_fee_amount_minor = self.random_stream.choice((0, 399, 599, 799))
        maximum_discount = subtotal_amount_minor + delivery_fee_amount_minor - 1
        discount_options = tuple(
            value for value in (0, 300, 500, 800, 1000) if value <= maximum_discount
        )
        discount_amount_minor = self.random_stream.choice(discount_options)
        total_amount_minor = (
            subtotal_amount_minor + delivery_fee_amount_minor - discount_amount_minor
        )
        location = self._create_delivery_location()
        serialized_items: list[JsonValue] = [item.to_dict() for item in items]

        data: JsonObject = {
            "customer_id": f"customer-{self.random_stream.randint(1, 100_000):06d}",
            "restaurant_id": f"restaurant-{self.random_stream.randint(1, 10_000):06d}",
            "delivery_location": location.to_dict(),
            "items": serialized_items,
            "subtotal_amount_minor": subtotal_amount_minor,
            "delivery_fee_amount_minor": delivery_fee_amount_minor,
            "discount_amount_minor": discount_amount_minor,
            "total_amount_minor": total_amount_minor,
            "currency": "BRL",
        }
        return self.event_factory.create(
            domain="order",
            event_name="created",
            schema_name="order-created",
            order_id=order_id,
            causation_id=command_id,
            aggregate_id=order_id,
            aggregate_version=1,
            data=data,
        )

    def create_order_confirmed(
        self,
        order_created: SimulatedEvent,
        payment_captured: SimulatedEvent,
        order_accepted: SimulatedEvent,
    ) -> SimulatedEvent:
        """Confirm an accepted order after its payment is captured."""
        _require_event_type(order_created, _ORDER_CREATED)
        _require_event_type(payment_captured, _PAYMENT_CAPTURED)
        _require_event_type(order_accepted, _ORDER_ACCEPTED)

        order_ids = {
            order_created.order_id,
            payment_captured.order_id,
            order_accepted.order_id,
        }
        if len(order_ids) != 1:
            msg = "order, payment, and fulfillment must belong to the same order"
            raise ValueError(msg)

        delay_ms = self.random_stream.randint(100, 500)
        self.event_factory.clock.advance(timedelta(milliseconds=delay_ms))

        data: JsonObject = {
            "payment_attempt_id": payment_captured.aggregate_id,
            "fulfillment_id": order_accepted.aggregate_id,
        }
        return self.event_factory.create(
            domain="order",
            event_name="confirmed",
            schema_name="order-confirmed",
            order_id=order_created.order_id,
            causation_id=payment_captured.event_id,
            aggregate_id=order_created.aggregate_id,
            aggregate_version=order_created.aggregate_version + 1,
            data=data,
        )

    def create_order_completed(
        self,
        order_confirmed: SimulatedEvent,
        order_delivered: SimulatedEvent,
    ) -> SimulatedEvent:
        """Complete an order after its successful delivery."""
        _require_event_type(order_confirmed, _ORDER_CONFIRMED)
        _require_event_type(order_delivered, _ORDER_DELIVERED)
        if order_confirmed.order_id != order_delivered.order_id:
            msg = "confirmed order and delivery must belong to the same order"
            raise ValueError(msg)

        self.event_factory.clock.advance(
            timedelta(milliseconds=self.random_stream.randint(100, 500))
        )
        data: JsonObject = {"delivery_id": order_delivered.aggregate_id}
        return self.event_factory.create(
            domain="order",
            event_name="completed",
            schema_name="order-completed",
            order_id=order_confirmed.order_id,
            causation_id=order_delivered.event_id,
            aggregate_id=order_confirmed.aggregate_id,
            aggregate_version=order_confirmed.aggregate_version + 1,
            data=data,
        )

    def _create_items(self) -> list[OrderItem]:
        """Generate a small deterministic basket of priced items."""
        return [
            OrderItem(
                order_item_id=self.order_item_ids.next_id(),
                menu_item_id=f"menu-item-{self.random_stream.randint(1, 50_000):06d}",
                quantity=self.random_stream.randint(1, 3),
                unit_price_minor=self.random_stream.randint(800, 7_500),
            )
            for _ in range(self.random_stream.randint(1, 4))
        ]

    def _create_delivery_location(self) -> DeliveryLocation:
        """Generate one deterministic delivery point in the São Paulo region."""
        return DeliveryLocation(
            delivery_zone_id=f"zone-{self.random_stream.randint(1, 20):02d}",
            latitude=round(self.random_stream.uniform(-23.70, -23.40), 6),
            longitude=round(self.random_stream.uniform(-46.80, -46.40), 6),
        )
