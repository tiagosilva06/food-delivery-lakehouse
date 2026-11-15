"""Deterministic injection of transport and data-quality anomalies."""

import random
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, Self

from food_delivery_lakehouse.simulator.events import JsonObject, SimulatedEvent
from food_delivery_lakehouse.simulator.settings import SimulationSettings

type AnomalyKind = Literal["duplicate", "late", "out_of_order", "invalid_schema"]


@dataclass(frozen=True, slots=True)
class AnomalyRates:
    """Define independent anomaly probabilities for emitted events."""

    duplicate: float
    late: float
    out_of_order: float
    invalid_schema: float

    def __post_init__(self) -> None:
        """Keep every probability in the closed interval from zero to one."""
        for name, value in {
            "duplicate": self.duplicate,
            "late": self.late,
            "out_of_order": self.out_of_order,
            "invalid_schema": self.invalid_schema,
        }.items():
            if not 0 <= value <= 1:
                msg = f"{name} must be between 0 and 1"
                raise ValueError(msg)

    @classmethod
    def from_settings(cls, settings: SimulationSettings) -> Self:
        """Read anomaly probabilities from a simulation profile."""
        return cls(
            duplicate=settings.duplicate_event_rate,
            late=settings.late_event_rate,
            out_of_order=settings.out_of_order_rate,
            invalid_schema=settings.invalid_schema_rate,
        )


@dataclass(frozen=True, slots=True)
class EmissionRecord:
    """Hold one publishable payload and simulator-only anomaly labels."""

    payload: JsonObject
    anomalies: frozenset[AnomalyKind] = frozenset()

    def to_dict(self) -> JsonObject:
        """Return an isolated payload ready for JSON serialization."""
        return deepcopy(self.payload)

    def with_anomaly(self, anomaly: AnomalyKind) -> Self:
        """Return a copy labeled with one additional anomaly."""
        return replace(self, anomalies=self.anomalies | {anomaly})


@dataclass(slots=True)
class EventAnomalyInjector:
    """Transform correct journeys into deterministic emission records."""

    random_stream: random.Random

    def inject(
        self,
        events: tuple[SimulatedEvent, ...],
        rates: AnomalyRates,
    ) -> tuple[EmissionRecord, ...]:
        """Apply configured anomalies without mutating domain events."""
        ready: list[EmissionRecord] = []
        delayed: list[EmissionRecord] = []

        for event in events:
            record = EmissionRecord(event.to_dict())
            if self.random_stream.random() < rates.invalid_schema:
                record = self._invalidate(record)

            target = ready
            if self.random_stream.random() < rates.late:
                record = self._delay(record)
                target = delayed
            target.append(record)

            if self.random_stream.random() < rates.duplicate:
                target.append(
                    EmissionRecord(
                        payload=record.to_dict(),
                        anomalies=record.anomalies | {"duplicate"},
                    )
                )

        records = ready + delayed
        self._reorder_adjacent_records(records, rates.out_of_order)
        return tuple(records)

    def _delay(self, record: EmissionRecord) -> EmissionRecord:
        """Move publication several minutes after the business event time."""
        payload = record.to_dict()
        occurred_at = _parse_timestamp(payload["time"], "time")
        delay = timedelta(minutes=self.random_stream.randint(5, 30))
        payload["publishedat"] = _format_timestamp(occurred_at + delay)
        return EmissionRecord(payload, record.anomalies | {"late"})

    @staticmethod
    def _invalidate(record: EmissionRecord) -> EmissionRecord:
        """Remove one required envelope field to force schema quarantine."""
        payload = record.to_dict()
        payload.pop("dataschema", None)
        return EmissionRecord(payload, record.anomalies | {"invalid_schema"})

    def _reorder_adjacent_records(
        self,
        records: list[EmissionRecord],
        rate: float,
    ) -> None:
        """Swap adjacent records to simulate transport reordering."""
        index = 0
        while index + 1 < len(records):
            if self.random_stream.random() < rate:
                first = records[index].with_anomaly("out_of_order")
                second = records[index + 1].with_anomaly("out_of_order")
                records[index], records[index + 1] = second, first
                index += 2
            else:
                index += 1


def _parse_timestamp(value: object, field_name: str) -> datetime:
    """Parse an RFC 3339 timestamp from a serialized event."""
    if not isinstance(value, str):
        msg = f"{field_name} must be str"
        raise ValueError(msg)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_timestamp(value: datetime) -> str:
    """Format an aware timestamp as RFC 3339 UTC."""
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
