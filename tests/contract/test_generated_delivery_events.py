"""Contract tests for generated Delivery events."""

import pytest

from food_delivery_lakehouse.simulator.events import SimulatedEvent
from tests.unit.simulator.domains.test_delivery import _create_delivery_flow

from .schema_helpers import REPOSITORY_ROOT, build_validator


@pytest.mark.parametrize(
    ("event", "schema_name"),
    tuple(
        zip(
            _create_delivery_flow(20261028),
            (
                "delivery-requested",
                "courier-search-started",
                "courier-assigned",
                "courier-arrived-at-restaurant",
            ),
            strict=True,
        )
    ),
)
def test_generated_delivery_event_matches_its_schema(
    event: SimulatedEvent,
    schema_name: str,
) -> None:
    """Validate generated Delivery events against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/delivery/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
