"""Virtual time primitives for reproducible simulations."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class VirtualClock:
    """Maintain an explicit UTC clock that advances only when requested."""

    _current_time: datetime

    def __post_init__(self) -> None:
        """Validate and normalize the initial time to UTC."""
        if self._current_time.tzinfo is None or self._current_time.utcoffset() is None:
            msg = "VirtualClock requires a timezone-aware datetime"
            raise ValueError(msg)
        self._current_time = self._current_time.astimezone(UTC)

    def now(self) -> datetime:
        """Return the current logical time without advancing it."""
        return self._current_time

    def advance(self, duration: timedelta) -> datetime:
        """Advance logical time by a non-negative duration and return the new time."""
        if duration < timedelta(0):
            msg = "VirtualClock cannot move backwards"
            raise ValueError(msg)
        self._current_time += duration
        return self._current_time
