# Coming from Airflow

## Overview

slsflow's DSL deliberately mirrors Airflow's ergonomics (`@task`, `>>`, the
`DAG()` context), so the *authoring* experience will feel familiar. This guide
is for teams moving off Airflow — it maps the concepts you know onto slsflow.

slsflow is **not** Airflow-compatible, and this is not a drop-in migration. What
that means in practice:

- **Carries over:** the mental model and most authoring syntax — DAGs, tasks,
  the `>>` dependency operator, trigger rules, `@daily`-style schedules.
- **Does *not* carry over:** Airflow operators and providers (you wire AWS work
  via `@task.sfn` / Lambda etc., not `PythonOperator`/`*Operator`), the runtime
  (pipelines execute as Step Functions state machines — there is no Airflow
  scheduler, executor, or metadata DB), and anything that depends on Airflow's
  Python process model (custom XCom backends, plugins, `on_*_callback` hooks).

So treat this as a re-authoring guide, not a lift-and-shift. The payoff is that
once migrated there is no orchestrator to run — see the
[architecture overview](../architecture/ARCHITECTURE.md).

---

## Syntax Comparison

### DAG Definition

**Airflow:**
```python
from airflow import DAG
from datetime import datetime

with DAG(
    'my_pipeline',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={'retries': 2}
) as dag:
    ...
```

**slsflow:**
```python
from slsflow import DAG

with DAG(
    dag_id='my_pipeline',
    schedule='@daily',
    alerts={'slack': '#my-channel'},  # Required!
    catchup=False,
    default_args={'retries': 2}
) as dag:
    ...
```

**Key differences:**
- `alerts` parameter is required
- `schedule_interval` → `schedule`
- `start_date` not required (use EventBridge schedule)

---

### Task Definition

**Airflow:**
```python
from airflow.decorators import task

@task
def my_task():
    return "result"
```

**slsflow:**
```python
from slsflow import task

@task.sfn(arn="arn:aws:states:...")
def my_task():
    pass
```

**Key differences:**
- Must specify task type: `@task.sfn`, `@task.lambda_`, `@task.glue`, etc.
- For SFN tasks, must provide `arn`
- Task output is automatically passed to downstream tasks via DynamoDB (up to 200KB per task, similar to Airflow XCom)

---

### Dependencies

**Airflow:**
```python
task_a >> task_b >> task_c
[task_a, task_b] >> task_c
```

**slsflow:** Same syntax!
```python
task_a >> task_b >> task_c
[task_a, task_b] >> task_c
```

---

### Operators → Task Types

| Airflow Operator | slsflow Equivalent |
|------------------|-------------------|
| PythonOperator | `@task.lambda_` |
| BashOperator | `@task.ecs` or `@task.lambda_` |
| S3Operator | `@task.lambda_` |
| GlueJobOperator | `@task.glue` |
| EcsOperator | `@task.ecs` |
| AthenaOperator | `@task.athena` |
| EmrAddStepsOperator | `@task.emr` |
| BatchOperator | `@task.batch` |

---

### XCom → Built-in Data Passing

slsflow automatically passes task outputs between dependent tasks via DynamoDB — no extra setup needed.

**Airflow XCom:**
```python
@task
def produce():
    return {"key": "value"}

@task
def consume(data):
    print(data["key"])

data = produce()
consume(data)
```

**slsflow (automatic):**

Each downstream task receives an `upstream` object in its input with outputs from all dependencies:

```python
# Task A (child SFN) returns:
{"processed_count": 42, "output_path": "s3://bucket/output/"}

# Task B automatically receives in its input:
{
    "current_date": "2025-07-25",
    "upstream": {
        "task_a": {
            "output": {"processed_count": 42, "output_path": "s3://bucket/output/"},
            "status": "success"
        }
    }
}
```

**How it works:**
1. Task A completes → its output is saved to DynamoDB under a stable key (up to 200KB)
2. Task B starts → `Read_Upstream_Outputs` reads outputs from all direct dependencies
3. Task B's child SFN receives `upstream.task_a.output` in its input

Output is stored under a canonical key (`pipeline#task#date`), so it survives incremental backfill — if Task A is skipped because it already succeeded, Task B still reads the original output.

