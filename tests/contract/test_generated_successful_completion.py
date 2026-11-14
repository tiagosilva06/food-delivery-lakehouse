"""Contract tests for generated successful completion events."""

import pytest

from food_delivery_lakehouse.simulator.events import SimulatedEvent
from tests.unit.simulator.domains.test_successful_completion import _create_completed_flow

from .schema_helpers import REPOSITORY_ROOT, build_validator


@pytest.mark.parametrize(
    ("event", "domain", "schema_name"),
    tuple(
        zip(
            _create_completed_flow(20261028)[2:],
            ("delivery", "order"),
            ("order-delivered", "order-completed"),
            strict=True,
        )
    ),
)
def test_generated_completion_event_matches_its_schema(
    event: SimulatedEvent,
    domain: str,
    schema_name: str,
) -> None:
    """Validate final successful events against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/{domain}/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
