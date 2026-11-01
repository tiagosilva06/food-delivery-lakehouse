"""Contract tests for Order events emitted after OrderCreated."""

from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contract.schema_helpers import build_validator, load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas/order/v1"
EXAMPLE_DIRECTORY = REPOSITORY_ROOT / "schemas/examples/order/v1"

EVENT_CASES = (
    ("order-confirmed", "payment_attempt_id"),
    ("order-cancellation-requested", "requested_by"),
    ("order-cancelled", "requested_by"),
    ("order-failed", "failure_stage"),
    ("order-completed", "delivery_id"),
)
EVENT_NAMES = tuple(event_name for event_name, _ in EVENT_CASES)


def schema_path(event_name: str) -> Path:
    """Return the schema path for an event name."""
    return SCHEMA_DIRECTORY / f"{event_name}.schema.json"


def example_path(event_name: str) -> Path:
    """Return the valid example path for an event name."""
    return EXAMPLE_DIRECTORY / f"{event_name}.valid.json"


def load_event(event_name: str) -> dict[str, Any]:
    """Load a valid event example."""
    return load_json(example_path(event_name))


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_valid_order_event_is_accepted(event_name: str) -> None:
    """Accept every documented valid Order event example."""
    build_validator(schema_path(event_name)).validate(load_event(event_name))


@pytest.mark.parametrize(("event_name", "required_payload_field"), EVENT_CASES)
def test_missing_required_payload_field_is_rejected(
    event_name: str, required_payload_field: str
) -> None:
    """Reject an Order event without one of its required payload fields."""
    event = load_event(event_name)
    del event["data"][required_payload_field]

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_aggregate_version_one_is_rejected(event_name: str) -> None:
    """Reserve aggregate version one for OrderCreated."""
    event = load_event(event_name)
    event["aggregateversion"] = 1

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize(
    ("event_name", "field", "invalid_value"),
    (
        ("order-cancellation-requested", "requested_by", "COURIER"),
        ("order-cancelled", "reason_code", "free form reason"),
        ("order-failed", "failure_stage", "RESTAURANT"),
    ),
)
def test_controlled_order_values_are_enforced(
    event_name: str, field: str, invalid_value: str
) -> None:
    """Reject values outside the controlled Order vocabularies."""
    event = load_event(event_name)
    event["data"][field] = invalid_value

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)
