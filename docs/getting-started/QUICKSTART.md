# Quickstart

Deploy SLSFlow to your AWS account in ~10 minutes.

## Prerequisites

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Node.js 18.18+](https://nodejs.org/) (22 LTS recommended)
- AWS credentials configured (`aws configure`)

## 1. Clone

```bash
git clone https://github.com/your-org/slsflow
cd slsflow/sam
```

## 2. Configure

```bash
cp samconfig.toml.example samconfig.toml
```

Open `samconfig.toml` and set your values:

```toml
parameter_overrides = [
  "Namespace=myorg",    # your org prefix — used in all resource names
  "Stage=dev",          # dev or prod
  "AwsRegion=us-east-1",
  "EnableCognitoAuth=true",
]
```

Everything else is optional (Slack, PagerDuty, custom domain).

## 3. Deploy infrastructure

```bash
sam build && sam deploy
```

~3-5 minutes. Creates: DynamoDB, Lambda, Step Functions, API Gateway,
Cognito, S3, CloudFront.

SAM manages the artifacts bucket automatically — no manual S3 setup needed.

## 4. Deploy UI

```bash
cd ../ui && npm ci && npm run build && ./deploy.sh
```

The script:
- Reads API Gateway URL and Cognito settings from CloudFormation outputs
- Generates `config.js` with real values
- Uploads UI to S3
- Invalidates CloudFront cache

Output:
```
✅ UI deployed successfully!
   URL: https://xxxx.cloudfront.net
   API: https://xxxx.execute-api.us-east-1.amazonaws.com/dev
```

## 5. Create first user (if Cognito enabled)

```bash
# Get User Pool ID from stack outputs
POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name slsflow-dev \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
  --output text)

aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username your@email.com \
  --temporary-password TempPass123!
```

## 6. Deploy your first pipeline

```bash
cd pipelines/my-pipeline
slsflow-deploy
```

---

## Updating SLSFlow

**Infrastructure only:**
```bash
git pull && sam build && sam deploy
```

**UI only:**
```bash
git pull
cd ui && npm ci && npm run build && ./deploy.sh
```

**Both:**
```bash
git pull
cd sam && sam build && sam deploy
cd ../ui && npm ci && npm run build && ./deploy.sh
```
