from __future__ import annotations

import argparse
import json
import re
import time

from databricks.sdk import WorkspaceClient


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


def safe_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value


def query(client: WorkspaceClient, warehouse_id: str, statement: str):
    response = client.statement_execution.execute_statement(
        statement=statement,
        warehouse_id=warehouse_id,
        wait_timeout="50s",
    )
    state = response.status.state.value
    while state not in TERMINAL_STATES:
        time.sleep(2)
        response = client.statement_execution.get_statement(response.statement_id)
        state = response.status.state.value
    if state != "SUCCEEDED":
        raise RuntimeError(f"SQL statement {state}: {response.status.error}")

    columns = [column.name for column in response.manifest.schema.columns]
    rows = response.result.data_array or []
    return [dict(zip(columns, row, strict=True)) for row in rows]


def as_int(row: dict[str, str], key: str) -> int:
    return int(row[key])


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployed Faultline invariants")
    parser.add_argument("--profile", default="faultline")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()

    catalog = safe_identifier(args.catalog)
    schema = safe_identifier(args.schema)
    prefix = f"{catalog}.{schema}"
    client = WorkspaceClient(profile=args.profile)

    counts = query(
        client,
        args.warehouse_id,
        f"""
        SELECT
          (SELECT count(*) FROM {prefix}.orders_bronze) AS bronze_rows,
          (SELECT count(*) FROM {prefix}.orders_valid) AS valid_rows,
          (SELECT count(*) FROM {prefix}.orders_quarantine) AS quarantine_rows,
          (SELECT count(*) FROM {prefix}.orders_current) AS current_rows,
          (SELECT count(*) FROM {prefix}.orders_history) AS history_rows
        """,
    )[0]
    reliability = query(
        client,
        args.warehouse_id,
        f"""
        SELECT received_events, distinct_events, duplicate_events,
               actionable_events, audit_preimages, latest_source_sequence
        FROM {prefix}.orders_reliability
        """,
    )[0]
    current = query(
        client,
        args.warehouse_id,
        f"""
        SELECT order_id, amount_cents, status
        FROM {prefix}.orders_current
        ORDER BY order_id
        """,
    )
    quarantine = query(
        client,
        args.warehouse_id,
        f"""
        SELECT order_id, violation_reasons
        FROM {prefix}.orders_quarantine
        ORDER BY _sort_by
        """,
    )

    assert as_int(counts, "bronze_rows") == 8, counts
    assert as_int(counts, "valid_rows") == 6, counts
    assert as_int(counts, "quarantine_rows") == 1, counts
    assert as_int(counts, "current_rows") == 2, counts
    assert as_int(counts, "history_rows") >= 3, counts
    assert as_int(reliability, "received_events") == 8, reliability
    assert as_int(reliability, "distinct_events") == 7, reliability
    assert as_int(reliability, "duplicate_events") == 1, reliability
    assert as_int(reliability, "actionable_events") == 7, reliability
    assert as_int(reliability, "audit_preimages") == 1, reliability
    assert as_int(reliability, "latest_source_sequence") == 7, reliability

    expected_current = [
        {"order_id": "order-001", "amount_cents": "2599", "status": "paid"},
        {"order_id": "order-002", "amount_cents": "7499", "status": "paid"},
    ]
    assert current == expected_current, current
    assert len(quarantine) == 1 and quarantine[0]["order_id"] == "order-004"

    print(
        json.dumps(
            {
                "counts": counts,
                "current": current,
                "quarantine": quarantine,
                "reliability": reliability,
                "verified": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

