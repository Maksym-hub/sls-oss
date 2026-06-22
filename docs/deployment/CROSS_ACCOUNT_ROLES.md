# Cross-Account Roles

SLSFlow supports executing tasks in different AWS accounts via cross-account IAM roles.

---

## Setup

### 1. Configure roles in `config.py`

```python
# config.py in your pipelines repo

ENVIRONMENTS = {
    "prod": {
        "namespace": "mycompany",
        "stage": "prod",
        "region": "us-east-1",
        "roles": {
            "etl":       "arn:aws:iam::111111111111:role/etl-execution-role",
            "analytics": "arn:aws:iam::222222222222:role/analytics-role",
        },
    },
}
```

### 2. Use in pipeline

```python
@task.sfn(
    arn="arn:aws:states:us-east-1:111111111111:stateMachine:etl-pipeline",
    role="etl",  # key from config.py roles
)
```

### 3. IAM trust policy in target account

The target account role must trust your SLSFlow orchestration role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::YOUR_ACCOUNT:role/YOUR_ORCHESTRATION_ROLE"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

---

## Environment Variable Override

```bash
export SLSFLOW_ROLE_ETL="arn:aws:iam::111111111111:role/etl-role"
```

Priority: env var > `config.py`.

---

## Verify Configuration

```bash
python3 -c "
from slsflow.config import config
c = config.for_stage('prod')
print(c.roles['etl'])
"
```
