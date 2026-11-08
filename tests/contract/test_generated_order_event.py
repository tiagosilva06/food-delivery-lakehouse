"""Contract tests for events produced by the real simulator code."""

from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.randomness import RandomStreams

from .schema_helpers import REPOSITORY_ROOT, build_validator


def test_generated_order_created_matches_its_json_schema() -> None:
    """Keep the simulator output aligned with the published OrderCreated contract."""
    clock = VirtualClock(datetime(2026, 10, 28, tzinfo=UTC))
    streams = RandomStreams(20261028)
    event_ids = DeterministicUuid7Generator(clock, streams.get("event_ids"))
    generator = OrderEventGenerator(
        CloudEventFactory(clock, event_ids),
        streams.get("orders"),
    )
    event = generator.create_order_created().to_dict()
    schema_path = REPOSITORY_ROOT / "schemas/order/v1/order-created.schema.json"

    build_validator(schema_path).validate(event)
