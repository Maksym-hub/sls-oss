"""Shopmart Weekly Pipeline.

Waits for 7 consecutive daily completions, then emits weekly_complete.
Triggered automatically when shopmart/weekly-complete materializes (PUSH mode).

This pipeline demonstrates PUSH-BASED cross-pipeline orchestration:
- The feeds pipeline subscribes to this asset
- No cron needed on feeds — it starts automatically when this emits
"""
from polyris import DAG, task, Asset

TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"

daily_complete  = Asset("shopmart/daily-complete")
weekly_complete = Asset("shopmart/weekly-complete")

with DAG(
    dag_id="shopmart-weekly",
    schedule="cron(0 22 ? * SUN *)",
    group="shopmart",
    description="Shopmart weekly — waits for 7 consecutive daily completions"
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
