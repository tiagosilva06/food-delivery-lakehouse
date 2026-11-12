"""Contract tests for Payment events produced by the real simulator code."""

from datetime import UTC, datetime

import pytest

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams

from .schema_helpers import REPOSITORY_ROOT, build_validator


def _create_generated_payment_events() -> tuple[SimulatedEvent, ...]:
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(20261028)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    event_factory = CloudEventFactory(clock, event_ids)
    order_created = OrderEventGenerator(event_factory, streams.get("orders")).create_order_created()
    payment_generator = PaymentEventGenerator(event_factory, streams.get("payments"))
    initiated = payment_generator.create_payment_initiated(order_created)
    authorized = payment_generator.create_payment_authorized(initiated)
    captured = payment_generator.create_payment_captured(authorized)
    return initiated, authorized, captured


@pytest.mark.parametrize(
    ("event", "schema_name"),
    tuple(
        zip(
            _create_generated_payment_events(),
            ("payment-initiated", "payment-authorized", "payment-captured"),
            strict=True,
        )
    ),
)
def test_generated_payment_event_matches_its_json_schema(
    event: SimulatedEvent, schema_name: str
) -> None:
    """Keep each generated Payment event aligned with its published contract."""
    schema_path = REPOSITORY_ROOT / f"schemas/payment/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
