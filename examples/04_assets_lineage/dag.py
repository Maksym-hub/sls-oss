"""Assets & lineage + a pull-based cross-pipeline dependency.

Assets are the data your tasks produce (`outlets`) and consume (`inlets`).
polyris tracks them to build a lineage graph and to drive backfills.

This pipeline also shows a PULL dependency: `build_report` won't start until
the `sales/daily-clean` asset — produced by *another* pipeline — is fresh
(`wait_for=[... .within(days=2)]`). The two pipelines never reference each
other directly; they meet only at the asset.

Run it locally (no AWS):  polyris-validate -v
"""
from polyris import DAG, task, Asset, Column, types as t

ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:worker"

# An asset produced by an upstream pipeline — we only depend on it here.
daily_clean = Asset("sales/daily-clean")

# A typed asset THIS pipeline produces. The schema documents the contract
# downstream consumers rely on and powers Glue drift detection.
report = Asset(
    "sales/weekly-report",
    description="Weekly sales rollup, one row per region.",
    schema=[
        Column("region",     t.varchar(8),     primary_key=True, nullable=False),
        Column("units_sold", t.bigint(),       nullable=False),
        Column("revenue",    t.decimal(14, 2), nullable=False),
        Column("event_date", t.date(),         partition_key=True, nullable=False),
    ],
)

with DAG(
    dag_id="weekly-report",
    schedule="cron(0 6 ? * MON *)",           # Mondays 06:00 UTC
    description="Weekly report — waits for fresh daily data, emits a typed asset.",
) as dag:

    @task.sfn(
        arn=ARN,
        wait_for=[daily_clean.within(days=2)],  # PULL: block until daily data is fresh
        outlets=[report],                        # this task materializes `report`
    )
    def build_report():
        """Roll up the last week of clean daily sales into the report asset."""
        pass

    build_report()
