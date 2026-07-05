"""Linear ETL — extract → transform → load.

Dependencies are created by *calling* one task with another's result: the
output of `extract()` flows into `transform(...)`, and that flows into
`load(...)`. polyris compiles this into a Step Functions state machine where
each state passes its output to the next.

Run it locally (no AWS):  polyris-validate -v
"""
from polyris import DAG, task

# Reuse one worker state machine here for brevity; in practice each step is
# usually its own state machine. Replace with your real ARN(s).
ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:worker"

with DAG(
    dag_id="sales-etl",
    schedule="@daily",
    description="Extract sales, transform, then load — a classic linear ETL.",
) as dag:

    @task.sfn(arn=ARN)
    def extract():
        """Pull raw sales rows from the source system."""
        pass

    @task.sfn(arn=ARN)
    def transform():
        """Clean and aggregate the extracted rows."""
        pass

    @task.sfn(arn=ARN)
    def load():
        """Write the aggregated result to the warehouse."""
        pass

    # extract → transform → load
    raw = extract()
    clean = transform(raw)
    load(clean)
