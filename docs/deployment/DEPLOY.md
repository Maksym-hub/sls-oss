# slsflow-deploy — CloudFormation Pipeline Deployment

CloudFormation-based pipeline deployment. AWS manages state natively.

- No external tools needed beyond AWS CLI
- Same workflow as `sam deploy` for shared infra

## Usage

```bash
# Deploy from pipeline directory (uses config.py defaults)
cd pipelines/acme/daily
slsflow-deploy

# Deploy to specific stage
slsflow-deploy --stage prod

# Override AWS profile
slsflow-deploy --profile my-aws-profile

# Stage + profile
slsflow-deploy --stage prod --profile my-aws-profile

# Preview without deploying
slsflow-deploy --dry-run

# Remove pipeline
slsflow-deploy --destroy

# Multi-DAG file — deploy specific DAG
slsflow-deploy --select acme-daily
```

See [CLI.md](../reference/CLI.md) for full options reference.

## What it deploys

For each pipeline:
- `AWS::StepFunctions::StateMachine` — the pipeline
- `AWS::Logs::LogGroup` — CloudWatch logs
- `AWS::Events::Rule` — EventBridge schedule (if `schedule` set)

State is managed by CloudFormation — create, update, and delete handled automatically.

## Prerequisites

1. Shared infra deployed: `sam deploy` (writes SSM parameters)
2. AWS credentials configured: `aws configure`
3. slsflow installed: `pip install slsflow`

## Pipeline file

Standard `dag.py` format:

```python
from slsflow import DAG, task
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

with DAG("acme-daily", schedule="@daily", alerts={"slack": "#alerts"}) as dag:
    @task.sfn(arn="arn:aws:states:...")
    def my_task(): pass
    my_task()

# No deploy() call needed — slsflow-deploy reads the DAG automatically
```

