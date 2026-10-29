-- Free Edition fallback for workspaces where Lakebase CDF cannot write to a
-- catalog backed by Databricks default storage. The table deliberately matches
-- the documented Lakebase CDF destination schema.

CREATE TABLE IF NOT EXISTS {catalog}.{schema}.lb_orders_history (
    order_id STRING,
    customer_id STRING,
    amount_cents BIGINT,
    status STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    _pg_change_type STRING,
    _pg_lsn BIGINT,
    _pg_xid INT,
    _timestamp TIMESTAMP,
    _sort_by BIGINT
)
USING DELTA
TBLPROPERTIES (
    'delta.appendOnly' = 'true',
    'faultline.source' = 'lakebase-cdf-compatible-fallback'
)

-- faultline:split

INSERT INTO {catalog}.{schema}.lb_orders_history
SELECT *
FROM VALUES
    ('order-001', 'customer-001', 2599L, 'pending',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:00:00',
     'insert', 1001L, 501, TIMESTAMP'2026-10-29 19:00:01', 1L),
    ('order-002', 'customer-002', 7499L, 'paid',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:00:00',
     'insert', 1002L, 502, TIMESTAMP'2026-10-29 19:00:02', 2L),
    ('order-003', 'customer-003', 1299L, 'shipped',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:00:00',
     'insert', 1003L, 503, TIMESTAMP'2026-10-29 19:00:03', 3L),
    ('order-001', 'customer-001', 2599L, 'pending',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:05:00',
     'update_preimage', 1004L, 504, TIMESTAMP'2026-10-29 19:05:01', 4L),
    ('order-001', 'customer-001', 2599L, 'paid',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:05:00',
     'update_postimage', 1004L, 504, TIMESTAMP'2026-10-29 19:05:01', 5L),
    ('order-003', 'customer-003', 1299L, 'shipped',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:10:00',
     'delete', 1005L, 505, TIMESTAMP'2026-10-29 19:10:01', 6L),
    ('order-004', 'customer-004', -100L, 'corrupt',
     TIMESTAMP'2026-10-29 19:15:00', TIMESTAMP'2026-10-29 19:15:00',
     'insert', 1006L, 506, TIMESTAMP'2026-10-29 19:15:01', 7L),
    ('order-002', 'customer-002', 7499L, 'paid',
     TIMESTAMP'2026-10-29 19:00:00', TIMESTAMP'2026-10-29 19:00:00',
     'insert', 1002L, 502, TIMESTAMP'2026-10-29 19:00:02', 2L)
AS seed(
    order_id, customer_id, amount_cents, status, created_at, updated_at,
    _pg_change_type, _pg_lsn, _pg_xid, _timestamp, _sort_by
)
WHERE NOT EXISTS (
    SELECT 1 FROM {catalog}.{schema}.lb_orders_history LIMIT 1
)

