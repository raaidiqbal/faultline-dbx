from __future__ import annotations

import argparse
from pathlib import Path
import re
import time

from databricks.sdk import WorkspaceClient


ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "databricks" / "sql" / "seed_delta_cdf.sql"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


def safe_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value


def wait_for_statement(client: WorkspaceClient, response):
    state = response.status.state.value
    while state not in TERMINAL_STATES:
        time.sleep(2)
        response = client.statement_execution.get_statement(response.statement_id)
        state = response.status.state.value
    if state != "SUCCEEDED":
        error = response.status.error
        raise RuntimeError(f"SQL statement {state}: {error}")
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Lakebase-CDF-compatible Delta input")
    parser.add_argument("--profile", default="faultline")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", required=True)
    args = parser.parse_args()

    catalog = safe_identifier(args.catalog)
    schema = safe_identifier(args.schema)
    sql_text = SQL_FILE.read_text(encoding="utf-8").format(
        catalog=catalog,
        schema=schema,
    )
    statements = [
        statement.strip()
        for statement in sql_text.split("-- faultline:split")
        if statement.strip()
    ]

    client = WorkspaceClient(profile=args.profile)
    for statement in statements:
        response = client.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=args.warehouse_id,
            catalog=catalog,
            schema=schema,
            wait_timeout="50s",
        )
        wait_for_statement(client, response)

    print(f"Seeded {catalog}.{schema}.lb_orders_history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

