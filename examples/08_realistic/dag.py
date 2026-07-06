"""Realistic pipeline — a plausible daily analytics run, end to end.

This is what a real polyris pipeline tends to look like: a mix of services, a
sensible dependency graph, retry/timeout defaults, a conditional notify on
failure, and a cross-account publish at the end. Nothing exotic — it just puts
the pieces from the earlier examples together the way you actually would.

Flow:
    ingest (Lambda)
      → clean (Glue) → aggregate (Athena) → build_report (Batch)
      → validate_freshness (Lambda)
    build_report + validate_freshness → publish (cross-account SFN)
    notify_on_failure runs only if something upstream failed.

Run it locally (no AWS):  polyris-validate -v
"""
from datetime import timedelta

from polyris import DAG, task

ACCOUNT = "000000000000"
REGION = "us-east-1"

with DAG(
    dag_id="daily-analytics",
    schedule="cron(0 5 * * ? *)",          # 05:00 UTC every day
    description="Daily analytics: ingest → clean → aggregate → report → publish.",
    tags=["example", "analytics", "daily"],
    doc_md="End-to-end reference pipeline combining several services.",
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "execution_timeout": timedelta(hours=1),
        "orchestration_timeout": timedelta(hours=4),
    },
) as dag:

    @task.lambda_(function_name="ingest-daily-events")
    def ingest():
        """Land yesterday's raw events."""
        pass

    @task.glue(job_name="clean-events", worker_type="G.1X", number_of_workers=4)
    def clean():
        """Dedupe and normalize."""
        pass

    @task.athena(
        query_string="INSERT INTO gold.daily SELECT * FROM silver.events",
        database="analytics",
        output_location=f"s3://{ACCOUNT}-athena-results/daily/",
    )
    def aggregate():
        """Roll up into the gold daily table."""
        pass

    @task.batch(job_definition="report-render:5", job_queue="reporting")
    def build_report():
        """Render the executive report."""
        pass

    @task.lambda_(function_name="check-data-freshness")
    def validate_freshness():
        """Guardrail: confirm the gold table is fresh before publishing."""
        pass

    @task.sfn(
        arn=f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:publish-report",
        role="orchestration",               # cross-account publish
    )
    def publish():
        """Publish the report via a nested, cross-account workflow."""
        pass

    @task.sfn(
        arn=f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:notify",
        trigger_rule="one_failed",          # only if something upstream failed
    )
    def notify_on_failure():
        """Page the on-call if any upstream step failed."""
        pass

    # Wire the graph.
    raw = ingest()
    cleaned = clean(raw)
    rolled = aggregate(cleaned)
    report = build_report(rolled)
    fresh = validate_freshness(rolled)

    [report, fresh] >> publish()
    # notify watches the whole spine; it triggers on any upstream failure.
    [raw, cleaned, rolled, report, fresh] >> notify_on_failure()
