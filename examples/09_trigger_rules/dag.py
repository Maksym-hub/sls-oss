"""Trigger-rule reference — every fan-in condition in one DAG.

A downstream task's `trigger_rule` decides *when* it runs relative to its
upstream tasks' outcomes. The default is `all_success`. Two upstream tasks
(`extract_a`, `extract_b`) feed one marker task per rule, so you can see each
condition side by side.

The ten rules (see docs/features/DSL.md#trigger-rules):

  all_success                  all upstreams succeeded (DEFAULT)
  all_failed                   all upstreams failed / upstream_failed
  all_done                     all upstreams finished (success or not)
  all_done_min_one_success     all finished AND at least one succeeded
  all_skipped                  all upstreams were skipped
  one_failed                   at least one failed (does not wait for the rest)
  one_success                  at least one succeeded (does not wait for the rest)
  one_done                     at least one finished (does not wait for the rest)
  none_failed                  nothing failed (success or skipped are OK)
  none_failed_min_one_success  nothing failed AND at least one succeeded

Run it locally (no AWS):  polyris-output --graph
"""
from polyris import DAG, task

# NOTE: placeholder ARN — replace with your own state machine before deploying.
ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:polyris-test-sfn"

with DAG(
    dag_id="trigger-rules-reference",
    schedule="@daily",
    description="One downstream marker per trigger rule, fed by two extracts.",
) as dag:

    @task.sfn(arn=ARN)
    def extract_a():
        """First upstream source."""
        pass

    @task.sfn(arn=ARN)
    def extract_b():
        """Second upstream source."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_success")
    def on_all_success():
        """Runs only if BOTH extracts succeeded (this is the default rule)."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_failed")
    def on_all_failed():
        """Runs only if BOTH extracts failed — e.g. an escalation/alert path."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_done")
    def on_all_done():
        """Runs once both finished, success or not — e.g. cleanup / marker."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_done_min_one_success")
    def on_all_done_min_one_success():
        """Runs once both finished AND at least one succeeded."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_skipped")
    def on_all_skipped():
        """Runs only if both upstreams were skipped."""
        pass

    @task.sfn(arn=ARN, trigger_rule="one_failed")
    def on_one_failed():
        """Fires as soon as any upstream fails — fast-fail alerting."""
        pass

    @task.sfn(arn=ARN, trigger_rule="one_success")
    def on_one_success():
        """Fires as soon as any upstream succeeds — first-wins pattern."""
        pass

    @task.sfn(arn=ARN, trigger_rule="one_done")
    def on_one_done():
        """Fires as soon as any upstream finishes, whatever the outcome."""
        pass

    @task.sfn(arn=ARN, trigger_rule="none_failed")
    def on_none_failed():
        """Runs if nothing failed (successes and skips are both fine)."""
        pass

    @task.sfn(arn=ARN, trigger_rule="none_failed_min_one_success")
    def on_none_failed_min_one_success():
        """Runs if nothing failed AND at least one upstream actually succeeded."""
        pass

    # Every marker depends on the same two extracts; only the trigger_rule differs.
    upstreams = [extract_a(), extract_b()]
    on_all_success(upstreams)
    on_all_failed(upstreams)
    on_all_done(upstreams)
    on_all_done_min_one_success(upstreams)
    on_all_skipped(upstreams)
    on_one_failed(upstreams)
    on_one_success(upstreams)
    on_one_done(upstreams)
    on_none_failed(upstreams)
    on_none_failed_min_one_success(upstreams)
