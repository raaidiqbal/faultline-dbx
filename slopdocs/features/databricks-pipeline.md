# Databricks pipeline adapter

The Lakeflow adapter lives in `databricks/pipelines/faultline_pipeline.py` and
is deployed by the Declarative Automation Bundle at the repository root.

Input contract: a Lakebase Change Data Feed destination named
`lb_orders_history`. The adapter depends on documented Lakebase columns
`_pg_change_type`, `_pg_lsn`, `_pg_xid`, `_timestamp`, and `_sort_by`.

Behavior:

- `orders_bronze` retains every source row, including update preimages.
- `orders_valid` exposes inserts, update postimages, and deletes to Lakeflow
  expectations. Do not pre-filter invalid rows after adding `is_valid`; the
  expectation operator must see failures so its metrics remain meaningful.
- `orders_quarantine` retains the same invalid actionable rows with an array of
  rule names. It is deliberately separate from expectation dropping.
- `orders_current` uses AUTO CDC SCD Type 1.
- `orders_history` uses AUTO CDC SCD Type 2.
- Both projections sequence by `struct(_sort_by, _pg_xid)`. `_sort_by` is the
  Lakebase-provided monotonic global order; `_pg_xid` is the deterministic
  tie-breaker.
- Exact source-event duplicates are visible in `orders_reliability` through
  the SHA-256 `event_key`; state idempotency is delegated to keyed AUTO CDC.

The pipeline uses the current `pyspark.pipelines` interface, not legacy `dlt`
or `apply_changes`. Contract tests intentionally fail if that regresses.

Workspace validation requires an authenticated Databricks profile because
bundle interpolation reads the current user's identity. Local syntax, core
correctness, and platform contract tests do not require workspace access.

