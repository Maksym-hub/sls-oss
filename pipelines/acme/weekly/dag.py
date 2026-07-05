"""Acme Weekly Pipeline.

Waits for 7 consecutive daily completions via asset consecutive() check,
then emits weekly_complete to trigger the downstream feeds pipeline.

Runs every Sunday at 22:00 UTC.

This pipeline demonstrates:
- Asset.consecutive(days=N) for cross-day dependency checks
- Cross-pipeline orchestration (weekly triggers feeds)
"""
from polyris import DAG, task, Asset

TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"

daily_complete  = Asset("acme/daily-complete")
weekly_complete = Asset("acme/weekly-complete")

with DAG(
    dag_id="acme-weekly",
    schedule="cron(0 22 ? * SUN *)",
    group="acme",
    description="Acme weekly — waits for 7 consecutive daily completions"
) as dag:

    @task.sfn(
        arn=TEST_QUICK,
        wait_for=[daily_complete.consecutive(days=7)],
        outlets=[weekly_complete]
    )
    def mark_weekly_complete():
        """Emit weekly_complete when all 7 daily runs are done."""
        pass

    mark_weekly_complete()

# Deploy: polyris-deploy
