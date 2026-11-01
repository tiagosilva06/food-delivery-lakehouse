"""Contract tests for the OrderCreated event."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMON_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/common/v1/cloud-event.schema.json"
ORDER_CREATED_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/order/v1/order-created.schema.json"
VALID_EVENT_PATH = REPOSITORY_ROOT / "schemas/examples/order/v1/order-created.valid.json"
INVALID_EVENT_PATH = REPOSITORY_ROOT / "schemas/examples/order/v1/order-created.invalid.json"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from the repository."""
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def build_validator() -> Draft202012Validator:
    """Build a validator with the shared CloudEvent schema registered."""
    common_schema = load_json(COMMON_SCHEMA_PATH)
    order_created_schema = load_json(ORDER_CREATED_SCHEMA_PATH)
    registry = Registry().with_resource(common_schema["$id"], Resource.from_contents(common_schema))
    Draft202012Validator.check_schema(order_created_schema)
    return Draft202012Validator(
        order_created_schema,
        registry=registry,
        format_checker=FormatChecker(),
    )


@pytest.fixture
def validator() -> Draft202012Validator:
    """Provide the OrderCreated contract validator."""
    return build_validator()


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
