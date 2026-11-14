"""Contract tests for generated courier handoff events."""

import pytest

from food_delivery_lakehouse.simulator.events import SimulatedEvent
from tests.unit.simulator.domains.test_delivery_handoff import _create_handoff_flow

from .schema_helpers import REPOSITORY_ROOT, build_validator


@pytest.mark.parametrize(
    ("event", "domain", "schema_name"),
    tuple(
        zip(
            _create_handoff_flow(20261028)[1:],
            ("fulfillment", "delivery", "delivery"),
            ("order-handed-to-courier", "order-picked-up", "delivery-started"),
            strict=True,
        )
    ),
)
def test_generated_handoff_event_matches_its_schema(
    event: SimulatedEvent,
    domain: str,
    schema_name: str,
) -> None:
    """Validate cross-domain handoff events against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/{domain}/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
