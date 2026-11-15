"""Tests for courier timeout and in-transit delivery failure journeys."""

from tests.unit.simulator.test_journey import _create_simulator


def test_courier_timeout_refunds_captured_payment() -> None:
    """Refund the order after no courier can be assigned."""
    events = _create_simulator().generate_courier_timeout_order()

    assert tuple(event.event_type for event in events[-6:]) == (
        "com.fooddelivery.delivery.courier-search-started.v1",
        "com.fooddelivery.delivery.courier-assignment-timed-out.v1",
        "com.fooddelivery.delivery.cancelled.v1",
        "com.fooddelivery.payment.refund-requested.v1",
        "com.fooddelivery.payment.refunded.v1",
        "com.fooddelivery.order.failed.v1",
    )
    assert events[-3].data["reason_code"] == "ORDER_CANCELLED"
    assert events[-1].data["failure_code"] == "COURIER_ASSIGNMENT_TIMEOUT"


def test_delivery_failure_refunds_captured_payment() -> None:
    """Refund the order after an in-transit delivery failure."""
    events = _create_simulator().generate_delivery_failure_order()

    assert tuple(event.event_type for event in events[-4:]) == (
        "com.fooddelivery.delivery.failed.v1",
        "com.fooddelivery.payment.refund-requested.v1",
        "com.fooddelivery.payment.refunded.v1",
        "com.fooddelivery.order.failed.v1",
    )
    assert events[-3].data["reason_code"] == "DELIVERY_FAILED"
    assert events[-1].data["failure_code"] == events[-4].data["failure_code"]
    assert events[-1].causation_id == events[-2].event_id


def test_delivery_failures_remain_deterministic() -> None:
    """Reproduce both delivery failures from the same seed."""
    first_timeout = _create_simulator(20261028).generate_courier_timeout_order()
    second_timeout = _create_simulator(20261028).generate_courier_timeout_order()
    first_delivery = _create_simulator(20261028).generate_delivery_failure_order()
    second_delivery = _create_simulator(20261028).generate_delivery_failure_order()

    assert tuple(event.to_dict() for event in first_timeout) == tuple(
        event.to_dict() for event in second_timeout
    )
    assert tuple(event.to_dict() for event in first_delivery) == tuple(
        event.to_dict() for event in second_delivery
    )
