"""Tests for reproducible named random streams."""

import pytest

from food_delivery_lakehouse.simulator.randomness import RandomStreams


def test_same_seed_and_stream_name_repeat_the_same_sequence() -> None:
    """Produce identical values when seed and stream name are unchanged."""
    first = RandomStreams(42).get("orders")
    second = RandomStreams(42).get("orders")

    assert [first.random() for _ in range(5)] == [second.random() for _ in range(5)]


def test_domain_streams_do_not_influence_each_other() -> None:
    """Keep Order results stable when another domain consumes random values."""
    baseline = RandomStreams(42)
    baseline_orders = [baseline.get("orders").random() for _ in range(3)]

    with_payment_activity = RandomStreams(42)
    _ = [with_payment_activity.get("payments").random() for _ in range(100)]
    orders_after_payments = [with_payment_activity.get("orders").random() for _ in range(3)]

    assert orders_after_payments == baseline_orders


def test_stream_name_must_not_be_empty() -> None:
    """Reject unnamed streams because they would hide ownership."""
    with pytest.raises(ValueError, match="must not be empty"):
        RandomStreams(42).get("  ")
