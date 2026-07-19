"""Branching & trigger rules — fan-out, fan-in, and conditional merges.

Real pipelines rarely run in a straight line. Here one task fans out to several
parallel branches, the branches fan back in, and `trigger_rule` controls *when*
the downstream tasks run:

  - the merge waits for every branch to finish (`all_done`)
  - a cleanup task runs whether or not things succeeded (`all_done`)
  - an alert task fires only if a branch failed (`one_failed`)

`chain()` and `cross_downstream()` are helpers for wiring dependencies without a
wall of `>>`.

Run it locally (no AWS):  polyris-validate -v
"""
from polyris import DAG, task, chain, cross_downstream

# NOTE: ARNs below are hardcoded to the testing-infra CloudFormation stack.
ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:polyris-test-sfn"

with DAG(
    dag_id="branching-demo",
    schedule="@hourly",
    description="Fan-out to parallel branches, fan back in with trigger rules.",
    tags=["example", "branching"],
) as dag:

    @task.sfn(arn=ARN)
    def start():
        """Single entry point; fans out to three branches."""
        pass

    @task.sfn(arn=ARN)
    def branch_a():
        pass

    @task.sfn(arn=ARN)
    def branch_b():
        pass

    @task.sfn(arn=ARN)
    def branch_c():
        pass

    @task.sfn(arn=ARN, trigger_rule="all_done")
    def merge():
        """Runs once every branch has finished, success or not."""
        pass

    @task.sfn(arn=ARN, trigger_rule="one_failed")
    def alert_on_failure():
        """Fires only if at least one branch failed."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_done")
    def cleanup():
        """Always runs at the end — tear down temp resources."""
        pass

    s = start()
    a, b, c = branch_a(), branch_b(), branch_c()
    m, alert, done = merge(), alert_on_failure(), cleanup()

    # start → (a, b, c): one upstream fanning out to many.
    cross_downstream([s], [a, b, c])
    # (a, b, c) → merge, and (a, b, c) → alert_on_failure.
    [a, b, c] >> m
    [a, b, c] >> alert
    # merge → cleanup: linear tail.
    chain(m, done)

    # Data flows along every edge, not just call-style ones: `>>` and
    # `cross_downstream` make the upstream's output available too. So each branch
    # reads `$states.input.upstream.start.output`, and `merge` (a fan-in) reads all
    # three branches under `upstream` — the same way as example 03. `cleanup`
    # depends only on ordering; it can ignore `upstream` entirely.
