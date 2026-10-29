"""Lakeflow pipeline for Lakebase CDC correctness and observability.

This file runs inside Databricks Lakeflow Declarative Pipelines. The local
``faultline`` package is the platform-independent correctness oracle; this
module is intentionally a thin adapter over Lakebase CDF system columns.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


SOURCE_TABLE = spark.conf.get("faultline.source_table")

ACTIONABLE_CHANGE_TYPES = ("insert", "update_postimage", "delete")
VALID_ORDER_STATUSES = ("pending", "paid", "shipped", "cancelled")

VALID_ORDER_RULES = {
    "order_id_present": "order_id IS NOT NULL AND length(trim(order_id)) > 0",
    "known_change_type": (
        "_pg_change_type IN ('insert', 'update_postimage', 'delete')"
    ),
    "valid_order_values": (
        "_pg_change_type = 'delete' OR "
        "(amount_cents IS NOT NULL AND amount_cents >= 0 "
        "AND status IN ('pending', 'paid', 'shipped', 'cancelled'))"
    ),
    "source_sequence_present": "_sort_by IS NOT NULL AND _pg_xid IS NOT NULL",
}


def _validity_expression():
    return F.expr(" AND ".join(f"({rule})" for rule in VALID_ORDER_RULES.values()))


def _violation_reasons():
    reasons = [
        F.when(~F.expr(rule), F.lit(name))
        for name, rule in VALID_ORDER_RULES.items()
    ]
    return F.array_compact(F.array(*reasons))


@dp.table(
    name="orders_bronze",
    comment="Append-only Lakebase order changes with source ordering metadata.",
    table_properties={"quality": "bronze"},
)
def orders_bronze():
    return (
        spark.readStream.table(SOURCE_TABLE)
        .withColumn(
            "event_key",
            F.sha2(
                F.concat_ws(
                    ":",
                    F.col("_pg_lsn").cast("string"),
                    F.col("_pg_xid").cast("string"),
                    F.col("order_id").cast("string"),
                    F.col("_pg_change_type"),
                ),
                256,
            ),
        )
        .withColumn(
            "is_actionable",
            F.col("_pg_change_type").isin(*ACTIONABLE_CHANGE_TYPES),
        )
    )


@dp.table(
    name="orders_valid",
    comment="Validated CDC actions eligible for current-state projection.",
    table_properties={"quality": "silver"},
)
@dp.expect_all_or_drop(VALID_ORDER_RULES)
def orders_valid():
    return (
        spark.readStream.table("orders_bronze")
        .filter(F.col("is_actionable"))
        .withColumn("is_valid", _validity_expression())
    )


@dp.table(
    name="orders_quarantine",
    comment="Malformed actionable CDC rows with machine-readable violation reasons.",
    table_properties={"quality": "quarantine"},
)
def orders_quarantine():
    return (
        spark.readStream.table("orders_bronze")
        .filter(F.col("is_actionable"))
        .withColumn("is_valid", _validity_expression())
        .filter(~F.col("is_valid"))
        .withColumn("violation_reasons", _violation_reasons())
    )


dp.create_streaming_table(
    name="orders_current",
    comment="Latest valid order state; deletes are represented as CDC tombstones.",
    table_properties={
        "quality": "gold",
        "pipelines.cdc.tombstoneGCThresholdInSeconds": "172800",
    },
)

dp.create_auto_cdc_flow(
    target="orders_current",
    source="orders_valid",
    keys=["order_id"],
    sequence_by=F.struct("_sort_by", "_pg_xid"),
    apply_as_deletes=F.expr("_pg_change_type = 'delete'"),
    except_column_list=[
        "_pg_change_type",
        "event_key",
        "is_actionable",
        "is_valid",
    ],
    stored_as_scd_type=1,
)


dp.create_streaming_table(
    name="orders_history",
    comment="SCD Type 2 history derived from valid Lakebase CDC actions.",
    table_properties={"quality": "gold"},
)

dp.create_auto_cdc_flow(
    target="orders_history",
    source="orders_valid",
    keys=["order_id"],
    sequence_by=F.struct("_sort_by", "_pg_xid"),
    apply_as_deletes=F.expr("_pg_change_type = 'delete'"),
    except_column_list=[
        "_pg_change_type",
        "event_key",
        "is_actionable",
        "is_valid",
    ],
    stored_as_scd_type=2,
)


@dp.materialized_view(
    name="orders_reliability",
    comment="Compact reliability counters for the incident console.",
    table_properties={"quality": "observability"},
)
def orders_reliability():
    events = spark.read.table("orders_bronze")
    return events.agg(
        F.count("*").alias("received_events"),
        F.countDistinct("event_key").alias("distinct_events"),
        (F.count("*") - F.countDistinct("event_key")).alias("duplicate_events"),
        F.sum(F.col("is_actionable").cast("long")).alias("actionable_events"),
        F.sum((F.col("_pg_change_type") == "update_preimage").cast("long")).alias(
            "audit_preimages"
        ),
        F.max("_timestamp").alias("latest_source_timestamp"),
        F.max("_sort_by").alias("latest_source_sequence"),
    )

