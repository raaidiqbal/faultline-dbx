from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import CdcEvent, ChangeType


@dataclass(frozen=True, slots=True)
class FaultProfile:
    duplicate_every: int = 0
    corrupt_every: int = 0
    reverse_window: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("duplicate_every", self.duplicate_every),
            ("corrupt_every", self.corrupt_every),
            ("reverse_window", self.reverse_window),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


def generate_order_events(entity_count: int, *, delete_every: int = 10) -> list[CdcEvent]:
    if entity_count < 1:
        raise ValueError("entity_count must be positive")
    if delete_every < 0:
        raise ValueError("delete_every must be non-negative")

    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events: list[CdcEvent] = []
    lsn = 1

    for index in range(1, entity_count + 1):
        entity_id = f"order-{index:06d}"
        events.append(
            CdcEvent(
                lsn=lsn,
                txid=f"tx-{lsn:08d}",
                entity_id=entity_id,
                change_type=ChangeType.INSERT,
                occurred_at=base_time + timedelta(milliseconds=lsn),
                payload={"amount_cents": 1_000 + index, "status": "created"},
            )
        )
        lsn += 1

        events.append(
            CdcEvent(
                lsn=lsn,
                txid=f"tx-{lsn:08d}",
                entity_id=entity_id,
                change_type=ChangeType.UPDATE,
                occurred_at=base_time + timedelta(milliseconds=lsn),
                payload={"amount_cents": 1_000 + index, "status": "authorized"},
            )
        )
        lsn += 1

        if delete_every and index % delete_every == 0:
            events.append(
                CdcEvent(
                    lsn=lsn,
                    txid=f"tx-{lsn:08d}",
                    entity_id=entity_id,
                    change_type=ChangeType.DELETE,
                    occurred_at=base_time + timedelta(milliseconds=lsn),
                )
            )
            lsn += 1

    return events


def inject_faults(events: Iterable[CdcEvent], profile: FaultProfile) -> list[CdcEvent]:
    injected: list[CdcEvent] = []

    for position, event in enumerate(events, start=1):
        candidate = event
        if profile.corrupt_every and position % profile.corrupt_every == 0:
            payload = dict(event.payload or {})
            payload["amount_cents"] = -1
            candidate = replace(event, payload=payload)

        injected.append(candidate)
        if profile.duplicate_every and position % profile.duplicate_every == 0:
            injected.append(candidate)

    if profile.reverse_window > 1:
        reordered: list[CdcEvent] = []
        for start in range(0, len(injected), profile.reverse_window):
            reordered.extend(reversed(injected[start : start + profile.reverse_window]))
        return reordered

    return injected

