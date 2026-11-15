"""Profile-driven, memory-bounded execution of simulated order journeys."""

import heapq
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from food_delivery_lakehouse.simulator.anomalies import (
    AnomalyRates,
    EmissionRecord,
    EventAnomalyInjector,
)
from food_delivery_lakehouse.simulator.clock import VirtualClock
from food_delivery_lakehouse.simulator.domains.delivery import DeliveryEventGenerator
from food_delivery_lakehouse.simulator.domains.fulfillment import FulfillmentEventGenerator
from food_delivery_lakehouse.simulator.domains.order import OrderEventGenerator
from food_delivery_lakehouse.simulator.domains.payment import PaymentEventGenerator
from food_delivery_lakehouse.simulator.events import CloudEventFactory, SimulatedEvent
from food_delivery_lakehouse.simulator.identifiers import DeterministicUuid7Generator
from food_delivery_lakehouse.simulator.journey import OrderJourneySimulator
from food_delivery_lakehouse.simulator.randomness import RandomStreams
from food_delivery_lakehouse.simulator.settings import SimulationSettings

type ScenarioName = Literal[
    "successful",
    "payment_failure",
    "restaurant_rejection",
    "courier_timeout",
    "delivery_failure",
]

_SCENARIOS: tuple[ScenarioName, ...] = (
    "successful",
    "payment_failure",
    "restaurant_rejection",
    "courier_timeout",
    "delivery_failure",
)

type PendingEmission = tuple[
    datetime,
    int,
    EmissionRecord,
    Iterator[EmissionRecord],
]


@dataclass(slots=True)
class SimulationRunner:
    """Generate configured journeys and merge their records by publication time."""

    settings: SimulationSettings
    _streams: RandomStreams = field(init=False, repr=False)
    _order: OrderEventGenerator = field(init=False, repr=False)
    _payment: PaymentEventGenerator = field(init=False, repr=False)
    _fulfillment: FulfillmentEventGenerator = field(init=False, repr=False)
    _delivery: DeliveryEventGenerator = field(init=False, repr=False)
    _anomaly_injector: EventAnomalyInjector = field(init=False, repr=False)
    _anomaly_rates: AnomalyRates = field(init=False, repr=False)
    _heap_sequence: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        """Create persistent random streams and business ID sequences."""
        self._streams = RandomStreams(self.settings.seed)
        initial_factory = self._create_event_factory(self.settings.logical_start_at)
        self._order = OrderEventGenerator(initial_factory, self._streams.get("orders"))
        self._payment = PaymentEventGenerator(initial_factory, self._streams.get("payments"))
        self._fulfillment = FulfillmentEventGenerator(
            initial_factory,
            self._streams.get("fulfillment"),
        )
        self._delivery = DeliveryEventGenerator(initial_factory, self._streams.get("delivery"))
        self._anomaly_injector = EventAnomalyInjector(self._streams.get("anomalies"))
        self._anomaly_rates = AnomalyRates.from_settings(self.settings)

    @classmethod
    def from_profile(cls, path: Path) -> "SimulationRunner":
        """Build a runner from one TOML execution profile."""
        return cls(SimulationSettings.from_toml(path))

    def run(self) -> Iterator[EmissionRecord]:
        """Yield interleaved emission records without materializing the full run."""
        pending: list[PendingEmission] = []
        next_order_index = 0

        while next_order_index < self.settings.order_count or pending:
            next_start = self._order_start_at(next_order_index)
            if next_order_index < self.settings.order_count and (
                not pending or next_start <= pending[0][0]
            ):
                records = self._generate_order_records(next_start)
                self._schedule_first(records, pending)
                next_order_index += 1
                continue

            _, _, record, remaining = heapq.heappop(pending)
            yield record
            self._schedule_next(remaining, pending)

    def _generate_order_records(self, start_at: datetime) -> tuple[EmissionRecord, ...]:
        """Generate and deform one journey beginning at a logical start time."""
        journey = self._create_journey(start_at)
        scenario = self._choose_scenario()
        events = self._generate_scenario(journey, scenario)
        return self._anomaly_injector.inject(events, self._anomaly_rates)

    def _create_journey(self, start_at: datetime) -> OrderJourneySimulator:
        """Point persistent domain generators at a clock for one new order."""
        event_factory = self._create_event_factory(start_at)
        self._order.event_factory = event_factory
        self._payment.event_factory = event_factory
        self._fulfillment.event_factory = event_factory
        self._delivery.event_factory = event_factory
        return OrderJourneySimulator(
            order=self._order,
            payment=self._payment,
            fulfillment=self._fulfillment,
            delivery=self._delivery,
        )

    def _create_event_factory(self, start_at: datetime) -> CloudEventFactory:
        """Create a per-order clock while preserving deterministic event IDs."""
        clock = VirtualClock(start_at)
        event_ids = DeterministicUuid7Generator(clock, self._streams.get("event_ids"))
        return CloudEventFactory(clock, event_ids)

    def _choose_scenario(self) -> ScenarioName:
        """Select one journey type from profile probabilities."""
        weights = (
            self.settings.successful_order_rate,
            self.settings.payment_failure_rate,
            self.settings.restaurant_rejection_rate,
            self.settings.courier_timeout_rate,
            self.settings.delivery_failure_rate,
        )
        selected = self._streams.get("scenarios").choices(_SCENARIOS, weights=weights, k=1)[0]
        return selected

    @staticmethod
    def _generate_scenario(
        journey: OrderJourneySimulator,
        scenario: ScenarioName,
    ) -> tuple[SimulatedEvent, ...]:
        """Dispatch the selected scenario to its journey method."""
        generators = {
            "successful": journey.generate_successful_order,
            "payment_failure": journey.generate_payment_failure_order,
            "restaurant_rejection": journey.generate_restaurant_rejection_order,
            "courier_timeout": journey.generate_courier_timeout_order,
            "delivery_failure": journey.generate_delivery_failure_order,
        }
        return generators[scenario]()

    def _order_start_at(self, order_index: int) -> datetime:
        """Distribute order creation uniformly across the logical duration."""
        duration_seconds = self.settings.duration_hours * 60 * 60
        offset_seconds = duration_seconds * order_index / self.settings.order_count
        return self.settings.logical_start_at + timedelta(seconds=offset_seconds)

    def _schedule_first(
        self,
        records: tuple[EmissionRecord, ...],
        pending: list[PendingEmission],
    ) -> None:
        """Schedule the first record of a journey and retain its iterator."""
        iterator = iter(records)
        self._schedule_next(iterator, pending)

    def _schedule_next(
        self,
        records: Iterator[EmissionRecord],
        pending: list[PendingEmission],
    ) -> None:
        """Place the next record from one journey on the publication heap."""
        try:
            record = next(records)
        except StopIteration:
            return
        self._heap_sequence += 1
        heapq.heappush(
            pending,
            (
                _published_at(record),
                self._heap_sequence,
                record,
                records,
            ),
        )


def _published_at(record: EmissionRecord) -> datetime:
    """Read the logical publication timestamp used by the merge heap."""
    value = record.payload.get("publishedat")
    if not isinstance(value, str):
        msg = "publishedat must be str"
        raise ValueError(msg)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
