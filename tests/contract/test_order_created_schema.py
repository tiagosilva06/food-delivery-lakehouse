"""Contract tests for the OrderCreated event."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from tests.contract.schema_helpers import build_validator, load_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORDER_CREATED_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/order/v1/order-created.schema.json"
VALID_EVENT_PATH = REPOSITORY_ROOT / "schemas/examples/order/v1/order-created.valid.json"
INVALID_EVENT_PATH = REPOSITORY_ROOT / "schemas/examples/order/v1/order-created.invalid.json"


@pytest.fixture
def validator() -> Draft202012Validator:
    """Provide the OrderCreated contract validator."""
    return build_validator(ORDER_CREATED_SCHEMA_PATH)


@pytest.fixture
def valid_event() -> dict[str, Any]:
    """Provide a fresh valid OrderCreated event for every test."""
    return load_json(VALID_EVENT_PATH)


def test_valid_order_created_event_is_accepted(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Accept an event that follows both the envelope and payload contracts."""
    validator.validate(valid_event)


def test_invalid_example_is_rejected(validator: Draft202012Validator) -> None:
    """Reject the documented invalid event example."""
    with pytest.raises(ValidationError):
        validator.validate(load_json(INVALID_EVENT_PATH))


def test_missing_envelope_field_is_rejected(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Reject an event without a required CloudEvent attribute."""
    del valid_event["orderid"]

    with pytest.raises(ValidationError):
        validator.validate(valid_event)


def test_wrong_event_type_is_rejected(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Reject a different event type presented as OrderCreated."""
    valid_event["type"] = "com.fooddelivery.payment.authorized.v1"

    with pytest.raises(ValidationError):
        validator.validate(valid_event)


def test_unknown_payload_field_is_rejected(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Reject payload fields that are not part of the published contract."""
    valid_event["data"]["unknown_field"] = "unexpected"

    with pytest.raises(ValidationError):
        validator.validate(valid_event)


def test_invalid_coordinates_are_rejected(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Reject a delivery latitude outside the geographic range."""
    valid_event["data"]["delivery_location"]["latitude"] = 91

    with pytest.raises(ValidationError):
        validator.validate(valid_event)


def test_arithmetic_consistency_is_left_to_business_validation(
    validator: Draft202012Validator, valid_event: dict[str, Any]
) -> None:
    """Keep cross-field amount calculations outside structural validation."""
    structurally_valid_event = deepcopy(valid_event)
    structurally_valid_event["data"]["total_amount_minor"] = 9999

    validator.validate(structurally_valid_event)
