"""Tests for terminal payment and restaurant failure journeys."""

from tests.unit.simulator.test_journey import _create_simulator


def test_payment_failure_stops_before_fulfillment() -> None:
    """End the journey without restaurant or delivery events."""
    events = _create_simulator().generate_payment_failure_order()

    assert tuple(event.event_type for event in events) == (
        "com.fooddelivery.order.created.v1",
        "com.fooddelivery.payment.initiated.v1",
        "com.fooddelivery.payment.authorization-failed.v1",
        "com.fooddelivery.order.failed.v1",
    )
    assert events[-1].data["failure_stage"] == "PAYMENT"
    assert events[-1].causation_id == events[-2].event_id


def test_restaurant_rejection_voids_payment_before_cancellation() -> None:
    """Release the authorization before moving Order to cancelled."""
    events = _create_simulator().generate_restaurant_rejection_order()

    assert tuple(event.event_type for event in events[-3:]) == (
        "com.fooddelivery.fulfillment.order-rejected-by-restaurant.v1",
        "com.fooddelivery.payment.authorization-voided.v1",
        "com.fooddelivery.order.cancelled.v1",
    )
    assert events[-2].data["reason_code"] == "RESTAURANT_REJECTED"
    assert events[-1].data == {
        "requested_by": "RESTAURANT",
        "reason_code": "RESTAURANT_REJECTED",
    }
    assert events[-1].causation_id == events[-2].event_id


def test_failed_journeys_remain_deterministic() -> None:
    """Reproduce both failure scenarios from the same seed."""
    first_payment = _create_simulator(20261028).generate_payment_failure_order()
    second_payment = _create_simulator(20261028).generate_payment_failure_order()
    first_rejection = _create_simulator(20261028).generate_restaurant_rejection_order()
    second_rejection = _create_simulator(20261028).generate_restaurant_rejection_order()

    assert tuple(event.to_dict() for event in first_payment) == tuple(
        event.to_dict() for event in second_payment
    )
    assert tuple(event.to_dict() for event in first_rejection) == tuple(
        event.to_dict() for event in second_rejection
    )
