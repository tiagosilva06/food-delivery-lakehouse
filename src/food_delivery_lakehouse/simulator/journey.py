"""Coordination of complete simulated order journeys."""

from dataclasses import dataclass

from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import SimulatedEvent


@dataclass(slots=True)
class OrderJourneySimulator:
    """Coordinate domain generators into complete order journeys."""

    order: OrderEventGenerator
    payment: PaymentEventGenerator
    fulfillment: FulfillmentEventGenerator
    delivery: DeliveryEventGenerator

    def generate_successful_order(self) -> tuple[SimulatedEvent, ...]:
        """Generate one ordered, successful food delivery journey."""
        order_created = self.order.create_order_created()
        payment_initiated = self.payment.create_payment_initiated(order_created)
        payment_authorized = self.payment.create_payment_authorized(payment_initiated)
        fulfillment_requested = self.fulfillment.create_fulfillment_requested(
            order_created,
            payment_authorized,
        )
        order_accepted = self.fulfillment.create_order_accepted(fulfillment_requested)
        payment_captured = self.payment.create_payment_captured(payment_authorized)
        order_confirmed = self.order.create_order_confirmed(
            order_created,
            payment_captured,
            order_accepted,
        )
        preparation_started = self.fulfillment.create_preparation_started(
            order_accepted,
            order_confirmed,
        )
        order_ready = self.fulfillment.create_order_ready_for_pickup(preparation_started)
        delivery_requested = self.delivery.create_delivery_requested(
            order_created,
            order_ready,
        )
        courier_search_started = self.delivery.create_courier_search_started(delivery_requested)
        courier_assigned = self.delivery.create_courier_assigned(courier_search_started)
        courier_arrived = self.delivery.create_courier_arrived_at_restaurant(courier_assigned)
        order_handed = self.fulfillment.create_order_handed_to_courier(
            order_ready,
            courier_arrived,
        )
        order_picked_up = self.delivery.create_order_picked_up(
            courier_arrived,
            order_handed,
        )
        delivery_started = self.delivery.create_delivery_started(order_picked_up)
        order_delivered = self.delivery.create_order_delivered(delivery_started)
        order_completed = self.order.create_order_completed(order_confirmed, order_delivered)

        return (
            order_created,
            payment_initiated,
            payment_authorized,
            fulfillment_requested,
            order_accepted,
            payment_captured,
            order_confirmed,
            preparation_started,
            order_ready,
            delivery_requested,
            courier_search_started,
            courier_assigned,
            courier_arrived,
            order_handed,
            order_picked_up,
            delivery_started,
            order_delivered,
            order_completed,
        )

    def generate_payment_failure_order(self) -> tuple[SimulatedEvent, ...]:
        """Generate an order that stops after payment authorization fails."""
        order_created = self.order.create_order_created()
        payment_initiated = self.payment.create_payment_initiated(order_created)
        payment_failed = self.payment.create_payment_authorization_failed(payment_initiated)
        order_failed = self.order.create_order_failed_from_payment(
            order_created,
            payment_failed,
        )
        return order_created, payment_initiated, payment_failed, order_failed

    def generate_restaurant_rejection_order(self) -> tuple[SimulatedEvent, ...]:
        """Generate an authorized order rejected by the restaurant."""
        order_created = self.order.create_order_created()
        payment_initiated = self.payment.create_payment_initiated(order_created)
        payment_authorized = self.payment.create_payment_authorized(payment_initiated)
        fulfillment_requested = self.fulfillment.create_fulfillment_requested(
            order_created,
            payment_authorized,
        )
        order_rejected = self.fulfillment.create_order_rejected(fulfillment_requested)
        payment_voided = self.payment.create_payment_authorization_voided(
            payment_authorized,
            order_rejected,
        )
        order_cancelled = self.order.create_order_cancelled_after_restaurant_rejection(
            order_created,
            order_rejected,
            payment_voided,
        )
        return (
            order_created,
            payment_initiated,
            payment_authorized,
            fulfillment_requested,
            order_rejected,
            payment_voided,
            order_cancelled,
        )
