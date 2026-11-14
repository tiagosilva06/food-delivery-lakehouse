"""Contract tests for generated terminal failure journeys."""

import pytest

from food_delivery_lakehouse.simulator.events import SimulatedEvent
from tests.unit.simulator.test_journey import _create_simulator

from .schema_helpers import REPOSITORY_ROOT, build_validator


def _generated_failure_events() -> tuple[tuple[SimulatedEvent, str, str], ...]:
    payment_events = _create_simulator(20261028).generate_payment_failure_order()
    rejection_events = _create_simulator(20261028).generate_restaurant_rejection_order()
    return (
        (payment_events[2], "payment", "payment-authorization-failed"),
        (payment_events[3], "order", "order-failed"),
        (rejection_events[4], "fulfillment", "order-rejected-by-restaurant"),
        (rejection_events[5], "payment", "payment-authorization-voided"),
        (rejection_events[6], "order", "order-cancelled"),
    )


@pytest.mark.parametrize(("event", "domain", "schema_name"), _generated_failure_events())
def test_generated_failure_event_matches_its_schema(
    event: SimulatedEvent,
    domain: str,
    schema_name: str,
) -> None:
    """Validate generated terminal failures against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/{domain}/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
