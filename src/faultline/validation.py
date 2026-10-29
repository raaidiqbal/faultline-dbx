from __future__ import annotations

from collections.abc import Mapping

from .models import CdcEvent, ChangeType, ValidationIssue


SUPPORTED_SCHEMA_VERSION = 1
ALLOWED_STATUSES = frozenset({"created", "authorized", "fulfilled", "cancelled"})


def validate_event(event: CdcEvent) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []

    if event.lsn < 0:
        issues.append(ValidationIssue("invalid_lsn", "lsn must be non-negative"))
    if not event.txid.strip():
        issues.append(ValidationIssue("missing_txid", "txid must be non-empty"))
    if not event.entity_id.strip():
        issues.append(ValidationIssue("missing_entity_id", "entity_id must be non-empty"))
    if event.schema_version != SUPPORTED_SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "unsupported_schema",
                f"schema version {event.schema_version} is not supported",
            )
        )

    if event.change_type is ChangeType.DELETE:
        return tuple(issues)

    if not isinstance(event.payload, Mapping):
        issues.append(ValidationIssue("missing_payload", "insert and update events require a payload"))
        return tuple(issues)

    amount = event.payload.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        issues.append(
            ValidationIssue(
                "invalid_amount",
                "amount_cents must be a non-negative integer",
            )
        )

    status = event.payload.get("status")
    if status not in ALLOWED_STATUSES:
        issues.append(
            ValidationIssue(
                "invalid_status",
                f"status must be one of {sorted(ALLOWED_STATUSES)}",
            )
        )

    return tuple(issues)

