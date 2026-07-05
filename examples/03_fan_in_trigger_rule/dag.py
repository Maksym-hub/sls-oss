"""Fan-out / fan-in with a trigger rule.

Three extracts run in parallel; a final `merge` task depends on all three.
`trigger_rule="all_done"` means merge runs once every upstream task has
*finished*, whether it succeeded or not — handy for cleanup or marker tasks.

Other rules include "all_success" (the default), "one_failed",
"one_success", "none_failed", ... see docs/features/DSL.md#trigger-rules.

Run it locally (no AWS):  polyris-output --graph
"""
from polyris import DAG, task

ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:worker"

with DAG(
    dag_id="multi-source-merge",
    schedule="@daily",
    description="Three parallel sources merged by an all_done marker task.",
) as dag:

    @task.sfn(arn=ARN)
    def extract_orders():
        """Extract orders."""
        pass

    @task.sfn(arn=ARN)
    def extract_returns():
        """Extract returns."""
        pass

    @task.sfn(arn=ARN)
    def extract_inventory():
        """Extract inventory."""
        pass

    @task.sfn(arn=ARN, trigger_rule="all_done")
    def merge():
        """Combine all three sources; runs even if some upstream failed."""
        pass

    # merge depends on all three parallel extracts (pass them as a list)
    merge([extract_orders(), extract_returns(), extract_inventory()])
