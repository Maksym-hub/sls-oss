# From Zero to Production Tutorial

This tutorial walks you through exploring slsflow locally, then deploying your first pipeline to AWS.

**Time required:** ~30 minutes (5 min local + 25 min AWS)

> **Just need commands?** See [QUICKSTART.md](QUICKSTART.md) for a 5-minute copy-paste version.
>
> **Starting from blank AWS account?** See [SETUP_FROM_SCRATCH.md](SETUP_FROM_SCRATCH.md) for complete setup (~1 hour).

---

## Prerequisites

1. **Python 3.11+** (that's it for Steps 1-2!)

For deployment (Steps 3+):
2. **AWS Account** with admin access
3. **AWS SAM CLI**
5. **AWS CLI** configured with credentials

---

## Step 1: Install slsflow (2 min)

```bash
mkdir my-pipelines && cd my-pipelines
python3 -m venv .venv
source .venv/bin/activate
pip install slsflow
python -c "from slsflow import DAG, task; print('✓ slsflow installed')"
```

---

## Step 2: Explore the DSL Locally (5 min)

No AWS account needed. Let's create a pipeline and explore what slsflow can do.

```bash
slsflow-init my-first-pipeline --local
cd my-first-pipeline
```

This generates `pipeline.py` — a working pipeline definition with placeholder ARNs. Let's explore:

```bash
slsflow-validate              # Validate the pipeline
slsflow-validate -v           # Verbose: tasks, deps, ASL preview
slsflow-output --json         # Full Step Functions JSON
slsflow-output --mermaid      # Generate a Mermaid diagram
slsflow-output --graph        # Show DAG as ASCII graph
```

### Edit the pipeline

Open `pipeline.py` and experiment:

```python
from slsflow import DAG, task, Asset


processed = Asset("my-data/processed")

with DAG(
    dag_id="my-first-pipeline",
    schedule="@daily",
    alerts={"slack": "#alerts"},
) as dag:

    @task.sfn(arn="arn:aws:states:us-east-1:123456789012:stateMachine:extract")
    def extract(): pass

    @task.sfn(
        arn="arn:aws:states:us-east-1:123456789012:stateMachine:transform",
        retries=2,                    # Retry on failure
        trigger_rule="all_success",   # Only run if extract succeeded
    )
    def transform(): pass

    @task.sfn(
        arn="arn:aws:states:us-east-1:123456789012:stateMachine:load",
        outlets=[processed],          # Emits asset event on success
    )
    def load(): pass

    extract() >> [transform(), load()]  # Fan-out
```

Run `slsflow-validate -v` to see how your changes affect the DAG.

At this point you understand the DSL. Ready to deploy? Continue below.

---

## Step 3: Configure Your Project (3 min)

Go back to the project root and create `config.py`:

```bash
cd ..  # back to my-pipelines/
```

```python
# config.py
ENVIRONMENTS = {
    "dev": {
        "namespace": "mycompany",
        "stage": "dev",
        "region": "us-east-1",
    },
}

DEFAULT_STAGE = "dev"
```

This is your **single source of truth** for all AWS configuration. Every pipeline reads from this file.

**What each key does:**
- `namespace` / `stage` — naming prefix for all AWS resources
- `region` — AWS region for deployment
- `roles` — cross-account IAM role shortcuts (optional)

---

## Step 4: Deploy Shared Infrastructure (10 min)

Shared infrastructure = the orchestration engine that runs all your pipelines.

```bash
cd sam
cp samconfig.toml.example samconfig.toml
# Edit samconfig.toml — set Namespace, Stage, SlackWebhookEndpoint
sam build && sam deploy
```

This creates: Step Functions helpers, DynamoDB tables, Lambda functions, API Gateway, and the Web Console.

---

## Step 5: Create Deploy-Ready Pipeline (5 min)

Now create a real pipeline that connects to your infrastructure:

```bash
cd ../../  # back to my-pipelines/
slsflow-init my-first-pipeline
cd my-first-pipeline
```

Edit `dag.py` — replace placeholder ARNs with real ones:

```python
from slsflow import DAG, task, config
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

with DAG(
    dag_id="my-first-pipeline",
    schedule="@daily",
    alerts={"slack": "#pipeline-alerts"},
) as dag:

    # Use full ARN directly — explicit and transparent
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-example-task")
    def extract(): pass

    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-example-task")
    def transform(): pass

    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-example-task")
    def load(): pass

    extract() >> transform() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

**Troubleshooting SSM parameters:**
- `"bucket not specified"` → add bucket to `config.py` ENVIRONMENTS
- `"Access Denied"` → check that `role_arn` has S3 read access to the state bucket

---

## Step 6: Deploy Pipeline

```bash
slsflow-deploy
```

---

## Step 7: Test Your Pipeline

### Via UI
1. Open Console URL (from `aws cloudformation describe-stacks --stack-name slsflow-dev --query "Stacks[0].Outputs" console_url`)
2. Click "my-first-pipeline"
3. Click "▶ Run"

### Via AWS Console
1. Open Step Functions
2. Find "mycompany-dev-slsflow-my-first-pipeline"
3. View executions

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `"Access Denied"` on deploy | Check AWS CLI profile and IAM permissions |
| Pipeline created but no runs | Check EventBridge rule in AWS Console |

See [TROUBLESHOOTING.md](../operations/TROUBLESHOOTING.md) for more.

---

## Next Steps

1. **DSL Reference** — [DSL.md](../features/DSL.md) — all task types, trigger rules, parameters
2. **Assets** — [ASSETS.md](../features/ASSETS.md) — cross-pipeline dependencies
3. **Configuration** — [CONFIGURATION.md](../reference/CONFIGURATION.md) — all config.py options
4. **Coming from Airflow** — [AIRFLOW_MIGRATION.md](../reference/AIRFLOW_MIGRATION.md) — concept mapping & honest differences

---

## Quick Reference

```python
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

# ARNs — use full ARN strings directly
f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-task"

# Cross-account role (from config.py ENVIRONMENTS roles dict)
role="etl"

# Dependencies
a >> b >> c           # Sequential
a >> [b, c]           # Fan-out
[a, b] >> c           # Fan-in

# Schedules
schedule="@daily"
schedule=[asset]      # Asset trigger
schedule=None         # Manual only
```
