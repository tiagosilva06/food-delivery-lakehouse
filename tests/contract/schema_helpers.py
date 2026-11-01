"""Shared helpers for JSON Schema contract tests."""

import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMON_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/common/v1/cloud-event.schema.json"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from the repository."""
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def build_validator(schema_path: Path) -> Draft202012Validator:
    """Build a validator with the shared CloudEvent schema registered."""
    common_schema = load_json(COMMON_SCHEMA_PATH)
    event_schema = load_json(schema_path)
    registry = Registry().with_resource(common_schema["$id"], Resource.from_contents(common_schema))
    Draft202012Validator.check_schema(event_schema)
    return Draft202012Validator(
        event_schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
