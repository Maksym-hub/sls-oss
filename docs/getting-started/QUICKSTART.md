# Quickstart

Deploy Polyris to your AWS account in ~10 minutes.

## Prerequisites

- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Node.js 18.18+](https://nodejs.org/) (22 LTS recommended)
- AWS credentials configured (`aws configure`)

## 1. Clone

```bash
# TODO(release): replace `polyris` with the real GitHub org before publishing
git clone https://github.com/polyris/polyris
cd polyris/sam
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

> `samconfig.toml` has a `stack_name` (the example: `polyris-dev`) — your
> CloudFormation stack name. `sam` reads it from there. But `./deploy.sh` and the
> `describe-stacks` lookups don't, so set it once here and pass it to them (rename
> it in samconfig → use the same name, or those lookups fail):

```bash
STACK_NAME=polyris-dev    # = stack_name in samconfig.toml
AWS_REGION=us-east-1      # = AwsRegion in samconfig.toml
# Using a named AWS profile? Add `--profile NAME` to the commands below.
```

## 3. Deploy infrastructure

```bash
sam build
sam deploy   # reads stack name, region, and parameters from samconfig.toml
```

~3-5 minutes. Creates: DynamoDB, Lambda, Step Functions, API Gateway,
Cognito, S3, CloudFront.

SAM manages the artifacts bucket automatically — no manual S3 setup needed.

## 4. Deploy UI

```bash
cd ../ui
npm ci
npm run build
# Pass the stack name — must match samconfig.toml. (Omit it and deploy.sh falls
# back to a `polyris-dev` default, which breaks if you renamed the stack.)
./deploy.sh "$STACK_NAME" "$AWS_REGION" ./out
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
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
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
polyris-deploy
```

---

## Updating Polyris

> New terminal? Re-set `STACK_NAME` / `AWS_REGION` (from step 2) first.

**Infrastructure only:**
```bash
git pull
cd sam && sam build && sam deploy   # stack/region/params from samconfig.toml
```

**UI only:**
```bash
git pull
cd ui && npm ci && npm run build && ./deploy.sh "$STACK_NAME" "$AWS_REGION" ./out
```

**Both:**
```bash
git pull
cd sam && sam build && sam deploy   # stack/region/params from samconfig.toml
cd ../ui && npm ci && npm run build && ./deploy.sh "$STACK_NAME" "$AWS_REGION" ./out
```
