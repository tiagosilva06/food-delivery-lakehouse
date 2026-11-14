"""Contract test for generated OrderConfirmed events."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams

from .schema_helpers import REPOSITORY_ROOT, build_validator


def test_generated_order_confirmed_matches_its_json_schema() -> None:
    """Validate the generated OrderConfirmed event against its contract."""
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(20261028)
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
        order_created,
        payment_captured,
        order_accepted,
    )
    schema_path = REPOSITORY_ROOT / "schemas/order/v1/order-confirmed.schema.json"

    build_validator(schema_path).validate(order_confirmed.to_dict())
