"""Tests for simulator execution profile settings."""

from dataclasses import replace
from datetime import UTC
from pathlib import Path

import pytest

from food_delivery_lakehouse.simulator.settings import SimulationSettings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROFILE_DIRECTORY = REPOSITORY_ROOT / "config/simulator"


@pytest.mark.parametrize(
    ("profile_name", "order_count", "peak_events_per_second"),
    (
        ("dev", 100, 50),
        ("validation", 10_000, 500),
        ("benchmark", 1_000_000, 1_500),
    ),
)
def test_profiles_load_expected_scale(
    profile_name: str, order_count: int, peak_events_per_second: int
) -> None:
    """Load each profile with its intended volume and peak throughput."""
    settings = SimulationSettings.from_toml(PROFILE_DIRECTORY / f"{profile_name}.toml")

    assert settings.profile_name == profile_name
    assert settings.order_count == order_count
    assert settings.target_peak_events_per_second == peak_events_per_second
    assert settings.logical_start_at.tzinfo == UTC


def test_invalid_anomaly_rate_is_rejected() -> None:
    """Keep anomaly probabilities within the valid range."""
    settings = SimulationSettings.from_toml(PROFILE_DIRECTORY / "dev.toml")

    with pytest.raises(ValueError, match="between 0 and 1"):
        replace(settings, duplicate_event_rate=1.01)
