# Faultline MVP plan

Decision: build at the existing repository root. The repo was empty and already initialized; avoid a nested Git repository. Public repo can still be named `faultline-dbx`.

Goal: portfolio-grade Databricks systems project showing end-to-end SDLC, database/CDC knowledge, incremental processing, reliability, observability, security boundaries, testing, and a clear demo. Avoid generic RAG/chatbot work because the resume already has MCP/LLM evidence.

Primary architecture:

- Lakebase Postgres is the operational source.
- Lakebase CDF (Public Preview, admin enablement required) emits WAL changes into a Unity Catalog managed Delta table. Feasibility spike first; Free Edition availability is unconfirmed.
- Lakeflow Declarative Pipeline consumes CDF, validates rows with expectations, quarantines failures, and materializes current-state/history/reliability tables.
- Pipeline event log is the observability source for throughput, failures, data-quality metrics, and recovery timing.
- Databricks App presents incident controls and reliability metrics. App is authenticated and cannot be the public resume link.
- Declarative Automation Bundle defines deployable resources. GitHub Actions runs local tests and static validation; Free Edition lacks account APIs needed for some deployment identities.
- Public artifact is GitHub README + architecture diagram + measured benchmarks + 90-second video/GIF.

Fallback: if Lakebase CDF cannot be enabled, generate Delta CDC input directly while preserving the same event schema, fault harness, Lakeflow pipeline, observability, and UI. Do not block the project on a preview feature. This fallback is active in the Free Edition workspace because Lakebase CDF rejects catalogs backed by Databricks default storage; the tier does not provide the required external-storage catalog.

Milestones:

1. Local correctness core: typed event model, validation, idempotent projector, quarantine, deterministic replay, fault injector, CLI, unit tests.
2. Databricks feasibility: CLI OAuth, workspace profile, Free Edition inventory, Lakebase CDF preview check, event_log() access.
3. Platform resources: Lakebase schema/seed API, Unity Catalog objects, Lakeflow pipeline, bundle definitions.
4. Incident UI: run scenarios, inspect quarantined rows, compare expected/current state, visualize freshness and recovery.
5. Evidence: load/fault matrix, correctness invariants, throughput/latency measurements, security review, demo recording, polished README.

Non-goals for MVP: real customer data, anonymous public Databricks App, multi-cloud support, GPU/model serving, enterprise account APIs, production SLA claims.

Security: never commit workspace credentials, OAuth tokens, generated profiles, or database passwords. Prefer OAuth U2M locally. Grant app/service identities least privilege. Synthetic data only.

Git hygiene: author is user's configured Git identity. Normal feature branches and conventional commit messages. No Codex/AI trailers, branch prefixes, generated-by comments, or GitHub-side @codex actions. Local review before push.

