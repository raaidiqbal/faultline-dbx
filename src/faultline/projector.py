from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .models import CdcEvent, ChangeType, OrderRecord, QuarantinedEvent
from .validation import validate_event


class IngestDisposition(str, Enum):
    APPLIED = "applied"
    SUPERSEDED = "superseded"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    received_events: int
    accepted_events: int
    duplicate_events: int
    quarantined_events: int
    current_records: int
    deleted_entities: int
    invariant_violations: tuple[str, ...]

    @property
    def reconciled(self) -> bool:
        return not self.invariant_violations


class CdcProjector:
    """Idempotent, arrival-order-independent CDC projector.

    The projector is deliberately independent of Spark and Databricks. It acts
    as the correctness oracle for future Lakeflow integration tests.
    """

    def __init__(self) -> None:
        self._seen: set[tuple[int, str, str]] = set()
        self._accepted: list[CdcEvent] = []
        self._quarantine: list[QuarantinedEvent] = []
        self._current: dict[str, OrderRecord] = {}
        self._latest_order: dict[str, tuple[int, str]] = {}
        self._latest_change: dict[str, ChangeType] = {}
        self._received = 0
        self._duplicates = 0

    @property
    def current(self) -> dict[str, OrderRecord]:
        return dict(self._current)

    @property
    def quarantine(self) -> tuple[QuarantinedEvent, ...]:
        return tuple(self._quarantine)

    @property
    def accepted(self) -> tuple[CdcEvent, ...]:
        return tuple(self._accepted)

    def ingest(self, event: CdcEvent) -> IngestDisposition:
        self._received += 1

        if event.idempotency_key in self._seen:
            self._duplicates += 1
            return IngestDisposition.DUPLICATE
        self._seen.add(event.idempotency_key)

        issues = validate_event(event)
        if issues:
            self._quarantine.append(QuarantinedEvent(event=event, issues=issues))
            return IngestDisposition.QUARANTINED

        self._accepted.append(event)
        previous_order = self._latest_order.get(event.entity_id)
        if previous_order is not None and event.ordering_key <= previous_order:
            return IngestDisposition.SUPERSEDED

        self._latest_order[event.entity_id] = event.ordering_key
        self._latest_change[event.entity_id] = event.change_type
        self._apply_latest(event)
        return IngestDisposition.APPLIED

    def ingest_many(self, events: Iterable[CdcEvent]) -> tuple[IngestDisposition, ...]:
        return tuple(self.ingest(event) for event in events)

    def reconcile(self) -> ReconciliationReport:
        expected, expected_latest_change = replay_events(self._accepted)
        violations: list[str] = []

        actual_ids = set(self._current)
        expected_ids = set(expected)
        for missing_id in sorted(expected_ids - actual_ids):
            violations.append(f"missing current record: {missing_id}")
        for unexpected_id in sorted(actual_ids - expected_ids):
            violations.append(f"unexpected current record: {unexpected_id}")
        for entity_id in sorted(actual_ids & expected_ids):
            if self._current[entity_id] != expected[entity_id]:
                violations.append(f"state mismatch: {entity_id}")

        deleted_entities = sum(
            1 for change in expected_latest_change.values() if change is ChangeType.DELETE
        )
        return ReconciliationReport(
            received_events=self._received,
            accepted_events=len(self._accepted),
            duplicate_events=self._duplicates,
            quarantined_events=len(self._quarantine),
            current_records=len(self._current),
            deleted_entities=deleted_entities,
            invariant_violations=tuple(violations),
        )

    def _apply_latest(self, event: CdcEvent) -> None:
        if event.change_type is ChangeType.DELETE:
            self._current.pop(event.entity_id, None)
            return

        assert event.payload is not None
        self._current[event.entity_id] = OrderRecord(
            order_id=event.entity_id,
            amount_cents=int(event.payload["amount_cents"]),
            status=str(event.payload["status"]),
            updated_at=event.occurred_at,
            source_lsn=event.lsn,
            source_txid=event.txid,
        )


def replay_events(
    events: Iterable[CdcEvent],
) -> tuple[dict[str, OrderRecord], dict[str, ChangeType]]:
    """Replay accepted unique events in source order into an independent state."""

    current: dict[str, OrderRecord] = {}
    latest_change: dict[str, ChangeType] = {}
    seen: set[tuple[int, str, str]] = set()

    for event in sorted(events, key=lambda item: (item.lsn, item.txid, item.entity_id)):
        if event.idempotency_key in seen:
            continue
        seen.add(event.idempotency_key)
        latest_change[event.entity_id] = event.change_type

        if event.change_type is ChangeType.DELETE:
            current.pop(event.entity_id, None)
            continue

        assert event.payload is not None
        current[event.entity_id] = OrderRecord(
            order_id=event.entity_id,
            amount_cents=int(event.payload["amount_cents"]),
            status=str(event.payload["status"]),
            updated_at=event.occurred_at,
            source_lsn=event.lsn,
            source_txid=event.txid,
        )

    return current, latest_change

