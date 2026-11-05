"""Stable named random streams derived from one simulation seed."""

import hashlib
import random
from dataclasses import dataclass, field


@dataclass(slots=True)
class RandomStreams:
    """Create isolated pseudo-random streams for simulator responsibilities."""

    master_seed: int
    _streams: dict[str, random.Random] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Reject negative seeds to keep configuration unambiguous."""
        if self.master_seed < 0:
            msg = "master_seed must be non-negative"
            raise ValueError(msg)

    def derive_seed(self, stream_name: str) -> int:
        """Derive a stable integer seed from the master seed and stream name."""
        normalized_name = stream_name.strip()
        if not normalized_name:
            msg = "stream_name must not be empty"
            raise ValueError(msg)

        material = f"{self.master_seed}:{normalized_name}".encode()
        digest = hashlib.sha256(material).digest()
        return int.from_bytes(digest[:16], byteorder="big", signed=False)

    def get(self, stream_name: str) -> random.Random:
        """Return the persistent pseudo-random generator for a named stream."""
        normalized_name = stream_name.strip()
        if normalized_name not in self._streams:
            self._streams[normalized_name] = random.Random(self.derive_seed(normalized_name))
        return self._streams[normalized_name]
