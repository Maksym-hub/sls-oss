# slsflow

**Orchestration without the orchestrator**

Serverless, asset-aware data pipelines on AWS Step Functions. No scheduler, no
workers, no metadata database to run — your pipelines compile to Step Functions,
and AWS runs them. Pay per run; idle cost is near zero.

If you've used Airflow, the `@task` / `>>` / `DAG()` DSL will feel familiar — but
slsflow is not managed Airflow. There's nothing to operate.

## Why slsflow

- 🪂 **Nothing to run** — no scheduler, workers, or metadata DB. Step Functions
  *is* the runtime, and it scales to zero between runs.
- 🔎 **Nothing hidden** — every pipeline compiles to a Step Functions state
  machine, so each run is a visible, debuggable execution history rather than
  opaque scheduler state.
- 🧬 **Asset-aware** — first-class data assets with lineage, partitions, and
  lineage-aware backfill (upstream smart-fill + downstream cascade), not just
  task graphs.
- 💸 **Pay-per-run** — a typical deployment runs ~$31/month; the floor is near
  zero because there is no always-on infrastructure.

## Features

- 🐍 **Familiar Python DSL** — `@task`, `>>` operators, `DAG()` context (Airflow-style ergonomics)
- 🚀 **One-command deploy** — `slsflow-deploy` (CloudFormation)
- 🤖 **AI Assistant** — Generate pipelines with natural language (FREE!)
- 🧪 **Local testing** — Validate, dry-run, mock execution
- 🔔 **Alerts required** — Slack and PagerDuty on failure (enforced per pipeline — no silent failures)
- 🎯 **11 trigger rules** — `all_success`, `one_failed`, `all_done`, etc. ([details](docs/features/DSL.md#trigger-rules))
- 🔗 **Automatic data passing** — task outputs flow to downstream tasks via a canonical output store in DynamoDB (up to 200KB)
- 📊 **Web Console** — pipelines, DAG view, Gantt, calendar, and the asset matrix (partition status across assets)
- 🧬 **Asset graph & lineage** — cross-pipeline dependencies and asset lineage
- ⏮️ **Lineage-aware backfill** — date-range backfill with task/asset selection, upstream smart-fill, downstream cascade, and partition granularity
- 🔗 **Pull-based deps** — `wait_for` with freshness and consecutive checks
- ⏭️ **Skip/Restart tasks** — partial pipeline runs via UI or API
- 🔄 **Auto-refresh UI** — polling-based updates (3s active, 30s idle)

---

## Where to Start

| I want to... | Go to |
|---|---|
| **Try slsflow without AWS** (explore DSL locally) | [Try It Now](#try-it-now) below |
| **Write a pipeline** (infra already deployed) | [Quick Start](#quick-start) below |
| **Set up slsflow from scratch** (blank AWS account) | [SETUP_FROM_SCRATCH.md](docs/getting-started/SETUP_FROM_SCRATCH.md) |
| **Learn step by step** with explanations | [TUTORIAL.md](docs/getting-started/TUTORIAL.md) |
| **Develop slsflow itself** (fix bugs, add features) | [CONTRIBUTING.md](CONTRIBUTING.md) |
| **Troubleshoot** a problem | [TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) |

---

## Try It Now

No AWS account needed. Explore the DSL, validate pipelines, generate Step Functions JSON — all locally.

```bash
pip install -e .
slsflow-init my-pipeline --local
cd my-pipeline
slsflow-validate              # Validate pipeline
slsflow-validate -v           # Verbose: tasks, deps, ASL preview
slsflow-output --json         # Full Step Functions JSON
slsflow-output --mermaid      # Generate diagram
slsflow-output --graph        # Show DAG as ASCII graph
```

Edit `dag.py` to experiment with task types, dependencies, trigger rules, and assets. When ready to deploy, see [Quick Start](#quick-start).

---

## Quick Start

> Assumes shared infrastructure is already deployed. Starting from scratch? See [SETUP_FROM_SCRATCH.md](docs/getting-started/SETUP_FROM_SCRATCH.md).

### 1. Install

```bash
pip install -e .
```

### 2. Configure (config.py)

```python
# config.py — in your pipelines repo root
ENVIRONMENTS = {
    "dev": {
        "namespace": "mycompany",
        "stage": "dev",
        "region": "us-east-1",
        # Cross-account role shortcuts (optional, used as role="etl" in tasks)
        "roles": {
            "etl": "arn:aws:iam::333333333333:role/cross-account-pipeline",
        },
    },
}

DEFAULT_STAGE = "dev"
```

### 3. Create pipeline

```bash
slsflow-init my-pipeline
```

This creates `my-pipeline/` with a working `dag.py`. Edit the task names and ARNs, then deploy with `slsflow-deploy`.

Or create manually — `my-pipeline/dag.py`:

```python
from slsflow import DAG, task, Asset


processed = Asset(name="my-pipeline/processed")

with DAG(
    dag_id="my-pipeline",
    schedule="@daily",
    alerts={
        "slack": "#alerts",
        # "slack_mentions": ["YOUR_SLACK_USER_ID"],  # optional: tag users/groups on failure
        # "pagerduty": "critical",  # optional: severity: critical | error | warning
    },
) as dag:

    # Same account — just the ARN
    @task.sfn(arn="arn:aws:states:us-east-1:111111111111:stateMachine:extract")
    def extract(): pass

    # Cross-account — role assumes into another account to run the SFN
    @task.sfn(
        arn="arn:aws:states:us-east-1:222222222222:stateMachine:transform",
        role="arn:aws:iam::222222222222:role/cross-account-pipeline",
    )
    def transform(): pass

    # role from config.py ENVIRONMENTS roles dict
    @task.sfn(
        arn="arn:aws:states:us-east-1:333333333333:stateMachine:load",
        role="etl",  # resolves from config.py ENVIRONMENTS["dev"]["roles"]["etl"]
        outlets=[processed],
    )
    def load(): pass

    extract() >> transform() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

<details>
<summary>Advanced: multi-stage pipeline (one file for dev + prod)</summary>

```python
from slsflow import DAG, task, config
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

with DAG("my-pipeline", schedule="@daily", alerts={"slack": "#alerts"}) as dag:

    # ARN uses STAGE to target correct environment
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-extract")
    def extract(): pass

    # Cross-account shorthand works the same way:
    #   role="etl" → resolves from config.py ENVIRONMENTS["dev"]["roles"]["etl"]
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-load", role="etl")
    def load(): pass

    extract() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

Deploy: `slsflow-deploy --stage dev`
</details>


### 4. Deploy

```bash
slsflow-deploy
```

### 5. Open Console

```bash
aws cloudformation describe-stacks --stack-name slsflow-dev --query "Stacks[0].Outputs[?OutputKey=='ConsoleUiUrl'].OutputValue" --output text
```

Pipeline runs daily at midnight, with automatic retries and alerts. Something broken? See [TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md).

---

## 🤖 AI Assistant (NEW!)

Generate pipelines with natural language. **100% FREE!**

```bash
# Install Ollama (one time)
curl -fsSL https://ollama.ai/install.sh | sh

# Run AI assistant
slsflow-ai
```

**Example session:**
```
You: /generate Daily ETL from S3 to Snowflake with Slack alerts

🤖 Assistant:
```python
from slsflow import DAG, task, config
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

with DAG("daily-etl", schedule="@daily", alerts={"slack": "#data"}) as dag:
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-s3-extract")
    def extract(): pass
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-snowflake-load")
    def load(): pass
    
    extract() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

See [AI_ASSISTANT.md](docs/tools/AI_ASSISTANT.md) for full documentation.

---

## 🧪 Local Testing

Test pipelines without deploying:

```python
from slsflow.local import validate, dry_run, run

# Validate DAG structure
validate(dag)

# Show execution plan
dry_run(dag)

# Mock execution
result = run(dag, mock=True)
print(result.summary())  # ✅ 3 succeeded, ❌ 0 failed
```

---

## Alerts Configuration

The `alerts` parameter is **required** for every DAG:

```python
# Slack only
with DAG("pipeline", alerts={"slack": "#alerts"}) as dag: ...

# With mentions — tag specific people/groups on failure
with DAG("pipeline", alerts={"slack": "#alerts", "slack_mentions": ["YOUR_SLACK_USER_ID", "S04ABCDEF"]}) as dag: ...

# PagerDuty only (severity: critical, error, warning, info)
with DAG("pipeline", alerts={"pagerduty": "critical"}) as dag: ...

# Both Slack and PagerDuty
with DAG("pipeline", alerts={"slack": "#critical", "pagerduty": "critical"}) as dag: ...

# Explicitly disabled (for test pipelines)
with DAG("test-pipeline", alerts=None) as dag: ...
```

`slack_mentions` accepts user IDs (`U...`), user group IDs (`S...`), `"here"`, or `"channel"`.
If omitted, no default mentions are used.

---

## Task Types

```python
# Step Function
@task.sfn(arn="arn:aws:states:...")
def my_task(): pass

# Lambda
@task.lambda_(function_name="my-function")
def process(): pass

# Glue
@task.glue(job_name="my-etl-job")
def etl(): pass

# ECS (Fargate)
@task.ecs(cluster="my-cluster", task_definition="my-task")
def container_job(): pass

# Athena
@task.athena(query_string="SELECT * FROM table", database="my_db")
def query(): pass

# EMR
@task.emr(emr_cluster_id="j-XXXXX", emr_step={...})
def spark_job(): pass

# AWS Batch
@task.batch(job_definition="my-job", job_queue="my-queue")
def batch_job(): pass
```

---

## Dependencies

```python
# Sequential
a >> b >> c

# Fan-out (one to many)
a >> [b, c, d]

# Fan-in (many to one)
[a, b, c] >> d

# Function call style
result = task_a()
task_b(result)
```

---

## Schedule Options

```python
# Time-based
DAG(schedule="@daily")                    # Midnight UTC
DAG(schedule="@hourly")                   # Every hour
DAG(schedule="cron(0 8 * * ? *)")         # 8:00 UTC daily
DAG(schedule="rate(6 hours)")             # Every 6 hours

# Asset-triggered
DAG(schedule=[processed_data])            # When asset ready
DAG(schedule=[asset_a & asset_b])         # When ALL ready (AND)
DAG(schedule=[asset_a | asset_b])         # When ANY ready (OR)

# Manual only
DAG(schedule=None)
```

---

## Asset-Based Orchestration

Cross-pipeline dependencies without hardcoded references:

```python
# Producer pipeline
processed = Asset(name="processed/acme")

with DAG("acme-daily", schedule="@daily", alerts={"slack": "#ch"}) as dag:
    @task.sfn(arn=..., outlets=[processed])
    def process(): pass
```

```python
# Consumer pipeline (triggered by asset)
processed = Asset(name="processed/acme")

with DAG("feeds", schedule=[processed], alerts={"slack": "#ch"}) as dag:
    @task.sfn(arn=...)
    def build_feeds(): pass
```

```python
# Pull-based dependencies (wait_for)
# Task waits for asset freshness before executing
daily_complete = Asset("acme/daily-complete")
weekly_complete = Asset("acme/weekly-complete")

with DAG("acme-weekly", schedule="cron(0 22 ? * SUN *)",
         alerts={"slack": "#data-alerts"}) as dag:
    @task.sfn(
        arn=...,
        wait_for=[daily_complete.consecutive(days=7)],  # Wait for 7 daily runs
        outlets=[weekly_complete]
    )
    def mark_weekly_complete(): pass
```

---

## Web Console

Access the console at your CloudFront URL. Features:

| View | Description |
|------|-------------|
| **🔀 DAG** | Interactive graph visualization (React Flow) |
| **📊 Gantt** | Timeline of task execution |
| **📅 Calendar** | Historical executions by date |
| **📦 Assets** | Asset lineage graph |
| **📋 Tasks** | All task instances across pipelines |
| **🏃 Runs** | All pipeline runs with filtering |

### Task Actions
- **Skip** — Mark task as skipped, continue pipeline
- **Fail** — Mark task as failed, continue pipeline
- **Stop** — Force stop running task
- **Restart** — Retry failed task

### Backfill (v0.78+ — unified seed-driven flow)

Backfill is a first-class operation in slsflow. One endpoint, one orchestrator
SFN, one persisted record (per ADR #51).

**From the UI:**
- Click **Backfill** on Pipeline page → opens with pipeline pre-selected
- Click **Backfill** on Asset Detail → opens with asset target + `cascade: auto`
- Click a **missing/failed cell** in Asset Matrix → opens with that exact partition
- Click **Backfill This Task** in Task Detail Modal → opens with task subset
- Browse `/backfills/` for history with status filters
- Drill into `/backfills/{id}/` for partition heatmap + cancel/retry

**From the CLI:**
```bash
export SLSFLOW_API_URL=https://<console-api>

slsflow backfill pipeline daily-etl --start 2024-01-15 --end 2024-01-20
slsflow backfill asset catalog/orders --start 2024-01-15 --end 2024-01-15 --cascade auto
slsflow backfills list --status active
slsflow backfills show bf-a1b2c3d4
slsflow backfills cancel bf-a1b2c3d4
slsflow backfills retry-failed bf-a1b2c3d4
```

**Features:**
- **Granularity-aware** — pipeline's cron schedule determines partition cadence
  (hourly/daily/weekly/monthly per ADR #52)
- **Cost preview** — `--preview` returns partition count + estimated SFN cost
  before commit
- **Cooperative cancel** — DDB-based; in-flight children complete, remaining
  partitions short-circuit
- **Retry-failed** — fork new backfill containing only failed partitions,
  linked via `parent_backfill_id`
- **Cascade** (asset target): `auto` (respect trigger rules) / `all` (force every
  consumer) / `none` (only rebuild this asset)
- **Hard limit**: 5000 partitions per backfill, soft warning at 500

---

## CLI Commands

Run from the pipeline directory:

```bash
# Validate pipeline
slsflow-validate

# Validate with details
slsflow-validate -v

# Validate all pipelines in project
slsflow-validate --all

# Generate Step Functions JSON
slsflow-output --json

# Generate Mermaid diagram
slsflow-output --mermaid

# Show DAG as ASCII graph
slsflow-output --graph

# Deploy pipeline
slsflow-deploy
slsflow-deploy --stage prod --profile my-profile

# Register pipeline in DynamoDB (manual)
slsflow-register --name my-pipeline
```

Backfill operations (v0.78+) — configure `SLSFLOW_API_URL`, then:

```bash
slsflow backfill pipeline daily-etl --start 2024-01-15 --end 2024-01-20
slsflow backfill asset catalog/db/orders --start 2024-01-15 --end 2024-01-15 --cascade auto
slsflow backfills list --status active
slsflow backfills show bf-a1b2c3d4
```

Full reference: [docs/reference/CLI.md](docs/reference/CLI.md)

---

## Project Structure

```
├── pipelines/                    # Pipeline definitions
│   ├── config.py                 # Shared config: ENVIRONMENTS, DEFAULT_STAGE
│   └── my-pipeline/
│       └── dag.py                # Pipeline definition
│
├── sam/                          # Shared infrastructure (SAM/CloudFormation)
│   ├── template.yaml             # SAM template (all AWS resources)
│   ├── samconfig.toml            # Deploy configuration
│   ├── samconfig.toml.example    # Example config
│   ├── lambdas/                  # 6 Lambda functions
│   └── sfn_templates/            # 13 SFN template files (16 SFNs total incl. 3 test)
│
├── slsflow/                      # Python DSL library
│   ├── dag.py                    # DAG class
│   ├── task.py                   # Task decorators
│   ├── assets.py                 # Asset definitions
│   └── generators.py             # ASL JSON generation
│
├── ui/                           # Web Console (React 19 + Next.js 16)
│   ├── deploy.sh                 # UI deploy script (S3 + CloudFront)
│   └── src/
│       ├── app/                  # Next.js App Router
│       └── components/           # React components
│
└── tests/                        # Test suite
```

---

## Deploy Infrastructure

```bash
cd sam
sam build && sam deploy
```

See [SETUP_FROM_SCRATCH.md](docs/getting-started/SETUP_FROM_SCRATCH.md) for full setup or [QUICKSTART.md](docs/getting-started/QUICKSTART.md) for fast path.

---

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](docs/getting-started/QUICKSTART.md) | 5-minute setup guide |
| [TUTORIAL.md](docs/getting-started/TUTORIAL.md) | From zero to production guide |
| [PROJECT_STRUCTURE.md](docs/getting-started/PROJECT_STRUCTURE.md) | Repository layouts, CI/CD |
| [DSL.md](docs/features/DSL.md) | Python DSL reference |
| [ASSETS.md](docs/features/ASSETS.md) | Asset-based orchestration |
| [ASSET_PULL_FEATURE.md](docs/features/ASSET_PULL_FEATURE.md) | wait_for / pull-based assets |
| [authentication.md](docs/features/authentication.md) | Cognito auth setup |
| [api-tokens.md](docs/features/api-tokens.md) | API tokens (PAT) for scripts/CI |
| [AI_ASSISTANT.md](docs/tools/AI_ASSISTANT.md) | AI pipeline generation (FREE!) |
| [LOCAL_TESTING.md](docs/tools/LOCAL_TESTING.md) | Local testing (validate, dry_run, mock) |
| [REGISTRATION.md](docs/tools/REGISTRATION.md) | Pipeline registration (CLI, auto) |
| [API.md](docs/operations/API.md) | REST API reference (52 endpoints) |
| [UI.md](docs/operations/UI.md) | Web Console guide |
| [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) | System architecture, diagrams |
| [STEP_FUNCTIONS.md](docs/architecture/STEP_FUNCTIONS.md) | ASL patterns and helpers |
| [BACKEND.md](docs/architecture/BACKEND.md) | Backend implementation details |
| [AIRFLOW_MIGRATION.md](docs/reference/AIRFLOW_MIGRATION.md) | Migration from Airflow |
| [DESIGN_DECISIONS.md](docs/reference/DESIGN_DECISIONS.md) | Key design decisions |
| [BACKLOG.md](docs/reference/BACKLOG.md) | Feature status and roadmap |

---

## Cost Comparison

| | Airflow (MWAA) | slsflow |
|---|----------------|---------|
| **Base cost** | ~$300/month | $0 |
| **Per pipeline run** | $0 (included) | ~$0.01 |
| **8 tasks, 1x/day, 30 days** | ~$300 | ~$0.50 |
| **Scaling** | Manual | Automatic |

---

## Requirements

- Python 3.11+
- AWS Account

```bash
pip install -e .          # pipeline development
pip install -e ".[dev]"   # slsflow development (adds pytest, ruff, mypy)
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and PR guidelines.

Quick start:
```bash
make test    # Run all tests
make check   # Lint + sync + test (before PR)
```

---

## License

MIT
