"""Acme Feeds Pipeline.

Generates customer data feeds based on weekly aggregated data.
Runs every Monday at 18:00 UTC.

This pipeline demonstrates PULL-BASED cross-pipeline dependency:
- Waits for acme/weekly-complete asset to be fresh (within 8 days)
- If asset is stale or missing, tasks wait until it's ready
- No direct pipeline coupling — only asset-level dependency
"""
from polyris import DAG, task, Asset

TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"

# Cross-pipeline dependency (PULL mode)
weekly_complete = Asset("acme/weekly-complete")

# Feed assets
feed_retailers = Asset("acme/feeds/retailers")
feed_brands    = Asset("acme/feeds/brands")
feed_analytics = Asset("acme/feeds/analytics")
feed_exports   = Asset("acme/feeds/exports")
feeds_complete = Asset("acme/feeds-complete")

with DAG(
    dag_id="acme-feeds",
    schedule="cron(0 18 ? * MON *)",
    group="acme",
    description="Acme feeds — pull-based dependency on weekly pipeline"
) as dag:

    @task.sfn(
        arn=TEST_QUICK,
        wait_for=[weekly_complete.within(days=8)],
        outlets=[feed_retailers]
    )
    def build_retailers_feed():
        """Generate retailers data feed. Waits for weekly data (max 8 days old)."""
        pass

    @task.sfn(
        arn=TEST_QUICK,
        wait_for=[weekly_complete.within(days=8)],
        outlets=[feed_brands]
    )
    def build_brands_feed():
        """Generate brands data feed. Waits for weekly data (max 8 days old)."""
        pass

    @task.sfn(
        arn=TEST_QUICK,
        wait_for=[weekly_complete.within(days=8)],
        outlets=[feed_analytics]
    )
    def build_analytics_feed():
        """Generate analytics data feed."""
        pass

    @task.sfn(
        arn=TEST_QUICK,
        inlets=[feed_retailers, feed_brands, feed_analytics],
        outlets=[feed_exports]
    )
    def build_exports():
        """Package and export all feeds."""
        pass

    @task.sfn(
        arn=TEST_QUICK,
        inlets=[feed_exports],
        outlets=[feeds_complete]
    )
    def mark_feeds_complete():
        """Mark feeds pipeline as complete."""
        pass

    ret  = build_retailers_feed()
    brd  = build_brands_feed()
    anl  = build_analytics_feed()
    exp  = build_exports([ret, brd, anl])
    mark_feeds_complete(exp)

# Deploy: polyris-deploy
