"""Contract tests for generated delivery failure journeys."""

import pytest

from food_delivery_lakehouse.simulator.events import SimulatedEvent
from tests.unit.simulator.test_journey import _create_simulator

from .schema_helpers import REPOSITORY_ROOT, build_validator


def _generated_delivery_failures() -> tuple[tuple[SimulatedEvent, str, str], ...]:
    timeout = _create_simulator(20261028).generate_courier_timeout_order()
    failed = _create_simulator(20261028).generate_delivery_failure_order()
    return (
        (timeout[-5], "delivery", "courier-assignment-timed-out"),
        (timeout[-4], "delivery", "delivery-cancelled"),
        (timeout[-3], "payment", "payment-refund-requested"),
        (timeout[-2], "payment", "payment-refunded"),
        (timeout[-1], "order", "order-failed"),
        (failed[-4], "delivery", "delivery-failed"),
        (failed[-3], "payment", "payment-refund-requested"),
        (failed[-2], "payment", "payment-refunded"),
        (failed[-1], "order", "order-failed"),
    )


@pytest.mark.parametrize(("event", "domain", "schema_name"), _generated_delivery_failures())
def test_generated_delivery_failure_matches_its_schema(
    event: SimulatedEvent,
    domain: str,
    schema_name: str,
) -> None:
    """Validate delivery failures and refunds against their contracts."""
    schema_path = REPOSITORY_ROOT / f"schemas/{domain}/v1/{schema_name}.schema.json"

    build_validator(schema_path).validate(event.to_dict())
