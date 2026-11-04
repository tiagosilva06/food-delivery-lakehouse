"""Contract tests for Fulfillment domain events."""

from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contract.schema_helpers import build_validator, load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas/fulfillment/v1"
EXAMPLE_DIRECTORY = REPOSITORY_ROOT / "schemas/examples/fulfillment/v1"

EVENT_NAMES = (
    "fulfillment-requested",
    "order-accepted-by-restaurant",
    "order-rejected-by-restaurant",
    "restaurant-acceptance-timed-out",
    "preparation-started",
    "order-ready-for-pickup",
    "order-handed-to-courier",
    "fulfillment-cancelled",
)
REQUIRED_PAYLOAD_CASES = (
    ("fulfillment-requested", "restaurant_id"),
    ("order-accepted-by-restaurant", "estimated_preparation_seconds"),
    ("order-rejected-by-restaurant", "reason_code"),
    ("restaurant-acceptance-timed-out", "timeout_seconds"),
    ("preparation-started", "estimated_ready_at"),
    ("order-handed-to-courier", "delivery_id"),
    ("fulfillment-cancelled", "reason_code"),
)
EVENTS_AFTER_REQUEST = tuple(
    event_name for event_name in EVENT_NAMES if event_name != "fulfillment-requested"
)


def schema_path(event_name: str) -> Path:
    """Return the schema path for a Fulfillment event."""
    return SCHEMA_DIRECTORY / f"{event_name}.schema.json"


def example_path(event_name: str) -> Path:
    """Return the valid example path for a Fulfillment event."""
    return EXAMPLE_DIRECTORY / f"{event_name}.valid.json"


def load_event(event_name: str) -> dict[str, Any]:
    """Load a valid Fulfillment event example."""
    return load_json(example_path(event_name))


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_valid_fulfillment_event_is_accepted(event_name: str) -> None:
    """Accept every documented valid Fulfillment event example."""
    build_validator(schema_path(event_name)).validate(load_event(event_name))


@pytest.mark.parametrize(("event_name", "required_payload_field"), REQUIRED_PAYLOAD_CASES)
def test_missing_required_payload_field_is_rejected(
    event_name: str, required_payload_field: str
) -> None:
    """Reject a Fulfillment event without a required payload field."""
    event = load_event(event_name)
    del event["data"][required_payload_field]

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize("event_name", EVENTS_AFTER_REQUEST)
def test_aggregate_version_one_is_rejected_after_request(event_name: str) -> None:
    """Reserve aggregate version one for FulfillmentRequested."""
    event = load_event(event_name)
    event["aggregateversion"] = 1

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


def test_fulfillment_requested_requires_aggregate_version_one() -> None:
    """Require a new fulfillment aggregate to start at version one."""
    event = load_event("fulfillment-requested")
    event["aggregateversion"] = 2

    with pytest.raises(ValidationError):
        build_validator(schema_path("fulfillment-requested")).validate(event)


def test_order_ready_for_pickup_requires_empty_payload() -> None:
    """Reject invented payload fields when the event fact is self-contained."""
    event = load_event("order-ready-for-pickup")
    event["data"]["ready"] = True

    with pytest.raises(ValidationError):
        build_validator(schema_path("order-ready-for-pickup")).validate(event)


@pytest.mark.parametrize(
    ("event_name", "field", "invalid_value"),
    (
        ("fulfillment-requested", "acceptance_deadline_at", "tomorrow"),
        ("order-accepted-by-restaurant", "estimated_preparation_seconds", 30),
        ("order-rejected-by-restaurant", "reason_code", "UNKNOWN_REASON"),
        ("restaurant-acceptance-timed-out", "timeout_seconds", 0),
        ("preparation-started", "estimated_ready_at", "soon"),
        ("order-handed-to-courier", "courier_id", ""),
        ("fulfillment-cancelled", "reason_code", "UNKNOWN_REASON"),
    ),
)
def test_controlled_fulfillment_values_are_enforced(
    event_name: str, field: str, invalid_value: object
) -> None:
    """Reject values outside the controlled Fulfillment contract rules."""
    event = load_event(event_name)
    event["data"][field] = invalid_value

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)
