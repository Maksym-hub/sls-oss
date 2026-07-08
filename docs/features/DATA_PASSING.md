# Passing data between tasks

A task sends data by **returning** it. How a downstream task reads it depends on
size and task type — the common case needs zero setup.

## Default: it just arrives (zero setup)

For a Lambda (or nested Step Function) downstream task, Polyris reads the upstream
outputs for you and puts them in the task's input under `upstream`. Your task just
reads them — no permissions, no extra calls:

```python
@task.lambda_(function_name="extract")
def extract(event):
    return {"rows": 1240, "path": "s3://bucket/2026-07-07/data.parquet"}

@task.lambda_(function_name="load")
def load(event):
    up = event["upstream"]["extract"]["output"]   # {"rows": 1240, "path": ...}
    ...

extract >> load
```

Polyris (which already has access to the output store) does the read under its own
role, so **you add nothing** — this is the path for most pipelines.

Limits of the default: the injected payload is capped (~25 KB per upstream output),
and it is only delivered to **Lambda** and **Step Function** tasks. For larger
outputs or for **ECS / Glue / Batch** tasks, use `pull()` below.

## For large outputs or service tasks: `xcom.pull()`

`pull()` fetches an upstream output directly from the store (up to ~350 KB per
output) and works from any task type:

```python
from polyris import xcom

@task.lambda_(function_name="load")
def load(event):
    data = xcom.pull("extract", event)   # any size; works in ECS/Glue/Batch too
```

How to call it per task type (only *how the context arrives* differs):

| Task type | Call |
|-----------|------|
| Lambda    | `xcom.pull("upstream", event)` — pass the handler event |
| ECS / Glue / Batch | `xcom.pull("upstream")` — context comes from the environment / job args |

Because `pull()` reads the store itself, the task's execution role needs read
access. Polyris publishes a managed policy for this — `PolyrisTaskReadPolicy`
(exported as `${Namespace}-${Stage}-polyris-task-read-policy`, least privilege:
`dynamodb:GetItem` + `s3:GetObject`). Attach it to any task role that calls
`pull()`:

```yaml
ManagedPolicyArns:
  - !ImportValue <namespace>-<stage>-polyris-task-read-policy
```

(You only need this for the `pull()` path — the default injected `upstream` needs
nothing.)

## Determinism

Data flows from the logical run date, so both paths are deterministic and
backfill-safe. Avoid making a task's stored output depend on wall-clock time
(`now()`), which would make re-runs diverge.
