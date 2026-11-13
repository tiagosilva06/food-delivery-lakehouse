"""Contract tests for generated Fulfillment events."""

from datetime import UTC, datetime

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams

from .schema_helpers import REPOSITORY_ROOT, build_validator


def _create_generated_fulfillment_events() -> tuple[
    SimulatedEvent,
    SimulatedEvent,
]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(20261028)

    event_ids = DeterministicUuid7Generator(
        clock,
        streams.get("event_ids"),
    )
    event_factory = CloudEventFactory(clock, event_ids)

    order_generator = OrderEventGenerator(
        event_factory,
        streams.get("orders"),
    )
    payment_generator = PaymentEventGenerator(
        event_factory,
        streams.get("payments"),
    )
    fulfillment_generator = FulfillmentEventGenerator(
        event_factory,
        streams.get("fulfillment"),
    )

    order_created = order_generator.create_order_created()

    payment_initiated = payment_generator.create_payment_initiated(order_created)
    payment_authorized = payment_generator.create_payment_authorized(payment_initiated)

    fulfillment_requested = fulfillment_generator.create_fulfillment_requested(
        order_created,
        payment_authorized,
    )
    order_accepted = fulfillment_generator.create_order_accepted(fulfillment_requested)

    return fulfillment_requested, order_accepted


@pytest.mark.parametrize(
    ("event", "schema_name"),
    tuple(
        zip(
            _create_generated_fulfillment_events(),
            (
                "fulfillment-requested",
                "order-accepted-by-restaurant",
            ),
            strict=True,
        )
    ),
)
def test_generated_fulfillment_event_matches_its_schema(
    event: SimulatedEvent,
    schema_name: str,
) -> None:
    """Validate generated Fulfillment events against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/fulfillment/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
