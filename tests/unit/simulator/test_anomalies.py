"""Tests for deterministic technical anomaly injection."""

from datetime import datetime

from food_delivery_lakehouse.simulator.anomalies import (
    AnomalyRates,
    EmissionRecord,
    EventAnomalyInjector,
)
from food_delivery_lakehouse.simulator.events import SimulatedEvent
from food_delivery_lakehouse.simulator.randomness import RandomStreams

from .test_journey import _create_simulator

ZERO_RATES = AnomalyRates(duplicate=0, late=0, out_of_order=0, invalid_schema=0)


def _inject(
    rates: AnomalyRates,
    seed: int = 42,
) -> tuple[tuple[SimulatedEvent, ...], tuple[EmissionRecord, ...]]:
    events = _create_simulator(seed).generate_successful_order()
    injector = EventAnomalyInjector(RandomStreams(seed).get("anomalies"))
    return events, injector.inject(events, rates)


def test_zero_rates_preserve_every_valid_event() -> None:
    """Keep payload count and order unchanged when anomalies are disabled."""
    events, records = _inject(ZERO_RATES)

    assert tuple(record.payload for record in records) == tuple(event.to_dict() for event in events)
    assert all(not record.anomalies for record in records)


def test_duplicate_rate_repeats_the_same_event_identity() -> None:
    """Emit an exact additional copy for every selected event."""
    events, records = _inject(AnomalyRates(duplicate=1, late=0, out_of_order=0, invalid_schema=0))

    assert len(records) == len(events) * 2
    for original, duplicate in zip(records[::2], records[1::2], strict=True):
        assert original.payload == duplicate.payload
        assert duplicate.anomalies == frozenset({"duplicate"})


def test_late_rate_updates_publication_time_and_defers_records() -> None:
    """Preserve event time while publishing selected records later."""
    _, records = _inject(AnomalyRates(duplicate=0, late=1, out_of_order=0, invalid_schema=0))

    assert all(record.anomalies == frozenset({"late"}) for record in records)
    for record in records:
        occurred_at = datetime.fromisoformat(str(record.payload["time"]).replace("Z", "+00:00"))
        published_at = datetime.fromisoformat(
            str(record.payload["publishedat"]).replace("Z", "+00:00")
        )
        assert published_at > occurred_at


def test_out_of_order_rate_swaps_adjacent_events() -> None:
    """Change transport order without changing event payloads."""
    events, records = _inject(AnomalyRates(duplicate=0, late=0, out_of_order=1, invalid_schema=0))

    original_ids = tuple(event.event_id for event in events)
    emitted_ids = tuple(str(record.payload["id"]) for record in records)
    assert emitted_ids != original_ids
    assert emitted_ids[:2] == original_ids[1::-1]
    assert all("out_of_order" in record.anomalies for record in records)


def test_invalid_schema_rate_removes_a_required_field() -> None:
    """Create payloads that schema validation must send to quarantine."""
    _, records = _inject(AnomalyRates(duplicate=0, late=0, out_of_order=0, invalid_schema=1))

    assert all("dataschema" not in record.payload for record in records)
    assert all(record.anomalies == frozenset({"invalid_schema"}) for record in records)


def test_same_seed_reproduces_the_same_anomalies() -> None:
    """Repeat anomaly selection and payload mutations from the same seed."""
    rates = AnomalyRates(duplicate=0.2, late=0.2, out_of_order=0.2, invalid_schema=0.2)
    _, first = _inject(rates, 20261028)
    _, second = _inject(rates, 20261028)

    assert first == second
