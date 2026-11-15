"""Tests for profile-driven simulator execution."""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from food_delivery_lakehouse.simulator.runner import SimulationRunner
from food_delivery_lakehouse.simulator.settings import SimulationSettings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEV_PROFILE = REPOSITORY_ROOT / "config/simulator/dev.toml"


def _success_only_settings(order_count: int = 5) -> SimulationSettings:
    settings = SimulationSettings.from_toml(DEV_PROFILE)
    return replace(
        settings,
        order_count=order_count,
        duration_hours=1,
        successful_order_rate=1.0,
        payment_failure_rate=0.0,
        restaurant_rejection_rate=0.0,
        courier_timeout_rate=0.0,
        delivery_failure_rate=0.0,
        duplicate_event_rate=0.0,
        late_event_rate=0.0,
        out_of_order_rate=0.0,
        invalid_schema_rate=0.0,
    )


def test_run_is_lazy_and_generates_unique_orders() -> None:
    """Yield records incrementally while preserving unique business IDs."""
    settings = _success_only_settings()
    output = SimulationRunner(settings).run()

    assert isinstance(output, Iterator)
    records = list(output)
    created = [
        record
        for record in records
        if record.payload["type"] == "com.fooddelivery.order.created.v1"
    ]
    assert len(created) == settings.order_count
    assert len({str(record.payload["orderid"]) for record in created}) == settings.order_count


def test_order_creation_is_distributed_across_logical_duration() -> None:
    """Start orders throughout the configured window instead of sequentially."""
    settings = _success_only_settings()
    records = list(SimulationRunner(settings).run())
    created_times = [
        str(record.payload["time"])
        for record in records
        if record.payload["type"] == "com.fooddelivery.order.created.v1"
    ]

    assert created_times[0] == "2026-10-28T00:00:00.000Z"
    assert created_times[-1] == "2026-10-28T00:48:00.000Z"
    assert len(set(created_times)) == settings.order_count


def test_records_from_concurrent_orders_are_time_merged() -> None:
    """Interleave concurrent journeys by publication time."""
    settings = _success_only_settings(order_count=10)
    records = list(SimulationRunner(settings).run())
    published = [str(record.payload["publishedat"]) for record in records]

    assert published == sorted(published)


def test_payment_failure_profile_stops_every_order_early() -> None:
    """Dispatch every order to the selected failure scenario."""
    settings = replace(
        _success_only_settings(order_count=4),
        successful_order_rate=0.0,
        payment_failure_rate=1.0,
    )
    records = list(SimulationRunner(settings).run())

    assert len(records) == 4 * settings.order_count
    assert all("fulfillment" not in str(record.payload["type"]) for record in records)


def test_same_profile_reproduces_the_same_emission_stream() -> None:
    """Repeat scenario selection, event data, and anomalies from one profile."""
    settings = replace(
        SimulationSettings.from_toml(DEV_PROFILE),
        order_count=20,
        duration_hours=1,
    )
    first = tuple(SimulationRunner(settings).run())
    second = tuple(SimulationRunner(settings).run())

    assert first == second
