# Faultline local correctness core

Purpose: deterministic, dependency-free reference implementation for CDC projection and reconciliation. This is the oracle used to test Databricks pipeline output later.

Event identity: `(lsn, txid, entity_id)`. Repeated delivery of the same key is a duplicate and has no effect, including repeated invalid events.

Ordering: current state is selected by max `(lsn, txid)` per entity, not arrival order. This guarantees convergence under delayed/out-of-order delivery. Equal LSNs are deterministically broken by txid; production CDF is expected to provide stronger source ordering.

Validation: schema version must be supported. Insert/update require mapping payload with non-negative integer `amount_cents` and an allowed status. Delete requires no payload. Invalid events are retained in quarantine with structured issues.

Reconciliation: replay every accepted unique event in deterministic order into an independent expected-state map; compare with projector state and report field-level mismatches. Later the same reference function will compare Lakeflow materializations with source CDF.

Fault injection is deterministic and composable: duplicate every Nth event, corrupt every Nth event, reverse fixed-size windows. Add schema drift and transaction reordering after the basic core is stable.

