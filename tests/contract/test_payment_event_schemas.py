"""Contract tests for Payment domain events."""

from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from tests.contract.schema_helpers import build_validator, load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas/payment/v1"
EXAMPLE_DIRECTORY = REPOSITORY_ROOT / "schemas/examples/payment/v1"

EVENT_CASES = (
    ("payment-initiated", "payment_provider_id"),
    ("payment-authorized", "provider_authorization_id"),
    ("payment-authorization-failed", "failure_code"),
    ("payment-captured", "provider_capture_id"),
    ("payment-authorization-voided", "provider_void_id"),
    ("payment-refund-requested", "refund_id"),
    ("payment-refunded", "provider_refund_id"),
    ("payment-refund-failed", "failure_code"),
)
EVENT_NAMES = tuple(event_name for event_name, _ in EVENT_CASES)
EVENTS_AFTER_INITIATION = tuple(
    event_name for event_name in EVENT_NAMES if event_name != "payment-initiated"
)


def schema_path(event_name: str) -> Path:
    """Return the schema path for a Payment event."""
    return SCHEMA_DIRECTORY / f"{event_name}.schema.json"


def example_path(event_name: str) -> Path:
    """Return the valid example path for a Payment event."""
    return EXAMPLE_DIRECTORY / f"{event_name}.valid.json"


def load_event(event_name: str) -> dict[str, Any]:
    """Load a valid Payment event example."""
    return load_json(example_path(event_name))


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_valid_payment_event_is_accepted(event_name: str) -> None:
    """Accept every documented valid Payment event example."""
    build_validator(schema_path(event_name)).validate(load_event(event_name))


@pytest.mark.parametrize(("event_name", "required_payload_field"), EVENT_CASES)
def test_missing_required_payload_field_is_rejected(
    event_name: str, required_payload_field: str
) -> None:
    """Reject a Payment event without one of its required payload fields."""
    event = load_event(event_name)
    del event["data"][required_payload_field]

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize("event_name", EVENTS_AFTER_INITIATION)
def test_aggregate_version_one_is_rejected_after_initiation(event_name: str) -> None:
    """Reserve aggregate version one for PaymentInitiated."""
    event = load_event(event_name)
    event["aggregateversion"] = 1

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


def test_payment_initiated_requires_aggregate_version_one() -> None:
    """Require a new payment attempt to start at aggregate version one."""
    event = load_event("payment-initiated")
    event["aggregateversion"] = 2

    with pytest.raises(ValidationError):
        build_validator(schema_path("payment-initiated")).validate(event)


@pytest.mark.parametrize("event_name", EVENT_NAMES)
def test_wrong_payment_event_type_is_rejected(event_name: str) -> None:
    """Reject an event type that does not match its Payment contract."""
    event = load_event(event_name)
    event["type"] = "com.fooddelivery.order.created.v1"

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)


@pytest.mark.parametrize(
    ("event_name", "field", "invalid_value"),
    (
        ("payment-initiated", "payment_method", "PIX"),
        ("payment-authorized", "currency", "USD"),
        ("payment-authorization-failed", "failure_code", "UNKNOWN_ERROR"),
        ("payment-captured", "amount_minor", 0),
        ("payment-authorization-voided", "reason_code", "UNKNOWN_REASON"),
        ("payment-refund-requested", "reason_code", "UNKNOWN_REASON"),
        ("payment-refunded", "amount_minor", -1),
        ("payment-refund-failed", "retryable", "yes"),
    ),
)
def test_controlled_payment_values_are_enforced(
    event_name: str, field: str, invalid_value: object
) -> None:
    """Reject values outside the controlled Payment contract rules."""
    event = load_event(event_name)
    event["data"][field] = invalid_value

    with pytest.raises(ValidationError):
        build_validator(schema_path(event_name)).validate(event)
