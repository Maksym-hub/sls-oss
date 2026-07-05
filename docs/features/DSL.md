# polyris Python DSL Reference

## Overview

polyris provides a Python DSL for defining data pipelines that compile to AWS
Step Functions. The DSL borrows Airflow's ergonomics — `@task`, the `>>`
dependency operator, and a `DAG()` context manager — so it feels familiar if
you've used Airflow. It is *not* Airflow-compatible: pipelines run on Step
Functions (not an Airflow scheduler/executor), and Airflow operators/providers
do not carry over.

---

## DAG Definition

```python
from polyris import DAG, task, Asset

with DAG(
    dag_id="my-pipeline",
    schedule="@daily",
    description="My data pipeline",
    tags=["production", "etl"],
    variables={
        "custom_var": "value"
    }
) as dag:
    ...
```

### DAG Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dag_id` | str | Yes | Unique pipeline identifier |
| `schedule` | str/Asset/list | No | Schedule: cron, preset, or assets |
| `alerts` | dict/None | No | **Deprecated** (ADR #103) — ignored; configure alerts in Settings → Alerts |
| `description` | str | No | Human-readable description |
| `tags` | list | No | Tags for organization |
| `variables` | dict | No | Pipeline variables |
| `catchup` | bool | No | Enable backfill (default: True) |
| `max_active_tasks` | int | No | Max concurrent tasks (default: 16) |
| `default_args` | dict | No | Default params for all tasks (see below) |

### Default Args

Apply shared parameters to all tasks in a DAG:

```python
from datetime import timedelta

with DAG(
    "my-pipeline",
    schedule="@daily",
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
        "execution_timeout": timedelta(hours=4),
        "orchestration_timeout": timedelta(hours=12),  # Wait for deps up to 12h
    }
) as dag:
    # All tasks inherit these defaults unless overridden
    @task.sfn(arn=..., retries=0)  # Override: no retries for this task
    def fragile_task(): pass
```

### Alerts Configuration

> **Deprecated (ADR #103).** The `alerts=` argument is no longer used. It is
> accepted for one release with a `DeprecationWarning` and then ignored — remove
> it from your DAGs. Alert delivery moved out of the DSL:
>
> - **Browser notifications** (in-app) are automatic and free — no setup.
> - **Slack / PagerDuty** are configured per-pipeline in the UI under
>   **Settings → Alerts** (Team tier), not in code. There you set the channel,
>   mentions, severity, channel mode, and the webhook / routing key (stored as
>   SSM secrets — only the parameter name is kept in the registry).
>
> Old DAGs that still pass `alerts={...}` keep importing; the argument is dropped
> at parse time with a warning. See the Settings → Alerts how-to for the new flow.

## Schedule Options

### Time-Based (EventBridge)

```python
# Presets
DAG(schedule="@daily")      # cron(0 0 * * ? *)
DAG(schedule="@hourly")     # cron(0 * * * ? *)
DAG(schedule="@weekly")     # cron(0 0 ? * SUN *)

# Custom cron
DAG(schedule="cron(0 8 * * ? *)")   # 8:00 UTC daily

# Rate expressions
DAG(schedule="rate(6 hours)")
DAG(schedule="rate(1 day)")
```

### Asset-Based (Cross-Pipeline Triggers)

```python
from polyris import Asset

asset_a = Asset("processed/acme")
asset_b = Asset("processed/ulta")

# Single asset (OR)
DAG(schedule=asset_a)

# Multiple assets - ALL required (AND)
DAG(schedule=[asset_a & asset_b])

# Multiple assets - ANY triggers (OR)
DAG(schedule=[asset_a | asset_b])
```

### Manual Only

```python
DAG(schedule=None)  # No automatic trigger
```

---

## Task Types

### Step Function Task

```python
@task.sfn(
    arn="arn:aws:states:us-east-1:123456789:stateMachine:my-sfn",
    execution_timeout=timedelta(hours=1),
    retries=2,
    wait_before=60,
    trigger_rule="all_success",
    outlets=[my_asset]
)
def my_task():
    pass
```

### Lambda Task

```python
@task.lambda_(
    function_name="my-function",
    payload={"key": "value"}
)
def process_data():
    pass
```

### Glue Task

```python
@task.glue(
    job_name="my-etl-job",
    arguments={"--key": "value"},
    worker_type="G.1X",
    number_of_workers=2
)
def etl_job():
    pass
```

### ECS Task

```python
@task.ecs(
    cluster="my-cluster",
    task_definition="my-task:1",
    launch_type="FARGATE",          # FARGATE requires at least one subnet
    subnets=["subnet-xxx"],
    security_groups=["sg-xxx"],
    assign_public_ip="ENABLED",     # ENABLED for a public subnet without a NAT gateway
    container_overrides={
        "containerOverrides": [{
            "name": "main",
            "command": ["python", "script.py"]
        }]
    }
)
def container_job():
    pass
```

`NetworkConfiguration` is sent only when `subnets` are provided; EC2 launch type
with `bridge`/`host` networking can omit them.

### Athena Task

```python
@task.athena(
    query_string="SELECT * FROM my_table",
    database="my_database",
    output_location="s3://bucket/output/",
    workgroup="primary"
)
def run_query():
    pass
```

Omit `output_location` to use the workgroup's enforced output location — the
wrapper then omits `ResultConfiguration` rather than sending an empty
`OutputLocation` (which `StartQueryExecution` rejects).

### EMR Task

```python
@task.emr(
    emr_cluster_id="j-XXXXXXXXXXXXX",
    emr_step={
        "Name": "Spark Job",
        "ActionOnFailure": "CONTINUE",
        "HadoopJarStep": {
            "Jar": "command-runner.jar",
            "Args": ["spark-submit", "s3://bucket/script.py"]
        }
    }
)
def spark_job():
    pass
```

### AWS Batch Task

```python
@task.batch(
    job_definition="my-job-def",
    job_queue="my-queue",
    batch_parameters={"param1": "value1"}
)
def batch_job():
    pass
```

---

## Task Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `arn` | str | - | Step Function ARN (for sfn type) |
| `execution_timeout` | timedelta | 24 hours | Max task execution time |
| `orchestration_timeout` | timedelta | same as execution_timeout | Max time waiting for dependencies |
| `retries` | int | 0 | Number of retry attempts |
| `retry_delay` | timedelta | 5 minutes | Delay between retries (base delay when backoff is on) |
| `retry_exponential_backoff` | bool | False | Double the wait each retry: `min(retry_delay·2^n, max_retry_delay)` |
| `max_retry_delay` | timedelta | none (3600s cap) | Ceiling for exponential backoff |
| `retry_jitter` | bool | False | Randomise each wait into `[base/2, base)` (avoids retry stampede) |
| `wait_before` | int | 0 | Wait N seconds before executing |
| `trigger_rule` | str | "all_success" | When to trigger task (see table below) |
| `role` | str | "same" | Cross-account role: 'acq', 'etl', 'same' |
| `outlets` | list | [] | Assets produced by this task |
| `inlets` | list | [] | Assets consumed by this task |
| `wait_for` | list | [] | Assets to wait for: `[asset]`, `[asset.within(hours=24)]`, `[asset.consecutive(days=7)]` |
| `skip_on_backfill` | bool | False | Skip this task by default during backfill |

```python
from datetime import timedelta

@task.sfn(
    arn="arn:aws:states:us-east-1:123456789:stateMachine:my-sfn",
    execution_timeout=timedelta(hours=2),
    orchestration_timeout=timedelta(days=3),  # Long wait for cross-pipeline deps
    retries=2,
    retry_delay=timedelta(minutes=10),
    wait_before=60,
    trigger_rule="all_success",
    outlets=[my_asset]
)
def my_task():
    pass
```

---

## Trigger Rules

> **Full Airflow parity** — polyris supports all 11 trigger rules from Apache Airflow.
> This is unique among serverless orchestrators; Prefect and Dagster have no equivalent.

| Rule | Description | Use Case |
|------|-------------|----------|
| `all_success` | All deps must succeed (default) | Standard ETL: extract → transform → load |
| `one_success` | At least one dep succeeded (immediate!) | Redundant sources: run if any data arrived |
| `all_done` | All deps finished (any status) | Cleanup: always run after pipeline, even on failure |
| `all_done_min_one_success` | All done + at least one success | Report: send results even if some branches failed |
| `one_done` | At least one dep finished (any status, immediate!) | Fan-out monitoring: react as soon as any task completes |
| `one_failed` | At least one dep failed (immediate!) | Alert: notify immediately when first failure happens |
| `all_failed` | All deps failed | Fallback: activate only when everything else failed |
| `none_failed` | No deps failed | Safe continue: proceed if nothing went wrong |
| `none_failed_min_one_success` | None failed + at least one success | Conditional merge: combine results from optional branches |
| `all_skipped` | All deps skipped | Skip handler: run only when entire branch was skipped |
| `none_skipped` | No deps skipped | Strict pipeline: ensure every step actually ran |

### Examples

```python
# Cleanup that always runs (teardown pattern)
@task.sfn(arn=..., trigger_rule="all_done")
def cleanup():
    """Tear down resources regardless of success/failure."""
    pass

# Alert on first failure (don't wait for other tasks)
@task.lambda_(function_name=f"alert-{STAGE}", trigger_rule="one_failed")
def alert_on_failure():
    """Send immediate Slack alert."""
    pass

# Fallback data source
@task.sfn(arn=..., trigger_rule="all_failed")
def use_cached_data():
    """Only use cache if all primary sources failed."""
    pass

# Safe merge from optional branches
@task.sfn(arn=..., trigger_rule="none_failed_min_one_success")
def merge_results():
    """Combine outputs from whichever branches ran successfully."""
    pass
```

---

## Dependencies

### Bitshift Operators

```python
# Sequential
task_a >> task_b >> task_c

# Fan-out (one to many)
task_a >> [task_b, task_c, task_d]

# Fan-in (many to one)
[task_a, task_b, task_c] >> task_d

# Mixed
task_a >> [task_b, task_c] >> task_d
```

### Function Call Style (Airflow 2.0+)

```python
@task.sfn(arn=...)
def extract(): pass

@task.sfn(arn=...)
def transform(): pass

@task.sfn(arn=...)
def load(): pass

# Dependencies via function calls
data = extract()
transformed = transform(data)
load(transformed)
```

### List of Dependencies

When a task depends on multiple upstream tasks:

```python
@task.sfn(arn=...)
def build_a(): pass

@task.sfn(arn=...)
def build_b(): pass

@task.sfn(arn=...)
def build_c(): pass

@task.sfn(arn=...)
def aggregate(): pass

# All three syntaxes work:
a, b, c = build_a(), build_b(), build_c()

# Option 1: List argument
aggregate([a, b, c])

# Option 2: Multiple arguments
aggregate(a, b, c)

# Option 3: Bitshift operator
[a, b, c] >> aggregate()
```

---

## Assets

### Definition

```python
from polyris import Asset

# Simple asset
processed = Asset(name="processed/acme")

# Asset with URI
processed = Asset(
    name="processed/acme",
    uri="s3://bucket/processed/acme/"
)

# Asset with group (for UI organization)
processed = Asset(
    name="processed/acme",
    group="acme"
)
```

### Producer Task (outlets)

```python
@task.sfn(arn=..., outlets=[processed])
def process_data():
    """Emits asset event when task completes."""
    pass
```

### Consumer DAG (schedule)

```python
with DAG(
    "feeds",
    schedule=[processed],  # Triggered when processed is ready
) as dag:
    ...
```

---

## Variables

### Pipeline Variables

```python
with DAG(
    "my-pipeline",
    variables={
        "current_date": "{% $substringBefore($now(), 'T') %}",
        "environment": "prod"
    }
) as dag:
    ...
```

### Auto Variables (in backfill)

When running backfill, these variables are auto-generated:

| Variable | Example | Description |
|----------|---------|-------------|
| `current_date` | "2025-07-25" | Execution date |
| `date_compact` | "20250725" | YYYYMMDD format |
| `year` | "2025" | Year |
| `month` | "07" | Month |
| `day` | "25" | Day |
| `day_of_week` | "friday" | Lowercase weekday |
| `previous_date` | "2025-07-24" | Day before |
| `minus_7_days` | "2025-07-18" | 7 days ago |
| `minus_30_days` | "2025-06-25" | 30 days ago |
| `is_backfill` | true | Backfill flag |

---

## Complete Example

```python
from polyris import DAG, task, Asset
import os

STAGE = os.environ.get("POLYRIS_STAGE", "dev")

# Assets
raw_data = Asset("raw/acme", group="acme")
processed = Asset("processed/acme", group="acme")

with DAG(
    dag_id="acme-etl",
    schedule="@daily",
    description="Acme ETL pipeline",
    tags=["production", "acme"]
) as dag:
    
    @task.sfn(
        arn=f"arn:aws:states:us-east-1:123456789:stateMachine:scrape-{STAGE}",
        skip_on_backfill=True
    )
    def scrape():
        """Scrape product data."""
        pass
    
    @task.sfn(
        arn=f"arn:aws:states:us-east-1:123456789:stateMachine:process-{STAGE}",
        outlets=[raw_data],
        retries=2
    )
    def process():
        """Process raw data."""
        pass
    
    @task.glue(
        job_name=f"transform-{STAGE}",
        outlets=[processed],
        trigger_rule="all_success"
    )
    def transform():
        """Transform to final format."""
        pass
    
    @task.lambda_(function_name=f"notify-{STAGE}", trigger_rule="all_done")
    def notify():
        """Send completion notification."""
        pass
    
    # Dependencies
    s = scrape()
    p = process(s)
    t = transform(p)
    notify(t)

# Deploy
# Deploy: polyris-deploy --stage $STAGE
```

---

## CLI Usage

Run these from the pipeline directory:

```bash
# Validate pipeline
polyris-validate

# Validate with details
polyris-validate -v

# Generate Step Functions JSON
polyris-output --json

# Generate Mermaid diagram
polyris-output --mermaid

# Show DAG as ASCII graph
polyris-output --graph

# Generate asset registry JSON
polyris-output --assets

# Deploy
polyris-deploy --stage dev
```
