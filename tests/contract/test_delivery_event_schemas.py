"""Contract tests for Delivery domain events."""

from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contract.schema_helpers import build_validator, load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas/delivery/v1"
EXAMPLE_DIRECTORY = REPOSITORY_ROOT / "schemas/examples/delivery/v1"

EVENT_CASES = (
    ("delivery-requested", "restaurant_id"),
    ("courier-search-started", "assignment_attempt_id"),
    ("courier-assigned", "courier_id"),
    ("courier-assignment-cancelled", "reason_code"),
    ("courier-arrived-at-restaurant", "courier_id"),
    ("order-picked-up", "courier_id"),
    ("delivery-started", "estimated_delivery_at"),
    ("order-delivered", "confirmation_type"),
    ("courier-assignment-timed-out", "timeout_seconds"),
    ("delivery-failed", "failure_code"),
    ("delivery-cancelled", "reason_code"),
)
EVENT_NAMES = tuple(event_name for event_name, _ in EVENT_CASES)
EVENTS_AFTER_REQUEST = tuple(
    event_name for event_name in EVENT_NAMES if event_name != "delivery-requested"
)


def schema_path(event_name: str) -> Path:
    """Return the schema path for a Delivery event."""
    return SCHEMA_DIRECTORY / f"{event_name}.schema.json"


def example_path(event_name: str) -> Path:
    """Return the valid example path for a Delivery event."""
    return EXAMPLE_DIRECTORY / f"{event_name}.valid.json"


def load_event(event_name: str) -> dict[str, Any]:
    """Load a valid Delivery event example."""
    return load_json(example_path(event_name))


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_valid_delivery_event_is_accepted(event_name: str) -> None:
    """Accept every documented valid Delivery event example."""
    build_validator(schema_path(event_name)).validate(load_event(event_name))


@pytest.mark.parametrize(("event_name", "required_payload_field"), EVENT_CASES)
def test_missing_required_payload_field_is_rejected(
    event_name: str, required_payload_field: str
) -> None:
    """Reject a Delivery event without a required payload field."""
    event = load_event(event_name)
    del event["data"][required_payload_field]

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize("event_name", EVENTS_AFTER_REQUEST)
def test_aggregate_version_one_is_rejected_after_request(event_name: str) -> None:
    """Reserve aggregate version one for DeliveryRequested."""
    event = load_event(event_name)
    event["aggregateversion"] = 1

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


def test_delivery_requested_requires_aggregate_version_one() -> None:
    """Require a new delivery aggregate to start at version one."""
    event = load_event("delivery-requested")
    event["aggregateversion"] = 2

    with pytest.raises(ValidationError):
        build_validator(schema_path("delivery-requested")).validate(event)


def test_invalid_dropoff_coordinate_is_rejected() -> None:
    """Reject a drop-off latitude outside the geographic range."""
    event = load_event("delivery-requested")
    event["data"]["dropoff_location"]["latitude"] = 91

    with pytest.raises(ValidationError):
        build_validator(schema_path("delivery-requested")).validate(event)


@pytest.mark.parametrize(
    ("event_name", "field", "invalid_value"),
    (
        ("delivery-requested", "delivery_deadline_at", "later"),
        ("courier-search-started", "search_radius_meters", 0),
        ("courier-assigned", "estimated_arrival_at", "soon"),
        ("courier-assignment-cancelled", "reason_code", "UNKNOWN_REASON"),
        ("courier-arrived-at-restaurant", "courier_id", ""),
        ("order-picked-up", "assignment_attempt_id", ""),
        ("delivery-started", "estimated_delivery_at", "later"),
        ("order-delivered", "confirmation_type", "UNKNOWN"),
        ("courier-assignment-timed-out", "timeout_seconds", 0),
        ("delivery-failed", "failure_code", "UNKNOWN_ERROR"),
        ("delivery-cancelled", "reason_code", "UNKNOWN_REASON"),
    ),
)
def test_controlled_delivery_values_are_enforced(
    event_name: str, field: str, invalid_value: object
) -> None:
    """Reject values outside the controlled Delivery contract rules."""
    event = load_event(event_name)
    event["data"][field] = invalid_value

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)
