# Configuration

SLSFlow uses `config.py` in your pipelines repo for project settings.

---

## Quick Start

```bash
# Generate config.py template
slsflow-init --project
```

Or create manually:

```python
# config.py (in your pipelines repo root)

ENVIRONMENTS = {
    "dev": {
        "namespace": "mycompany",
        "stage": "dev",
        "region": "us-east-1",
        "account_id": "111111111111",
        # "profile": "my-dev-profile",  # optional AWS profile
    },
    "prod": {
        "namespace": "mycompany",
        "stage": "prod",
        "region": "us-east-1",
        "account_id": "222222222222",
        # "profile": "my-prod-profile",
        # "roles": {
        #     "etl": "arn:aws:iam::123456789012:role/etl-role",
        # },
    },
}

DEFAULT_STAGE = "dev"
```

---

## Configuration Priority

1. **CLI arguments** — `--stage`, `--profile`, `--namespace`
2. **Environment variables** — `SLSFLOW_*`
3. **config.py** — `ENVIRONMENTS[stage]`

---

## Settings

| Setting | config.py key | Environment Variable | Default |
|---------|--------------|----------------------|---------|
| Namespace | `namespace` | `SLSFLOW_NAMESPACE` | `"slsflow"` |
| Stage | `stage` / `DEFAULT_STAGE` | `SLSFLOW_STAGE` | `"dev"` |
| Region | `region` | `SLSFLOW_REGION` | `"us-east-1"` |
| Profile | `profile` | `SLSFLOW_PROFILE` | `None` (AWS default) |
| Account ID | `account_id` | `SLSFLOW_ACCOUNT_ID` | `None` (no guard) |

When `account_id` is set, `slsflow-deploy` verifies that the AWS credentials resolve to the expected account before deploying. This prevents accidental deployment to the wrong account.

---

## Cross-Account Roles

```python
ENVIRONMENTS = {
    "prod": {
        "namespace": "mycompany",
        "stage": "prod",
        "region": "us-east-1",
        "roles": {
            "etl": "arn:aws:iam::123456789012:role/etl-execution-role",
            "analytics": "arn:aws:iam::456789012345:role/analytics-role",
        },
    },
}
```

Usage in pipeline:
```python
@task.sfn(
    arn="arn:aws:states:us-east-1:...",
    role="etl",  # key from config.py roles
)
```

---

## Multi-Stage Deploy

```bash
slsflow-deploy --stage dev
slsflow-deploy --stage prod
slsflow-deploy --stage prod --profile my-prod-profile  # override profile
```

---

## Environment Variables (CI/CD)

For GitHub Actions or other CI systems:

```yaml
- name: Deploy
  env:
    SLSFLOW_NAMESPACE: mycompany
    SLSFLOW_STAGE: prod
    AWS_PROFILE: prod
  run: slsflow-deploy
```

---

See [CLI.md](CLI.md) for full command options reference.
