# Project Structure

This guide covers different ways to organize slsflow projects.

## Installation

```bash
# From PyPI
pip install slsflow
```

## Structure Options

### Option A: Single Repository (Simple)

Best for: Small teams, getting started, monorepo setups.

```
mycompany-data/
├── pyproject.toml              # Python packaging + dev tools
├── config.py                   # slsflow project config (namespaces, stages, roles)
├── sam/
│   └── shared/                 # Shared infrastructure
│       ├── template.yaml    # SAM template
│       └── ...
│
├── pipelines/
│   ├── acme-daily/
│   │   ├── dag.py
│   │   └── │   └── nexus-hourly/
│       ├── dag.py
│       └── │
└── .github/
    └── workflows/
        └── ci.yml
```

**config.py** (root):
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

**Workflow:**
```bash
# 1. Deploy infrastructure (one-time)
cd sam
# Set Stage=dev in samconfig.toml
sam build && sam deploy

# 2. Create pipeline
cd ../pipelines
slsflow-init my-pipeline
cd my-pipeline

# 3. Deploy
slsflow-deploy
```

---

### Option B: Separate Repositories (Production)

Best for: Multiple teams, separate ownership.

```
# Repo 1: slsflow library (PyPI)
slsflow/
├── slsflow/
└── pyproject.toml

# Repo 2: Infrastructure (platform team)
slsflow-infra/
└── sam/
    ├── dev/shared/
    └── prod/shared/

# Repo 3: Pipelines (data team)
data-pipelines/
├── pyproject.toml              # Python packaging
├── config.py                   # slsflow project config
├── pipelines/
│   ├── acme-daily/
│   └── nexus-hourly/
└── .github/workflows/ci.yml
```

---

## Pipeline File Structure

Each pipeline needs a single `dag.py`:

```
my-pipeline/
└── dag.py     # Pipeline definition
```

**dag.py:**
```python
from slsflow import DAG, task
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

# Config from config.py ENVIRONMENTS

with DAG(
    dag_id="my-pipeline",
    schedule="@daily",
    alerts={"slack": "#alerts"}
) as dag:
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-extract-task")
    def extract(): pass
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-load-task")
    def load(): pass
    
    extract() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

---

## CI/CD

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install
        run: pip install -e ".[dev]"
      
      - name: Lint
        run: ruff check .
      
      - name: Test
        run: pytest tests/

  deploy-dev:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    env:
      SLSFLOW_STAGE: dev
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: pip install -e .
      - name: Deploy pipeline
        run: |
          cd pipelines/my-pipeline
          slsflow-deploy --stage dev
```

---

## Environment Management

### Via config.py + Environment Variables

`config.py` defines per-stage settings:

```python
# config.py
ENVIRONMENTS = {
    "dev": {"namespace": "mycompany", "stage": "dev", "region": "us-east-1"},
    "prod": {"namespace": "mycompany", "stage": "prod", "region": "us-east-1"},
}
DEFAULT_STAGE = "dev"
```

Override in CI or command line:
```bash
# Deploy to dev (default)
slsflow-deploy

# Deploy to prod
slsflow-deploy --stage prod

# Or via environment variable
export SLSFLOW_STAGE=prod
slsflow-deploy
```

In code:
```python
import os
STAGE = os.environ.get("SLSFLOW_STAGE", "dev")
f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-task"
```

---

## Best Practices

1. **One config.py** at repo root with all slsflow ENVIRONMENTS config
2. **One pipeline per folder** with a `dag.py`
3. **Use full ARN strings directly** — explicit and transparent
4. **Use environment variables** for stage/account overrides in CI
5. **Test locally** before deploying: `slsflow-validate -v`

---

## Next Steps

- [CONFIGURATION.md](../reference/CONFIGURATION.md) — All config options
- [TUTORIAL.md](TUTORIAL.md) — Step-by-step guide
- [DSL.md](../features/DSL.md) — Pipeline DSL reference
