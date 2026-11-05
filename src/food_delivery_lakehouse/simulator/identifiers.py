"""Reproducible identifier generators used by the simulator."""

import random
from dataclasses import dataclass, field
from uuid import UUID

from food_delivery_lakehouse.simulator.clock import VirtualClock


@dataclass(slots=True)
class SequenceIdGenerator:
    """Generate deterministic, readable business identifiers."""

    prefix: str
    width: int = 12
    start: int = 1
    _next_value: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate identifier settings and initialize the counter."""
        self.prefix = self.prefix.strip()
        if not self.prefix:
            msg = "prefix must not be empty"
            raise ValueError(msg)
        if self.width < 1:
            msg = "width must be positive"
            raise ValueError(msg)
        if self.start < 0:
            msg = "start must be non-negative"
            raise ValueError(msg)
        self._next_value = self.start

    def next_id(self) -> str:
        """Return the next prefixed identifier."""
        identifier = f"{self.prefix}-{self._next_value:0{self.width}d}"
        self._next_value += 1
        return identifier


@dataclass(slots=True)
class DeterministicUuid7Generator:
    """Generate time-ordered UUIDv7 values from virtual time and seeded randomness."""

    clock: VirtualClock
    random_stream: random.Random
    _sequence: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize a deterministic 74-bit sequence."""
        self._sequence = self.random_stream.getrandbits(74)

    def next_id(self) -> str:
        """Return a deterministic UUIDv7 string for the current virtual time."""
        timestamp_ms = int(self.clock.now().timestamp() * 1000)
        if not 0 <= timestamp_ms < 2**48:
            msg = "virtual timestamp is outside the UUIDv7 range"
            raise ValueError(msg)

        sequence = self._sequence
        self._sequence = (self._sequence + 1) % (2**74)
        random_a = (sequence >> 62) & 0xFFF
        random_b = sequence & ((1 << 62) - 1)

        value = timestamp_ms << 80
        value |= 0x7 << 76
        value |= random_a << 64
        value |= 0b10 << 62
        value |= random_b
        return str(UUID(int=value))
