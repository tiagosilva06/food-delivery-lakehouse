"""Deterministic event generation for the Payment domain."""

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
_PAYMENT_INITIATED = "com.fooddelivery.payment.initiated.v1"
_PAYMENT_AUTHORIZED = "com.fooddelivery.payment.authorized.v1"


def _require_event_type(event: SimulatedEvent, expected_type: str) -> None:
    """Reject an invalid predecessor in the payment lifecycle."""
    if event.event_type != expected_type:
        msg = f"expected predecessor {expected_type}, got {event.event_type}"
        raise ValueError(msg)


def _require_data_value(event: SimulatedEvent, field_name: str, expected_type: type) -> JsonValue:
    """Read one required payload value with a runtime type check."""
    value = event.data.get(field_name)
    if not isinstance(value, expected_type) or isinstance(value, bool):
        msg = f"{field_name} must be {expected_type.__name__}"
        raise ValueError(msg)
    return value


@dataclass(slots=True)
class PaymentEventGenerator:
    """Generate the successful lifecycle of one payment attempt."""

    event_factory: CloudEventFactory
    random_stream: random.Random
    payment_attempt_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("payment-attempt")
    )
    authorization_ids: SequenceIdGenerator = field(
        default_factory=lambda: SequenceIdGenerator("authorization")
    )
    capture_ids: SequenceIdGenerator = field(default_factory=lambda: SequenceIdGenerator("capture"))

    def create_payment_initiated(self, order_created: SimulatedEvent) -> SimulatedEvent:
        """Start a card payment using the order total and currency."""
        _require_event_type(order_created, _ORDER_CREATED)
        amount_minor = _require_data_value(order_created, "total_amount_minor", int)
        currency = _require_data_value(order_created, "currency", str)
        self._advance_clock(100, 500)
        payment_attempt_id = self.payment_attempt_ids.next_id()
        data: JsonObject = {
            "payment_provider_id": self.random_stream.choice(
                ("payment-provider-01", "payment-provider-02")
            ),
            "payment_method": "CARD",
            "amount_minor": amount_minor,
            "currency": currency,
        }
        return self.event_factory.create(
            domain="payment",
            event_name="initiated",
            schema_name="payment-initiated",
            order_id=order_created.order_id,
            causation_id=order_created.event_id,
            aggregate_id=payment_attempt_id,
            aggregate_version=1,
            data=data,
        )

    def create_payment_authorized(self, payment_initiated: SimulatedEvent) -> SimulatedEvent:
        """Authorize the full value of an initiated payment attempt."""
        _require_event_type(payment_initiated, _PAYMENT_INITIATED)
        amount_minor = _require_data_value(payment_initiated, "amount_minor", int)
        currency = _require_data_value(payment_initiated, "currency", str)
        self._advance_clock(500, 2_500)
        data: JsonObject = {
            "provider_authorization_id": self.authorization_ids.next_id(),
            "amount_minor": amount_minor,
            "currency": currency,
        }
        return self.event_factory.create(
            domain="payment",
            event_name="authorized",
            schema_name="payment-authorized",
            order_id=payment_initiated.order_id,
            causation_id=payment_initiated.event_id,
            aggregate_id=payment_initiated.aggregate_id,
            aggregate_version=payment_initiated.aggregate_version + 1,
            data=data,
        )

    def create_payment_captured(self, payment_authorized: SimulatedEvent) -> SimulatedEvent:
        """Capture the full value of an authorized payment attempt."""
        _require_event_type(payment_authorized, _PAYMENT_AUTHORIZED)
        amount_minor = _require_data_value(payment_authorized, "amount_minor", int)
        currency = _require_data_value(payment_authorized, "currency", str)
        self._advance_clock(500, 1_500)
        data: JsonObject = {
            "provider_capture_id": self.capture_ids.next_id(),
            "amount_minor": amount_minor,
            "currency": currency,
        }
        return self.event_factory.create(
            domain="payment",
            event_name="captured",
            schema_name="payment-captured",
            order_id=payment_authorized.order_id,
            causation_id=payment_authorized.event_id,
            aggregate_id=payment_authorized.aggregate_id,
            aggregate_version=payment_authorized.aggregate_version + 1,
            data=data,
        )

    def _advance_clock(self, minimum_ms: int, maximum_ms: int) -> None:
        """Advance logical time by a deterministic processing delay."""
        delay_ms = self.random_stream.randint(minimum_ms, maximum_ms)
        self.event_factory.clock.advance(timedelta(milliseconds=delay_ms))
