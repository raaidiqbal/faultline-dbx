# Local benchmark contract

`scripts/benchmark_local.py` measures only the platform-independent correctness
oracle. It excludes event generation and fault injection, times ingest plus
independent replay, runs each scenario seven times by default, and records the
median, p95, individual samples, disposition counts, and reconciliation result.

Checked-in evidence is `benchmarks/local-2026-10-29.json`. Never describe it as
Spark, Lakeflow, Lakebase, cluster, or production throughput. Workspace results
stay separate because the Free Edition CDF fallback is tiny and cold-start
timing would dominate.

The severe scenario can show higher delivered-event throughput than the mixed
scenario. One third of severe deliveries are exact duplicates, so the projector
short-circuits them at the idempotency set before validation/projection. This is
expected behavior and must be explained whenever the figure is used.

Add new benchmark cases to `CASES`; keep a smoke contract in unit tests. Raw
JSON is the source of truth for README figures and the benchmark canvas.
