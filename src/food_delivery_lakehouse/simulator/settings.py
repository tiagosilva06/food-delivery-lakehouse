"""Configuration loading and validation for simulator execution profiles."""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Self, cast


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    """Validated settings shared by every simulator profile."""

    profile_name: str
    seed: int
    logical_start_at: datetime
    duration_hours: int
    order_count: int
    target_peak_events_per_second: int
    duplicate_event_rate: float
    late_event_rate: float
    out_of_order_rate: float
    invalid_schema_rate: float

    def __post_init__(self) -> None:
        """Validate profile values before a simulation can start."""
        if not self.profile_name.strip():
            msg = "profile_name must not be empty"
            raise ValueError(msg)
        if self.seed < 0:
            msg = "seed must be non-negative"
            raise ValueError(msg)
        if self.logical_start_at.tzinfo is None or self.logical_start_at.utcoffset() is None:
            msg = "logical_start_at must be timezone-aware"
            raise ValueError(msg)
        if self.duration_hours < 1:
            msg = "duration_hours must be positive"
            raise ValueError(msg)
        if self.order_count < 1:
            msg = "order_count must be positive"
            raise ValueError(msg)
        if self.target_peak_events_per_second < 1:
            msg = "target_peak_events_per_second must be positive"
            raise ValueError(msg)

        rates = {
            "duplicate_event_rate": self.duplicate_event_rate,
            "late_event_rate": self.late_event_rate,
            "out_of_order_rate": self.out_of_order_rate,
            "invalid_schema_rate": self.invalid_schema_rate,
        }
        for name, value in rates.items():
            if not 0 <= value <= 1:
                msg = f"{name} must be between 0 and 1"
                raise ValueError(msg)

    @classmethod
    def from_toml(cls, path: Path) -> Self:
        """Load and validate a simulation profile from a TOML file."""
        with path.open("rb") as profile_file:
            raw = tomllib.load(profile_file)

        simulation = cast(dict[str, Any], raw["simulation"])
        throughput = cast(dict[str, Any], raw["throughput"])
        anomalies = cast(dict[str, Any], raw["anomalies"])
        logical_start_at = datetime.fromisoformat(
            cast(str, simulation["logical_start_at"]).replace("Z", "+00:00")
        )

        return cls(
            profile_name=cast(str, simulation["profile_name"]),
            seed=cast(int, simulation["seed"]),
            logical_start_at=logical_start_at,
            duration_hours=cast(int, simulation["duration_hours"]),
            order_count=cast(int, simulation["order_count"]),
            target_peak_events_per_second=cast(int, throughput["target_peak_events_per_second"]),
            duplicate_event_rate=cast(float, anomalies["duplicate_event_rate"]),
            late_event_rate=cast(float, anomalies["late_event_rate"]),
            out_of_order_rate=cast(float, anomalies["out_of_order_rate"]),
            invalid_schema_rate=cast(float, anomalies["invalid_schema_rate"]),
        )
