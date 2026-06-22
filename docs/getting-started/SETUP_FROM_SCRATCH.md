# Complete Setup Guide (From Scratch)

Deploy slsflow to a blank AWS account. ~30-45 minutes.

---

## Overview

```
1. Prerequisites (5 min)     — AWS CLI, SAM CLI, Node.js
2. Configure (5 min)         — samconfig.toml, Slack webhook
3. Deploy Infrastructure (10 min) — sam build && sam deploy
4. Deploy UI (5 min)         — npm build + ui/deploy.sh
5. Create first user (5 min) — Cognito (if auth enabled)
6. Deploy first pipeline (5 min) — slsflow-deploy
```

---

## Step 1: Prerequisites

### AWS CLI
```bash
# macOS
brew install awscli

# Linux
pip install awscli

# Configure credentials
aws configure --profile slsflow-dev
# Enter: Access Key, Secret, region (e.g. us-east-1), output format (json)
```

### AWS SAM CLI
```bash
# macOS
brew tap aws/tap && brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Verify
sam --version   # must be >= 1.50.0
```

### Node.js (for UI build)
```bash
# via nvm (recommended)
nvm install 22 && nvm use 22

node --version  # must be >= 18.18 (22 LTS recommended)
```

---

## Step 2: Configure

### 2.1 Clone the repo

```bash
git clone https://github.com/your-org/slsflow.git
cd slsflow
```

### 2.2 Create samconfig.toml

```bash
cd sam
cp samconfig.toml.example samconfig.toml
```

Edit `samconfig.toml` — set the required values:

```toml
[default.deploy.parameters]
parameter_overrides = [
  "Namespace=myorg",         # prefix for all resource names: myorg-dev-slsflow-*
  "Stage=dev",               # dev | prod
  "AwsRegion=us-east-1",
  "SlackWebhookEndpoint=https://hooks.slack.com/services/...",  # required for alerts
  "DefaultSlackChannel=#pipeline-alerts",
  "EnableCognitoAuth=true",  # set false to skip auth during initial testing
]
```

Everything else in `samconfig.toml` (PagerDuty, custom domain, log levels) is optional.

### 2.3 Configure config.py

In the **pipelines repo root**, create `config.py`:

```python
# config.py
ENVIRONMENTS = {
    "dev": {
        "namespace": "myorg",
        "stage": "dev",
        "region": "us-east-1",
        # "profile": "my-aws-profile",  # optional
    },
    "prod": {
        "namespace": "myorg",
        "stage": "prod",
        "region": "us-east-1",
    },
}

DEFAULT_STAGE = "dev"
```

Or generate it automatically:
```bash
slsflow-init --project
```

This is read by `slsflow-deploy` when deploying pipelines.

### 2.4 Get a Slack webhook (if you don't have one)

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. **Incoming Webhooks** → toggle on → **Add New Webhook to Workspace**
3. Pick a channel (e.g. `#pipeline-alerts`) → **Allow**
4. Copy the webhook URL

Test it:
```bash
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"slsflow test"}' \
  https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Step 3: Deploy Infrastructure

```bash
cd sam
sam build && sam deploy --profile slsflow-dev
```

First deploy takes ~5-10 minutes. Creates:
- 7 DynamoDB tables
- 16 Step Functions state machines (13 templates + 3 test SFNs)
- 6 Lambda functions
- API Gateway, Cognito, S3, CloudFront

All outputs are written to SSM automatically:
```bash
# View stack outputs
aws cloudformation describe-stacks \
  --stack-name slsflow-dev \
  --query "Stacks[0].Outputs" \
  --output table \
  --profile slsflow-dev
```

---

## Step 4: Deploy UI

```bash
cd ../ui && npm ci && npm run build && ./deploy.sh --profile slsflow-dev
```

The script reads CloudFormation outputs, generates `config.js` with the real API Gateway URL and Cognito settings, uploads to S3, and invalidates CloudFront.

Output:
```
✅ UI deployed!
   URL: https://xxxx.cloudfront.net
   API: https://xxxx.execute-api.us-east-1.amazonaws.com/dev
```

Open the URL in your browser. You should see the slsflow Console.

---

## Step 5: Create First User (Cognito)

Skip if you set `EnableCognitoAuth=false`.

```bash
# Get User Pool ID
POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name slsflow-dev \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
  --output text \
  --profile slsflow-dev)

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com Name=email_verified,Value=true \
  --temporary-password "TempPass123!" \
  --profile slsflow-dev

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username admin@example.com \
  --password "YourSecurePassword123!" \
  --permanent \
  --profile slsflow-dev
```

Log in at the CloudFront URL.

> **For API/CLI/CI access** (not the browser), generate a Personal Access Token
> after logging in: avatar → **API Tokens** → Generate. Use it as
> `Authorization: Bearer slsf_…`. See
> [api-tokens.md](../features/api-tokens.md). (Auth is enforced only when
> `AUTH_ENABLED=true`.)

---

## Step 6: Deploy First Pipeline

```bash
cd ..   # repo root
pip install -e .

# Create a demo pipeline
cd pipelines
slsflow-init hello-world
cd hello-world

# Edit dag.py — set a real task ARN, or use the test SFN from outputs:
# TEST_QUICK_ARN=$(aws cloudformation describe-stacks --stack-name slsflow-dev \
#   --query "Stacks[0].Outputs[?OutputKey=='TestQuickSfnArn'].OutputValue" --output text)

slsflow-deploy --stage dev --profile slsflow-dev
```

Open the Console → see `hello-world` in the pipeline list → click **Run**.

---

## Multiple Environments

Each environment is a separate CloudFormation stack with its own `samconfig.toml`:

```bash
# dev — already done above

# prod
cp samconfig.toml samconfig.prod.toml
# Edit samconfig.prod.toml: Stage=prod, Namespace=myorg, different Slack channel, etc.

sam build
sam deploy --config-file samconfig.prod.toml --profile slsflow-prod
```

Pipelines target environments via `--stage`:
```bash
slsflow-deploy --stage prod --profile slsflow-prod
```

---

## Clean Up

```bash
# Remove pipelines first
cd pipelines/hello-world
slsflow-deploy --destroy --stage dev

# Remove infrastructure
cd sam
sam delete --stack-name slsflow-dev --profile slsflow-dev
```

---

## Next Steps

| I want to... | Go to |
|---|---|
| Write real pipelines | [TUTORIAL.md](TUTORIAL.md) |
| Learn the Python DSL | [DSL.md](../features/DSL.md) |
| Asset-based orchestration | [ASSETS.md](../features/ASSETS.md) |
| SAM parameters reference | [SAM.md](../deployment/SAM.md) |
| Something's broken | [TROUBLESHOOTING.md](../operations/TROUBLESHOOTING.md) |
