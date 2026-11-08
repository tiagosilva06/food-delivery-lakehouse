"""CloudEvents primitives shared by every simulator domain."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

_DOMAIN_RESOURCES = {
    "order": "orders",
    "payment": "payments",
    "fulfillment": "fulfillments",
    "delivery": "deliveries",
}


def _format_datetime(value: datetime) -> str:
    """Format an aware datetime as an RFC 3339 UTC timestamp."""
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SimulatedEvent:
    """Represent one typed domain event before JSON serialization."""

    event_id: str
    source: str
    event_type: str
    subject: str
    occurred_at: datetime
    data_schema: str
    order_id: str
    correlation_id: str
    causation_id: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    published_at: datetime
    data: JsonObject

    def __post_init__(self) -> None:
        """Reject invalid envelope values before serialization."""
        text_fields = {
            "event_id": self.event_id,
            "source": self.source,
            "event_type": self.event_type,
            "subject": self.subject,
            "data_schema": self.data_schema,
            "order_id": self.order_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
        }
        for name, value in text_fields.items():
            if not value.strip():
                msg = f"{name} must not be empty"
                raise ValueError(msg)
        if self.aggregate_version < 1:
            msg = "aggregate_version must be positive"
            raise ValueError(msg)
        for name, timestamp in {
            "occurred_at": self.occurred_at,
            "published_at": self.published_at,
        }.items():
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                msg = f"{name} must be timezone-aware"
                raise ValueError(msg)

    def to_dict(self) -> JsonObject:
        """Serialize the event to the project's CloudEvents JSON contract."""
        return {
            "specversion": "1.0",
            "id": self.event_id,
            "source": self.source,
            "type": self.event_type,
            "subject": self.subject,
            "time": _format_datetime(self.occurred_at),
            "datacontenttype": "application/json",
            "dataschema": self.data_schema,
            "orderid": self.order_id,
            "correlationid": self.correlation_id,
            "causationid": self.causation_id,
            "aggregatetype": self.aggregate_type,
            "aggregateid": self.aggregate_id,
            "aggregateversion": self.aggregate_version,
            "publishedat": _format_datetime(self.published_at),
            "data": deepcopy(self.data),
        }


@dataclass(frozen=True, slots=True)
class CloudEventFactory:
    """Create consistent CloudEvents envelopes from domain-specific data."""

    clock: VirtualClock
    event_ids: DeterministicUuid7Generator

    def create(
        self,
        *,
        domain: str,
        event_name: str,
        schema_name: str,
        order_id: str,
        causation_id: str,
        aggregate_id: str,
        aggregate_version: int,
        data: JsonObject,
    ) -> SimulatedEvent:
        """Build one event using virtual time and a deterministic event ID."""
        normalized_domain = domain.strip()
        normalized_event_name = event_name.strip()
        normalized_schema_name = schema_name.strip()
        if normalized_domain not in _DOMAIN_RESOURCES:
            msg = f"unsupported event domain: {normalized_domain}"
            raise ValueError(msg)
        if not normalized_event_name:
            msg = "event_name must not be empty"
            raise ValueError(msg)
        if not normalized_schema_name:
            msg = "schema_name must not be empty"
            raise ValueError(msg)

        resource = _DOMAIN_RESOURCES[normalized_domain]
        event_time = self.clock.now()
        return SimulatedEvent(
            event_id=self.event_ids.next_id(),
            source=f"/simulator/{resource}",
            event_type=f"com.fooddelivery.{normalized_domain}.{normalized_event_name}.v1",
            subject=f"{resource}/{aggregate_id}",
            occurred_at=event_time,
            data_schema=(
                "https://food-delivery-lakehouse.local/schemas/"
                f"{normalized_domain}/v1/{normalized_schema_name}.schema.json"
            ),
            order_id=order_id,
            correlation_id=order_id,
            causation_id=causation_id,
            aggregate_type=normalized_domain,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            published_at=event_time,
            data=deepcopy(data),
        )
