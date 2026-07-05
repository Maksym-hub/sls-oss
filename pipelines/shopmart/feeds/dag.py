"""Shopmart Feeds Pipeline.

Generates customer feeds based on weekly data.

This pipeline demonstrates PUSH-BASED cross-pipeline dependency:
- Triggered automatically when shopmart/weekly-complete asset materializes
- No cron schedule — starts as soon as the weekly pipeline finishes
- Compare with acme-feeds which uses PULL-BASED (within days) dependency
"""
from polyris import DAG, task, Asset

TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"

# Cross-pipeline dependency (PUSH mode)
weekly_complete = Asset("shopmart/weekly-complete")

feed_retailers = Asset("shopmart/feeds/retailers")
feed_brands    = Asset("shopmart/feeds/brands")
feed_analytics = Asset("shopmart/feeds/analytics")
feed_exports   = Asset("shopmart/feeds/exports")
feeds_complete = Asset("shopmart/feeds-complete")

with DAG(
    dag_id="shopmart-feeds",
    schedule=weekly_complete,  # PUSH: triggered when weekly-complete materializes
    group="shopmart",
    description="Shopmart feeds — push-triggered by weekly pipeline completion"
) as dag:

    @task.sfn(arn=TEST_QUICK, outlets=[feed_retailers])
    def build_retailers_feed():
        """Generate retailers data feed."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[feed_brands])
    def build_brands_feed():
        """Generate brands data feed."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[feed_analytics])
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

    @task.sfn(arn=TEST_QUICK, inlets=[feed_exports], outlets=[feeds_complete])
    def mark_feeds_complete():
        """Mark feeds pipeline as complete."""
        pass

    ret = build_retailers_feed()
    brd = build_brands_feed()
    anl = build_analytics_feed()
    exp = build_exports([ret, brd, anl])
    mark_feeds_complete(exp)

# Deploy: polyris-deploy
