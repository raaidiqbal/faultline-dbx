from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ChangeType(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class CdcEvent:
    lsn: int
    txid: str
    entity_id: str
    change_type: ChangeType
    occurred_at: datetime
    payload: Mapping[str, Any] | None = None
    schema_version: int = 1

    @property
    def idempotency_key(self) -> tuple[int, str, str]:
        return (self.lsn, self.txid, self.entity_id)

    @property
    def ordering_key(self) -> tuple[int, str]:
        return (self.lsn, self.txid)


@dataclass(frozen=True, slots=True)
class OrderRecord:
    order_id: str
    amount_cents: int
    status: str
    updated_at: datetime
    source_lsn: int
    source_txid: str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class QuarantinedEvent:
    event: CdcEvent
    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