**For large data (>200KB):** Write to S3 and pass the path:

```python
# Task A returns a pointer:
{"output_path": "s3://bucket/output/2025-07-25/result.parquet"}

# Task B reads using the path from upstream
```

**Limits:** Each dependency output is capped at 25KB when read by downstream tasks (to stay within Step Functions' 256KB payload limit). The full output (up to 200KB) is preserved in DynamoDB — only the in-flight payload is trimmed. For large results, return S3 pointers instead of data.

**Supported task types:** `upstream` is passed to `sfn` and `lambda` task types. For `ecs`, `glue`, `athena`, `emr`, `batch` — use S3 pointers or task_config parameters instead (these AWS services have structured APIs that don't accept arbitrary JSON input).

---

### Sensors → Asset Triggers

**Airflow Sensor:**
```python
from airflow.sensors.s3_key_sensor import S3KeySensor

wait_for_file = S3KeySensor(
    task_id='wait_for_file',
    bucket_key='s3://bucket/data/{{ ds }}/file.csv',
    timeout=3600
)
```

**slsflow Asset:**
```python
from slsflow import Asset

data_file = Asset('data/daily')

# Producer pipeline
with DAG('producer', schedule='@daily', alerts={'slack': '#ch'}) as dag:
    @task.sfn(arn=..., outlets=[data_file])
    def produce():
        pass

# Consumer pipeline (triggered by asset)
with DAG('consumer', schedule=[data_file], alerts={'slack': '#ch'}) as dag:
    @task.sfn(arn=...)
    def consume():
        pass
```

---

### Trigger Rules

| Airflow | slsflow | Description |
|---------|---------|-------------|
| `all_success` | `all_success` | All deps succeeded (default) |
| `one_success` | `one_success` | At least one succeeded |
| `all_failed` | `all_failed` | All deps failed |
| `one_failed` | `one_failed` | At least one failed |
| `all_done` | `all_done` | All deps finished |
| `none_failed` | `none_failed` | No deps failed |
| `none_failed_min_one_success` | `none_failed_min_one_success` | None failed + one success |

---

## Migration Steps

### Step 1: Identify Task Types

Map your Airflow operators to slsflow task types:

```python
# Before: Airflow
from airflow.operators.python import PythonOperator

scrape = PythonOperator(
    task_id='scrape',
    python_callable=scrape_data
)

# After: slsflow (using Lambda)
@task.lambda_(function_name='scrape-function')
def scrape():
    pass
```

### Step 2: Move Logic to AWS Services

For Python tasks, create Lambda functions:

```python
# Lambda function: scrape-function/handler.py
def handler(event, context):
    # Your scrape logic
    return {'status': 'success'}
```

Or Step Functions:
```python
# Create a simple SFN that executes your logic
@task.sfn(arn='arn:aws:states:...:stateMachine:scrape')
def scrape():
    pass
```

### Step 3: Convert DAG

```python
# Before: Airflow
from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG('my_dag', schedule_interval='@daily') as dag:
    t1 = PythonOperator(task_id='task1', python_callable=func1)
    t2 = PythonOperator(task_id='task2', python_callable=func2)
    t1 >> t2

# After: slsflow
from slsflow import DAG, task

with DAG('my_dag', schedule='@daily', alerts={'slack': '#ch'}) as dag:
    @task.lambda_(function_name='func1')
    def task1(): pass
    
    @task.lambda_(function_name='func2')
    def task2(): pass
    
    t1 = task1()
    task2(t1)
```

### Step 4: Handle Inter-Task Communication

slsflow automatically passes task outputs via DynamoDB. Your child SFN/Lambda just needs to return JSON:

```python
# Task 1: Returns output (automatically saved to DynamoDB)
def task1_handler(event, context):
    result = process_data()
    return {"row_count": len(result), "output_path": f"s3://bucket/{event['current_date']}/"}

# Task 2: Reads upstream output (automatically injected)
def task2_handler(event, context):
    upstream = event.get("upstream", {})
    task1_output = upstream.get("task1", {}).get("output", {})
    output_path = task1_output.get("output_path")
    # Use output_path to read data
```

For large data (>200KB), return an S3 pointer instead of the data itself.

### Step 5: Convert Sensors to Assets

```python
# Before: Airflow sensor
sensor = ExternalTaskSensor(
    task_id='wait_for_upstream',
    external_dag_id='upstream_dag',
    external_task_id='final_task'
)

# After: slsflow asset
upstream_complete = Asset('upstream/complete')

# In upstream DAG
@task.sfn(arn=..., outlets=[upstream_complete])
def final_task(): pass

# In downstream DAG
with DAG('downstream', schedule=[upstream_complete], alerts={'slack': '#ch'}) as dag:
    ...
```

### Step 6: Add Alerts

```python
# Required for all DAGs
with DAG(
    'my_dag',
    schedule='@daily',
    alerts={
        'slack': '#my-channel',
        'slack_mentions': ['YOUR_SLACK_USER_ID'],  # Optional: tag users/groups
        'pagerduty': 'critical'  # Optional
    }
) as dag:
    ...
```

---

## Feature Comparison

| Feature | Airflow | slsflow |
|---------|---------|---------|
| Cost (idle) | ~$300/month (MWAA) | $0 |
| Scaling | Manual | Automatic |
| UI | Built-in | Web Console |
| Alerting | Callbacks | Slack + PagerDuty |
| Trigger Rules | ✓ | ✓ |
| XCom | ✓ | ✓ (via DynamoDB, automatic, up to 200KB) |
| Sensors | ✓ | Asset triggers |
| Backfill | ✓ | ✓ (with UI) |
| Pause/Resume | ✓ | ✓ |

---

## Not Supported

These Airflow features are not directly supported:

1. **Dynamic task generation** - Use Map state instead
2. **Task Instance retries** - Configure at task level
3. **SubDAGs** - Use nested Step Functions
4. **Pools** - Use Step Functions concurrency limits
5. **Connections/Hooks** - Use AWS Secrets Manager
6. **Variables (web UI)** - Use pipeline variables or SSM

### Built-in Task Variables

Every child task automatically receives date-derived variables (like Airflow's `{{ ds }}`, `{{ prev_ds }}`).

| Variable | Example | Airflow equivalent |
|---|---|---|
| `current_date` | 2026-02-18 | `{{ ds }}` |
| `previous_date` | 2026-02-17 | `{{ prev_ds }}` |
| `next_date` | 2026-02-19 | `{{ next_ds }}` |
| `date_compact` | 20260218 | `{{ ds_nodash }}` |
| `year`, `month`, `day` | 2026, 02, 18 | `{{ execution_date.year }}` |
| `day_of_week` | wednesday | — |
| `minus_7_days` | 2026-02-11 | `{{ macros.ds_add(ds, -7) }}` |

Full list and how to add new variables: `sam/lambdas/console_api/task_variables.py`

---

## Example: Full Migration

**Airflow DAG:**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.s3_key_sensor import S3KeySensor
from datetime import datetime

def extract_data(): ...
def transform_data(): ...
def load_data(): ...

with DAG(
    'etl_pipeline',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False
) as dag:
    
    wait = S3KeySensor(
        task_id='wait_for_source',
        bucket_key='s3://source/data/{{ ds }}/'
    )
    
    extract = PythonOperator(
        task_id='extract',
        python_callable=extract_data
    )
    
    transform = PythonOperator(
        task_id='transform',
        python_callable=transform_data
    )
    
    load = PythonOperator(
        task_id='load',
        python_callable=load_data
    )
    
    wait >> extract >> transform >> load
```

**slsflow DAG:**
```python
from slsflow import DAG, task, Asset

source_data = Asset('source/daily')
processed_data = Asset('processed/daily')

with DAG(
    'etl_pipeline',
    schedule=[source_data],  # Triggered by asset
    alerts={'slack': '#etl-alerts'},
    catchup=False
) as dag:
    
    @task.lambda_(function_name='extract-fn')
    def extract(): pass
    
    @task.glue(job_name='transform-job')
    def transform(): pass
    
    @task.lambda_(function_name='load-fn', outlets=[processed_data])
    def load(): pass
    
    e = extract()
    t = transform(e)
    load(t)
```
