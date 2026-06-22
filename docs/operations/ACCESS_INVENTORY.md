# Access Inventory

The complete list of access, credentials, and accounts required to **operate and
deploy** SLSFlow. Pair this with [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) (the
day-to-day operator runbook) and [`DEPLOYMENT_DRILL.md`](./DEPLOYMENT_DRILL.md)
(the hands-on deploy walkthrough).

> **Purpose.** No single point of failure on access. Every item below should have
> **at least two** people who hold or can recover it. Fill the `<owner>` /
> `<backup>` columns and keep this file current — it is the first thing a new
> co-maintainer reads.

## 1. AWS

| What | Value | Owner | Backup |
|---|---|---|---|
| Account ID | `<fill>` (do **not** commit real IDs to public code — see pre-release gaps) | | |
| Primary region | `us-east-1` | | |
| Console / SSO login | `<fill>` | | |
| Deploy CLI profile | `slsflow-dev` (in `~/.aws/config`) | | |
| Live stack name | `slsflow-dev` (CloudFormation / SAM) | | |
| Deploy IAM principal | `<role/user used by sam deploy>` — needs CFN + the service perms in `template.yaml` | | |

**Recovery:** account root credentials + MFA device location: `<fill>`. Billing
alerts route to: `<fill>`.

## 2. Secrets & their locations

| Secret | Where it lives | Rotation |
|---|---|---|
| SAM deploy config | `sam/samconfig.toml` | **Rotate + scrub from git history before any public release** (pre-release blocker) |
| UI runtime env | `ui/.env.local` (`API_GATEWAY_URL`, `NEXT_PUBLIC_AUTH_ENABLED`) — local only, never committed | n/a |
| Cognito app client secret | AWS Cognito console / SAM outputs | on staff change |
| `ANTHROPIC_API_KEY` (CI review) | GitHub repo secret | on staff change |
| Any third-party tokens (Slack webhook, etc.) | `<fill>` | `<fill>` |

> **Rule:** secrets never enter the repo. If one is committed, rotate it *and*
> scrub history (`git filter-repo`) — rotation alone is insufficient once pushed.

## 3. Source control

| What | Value |
|---|---|
| Repository | `github.com/Maksym-hub/slsflow` |
| SSH remote | `git@github-maksym-hub:Maksym-hub/slsflow.git` (alias → `~/.ssh/id_ed25519_maksym_hub`; plain `git@github.com` picks the wrong identity) |
| Admin / org owners | `<fill>` |
| Branch protection / required checks | `ci.yml` (blocking); `claude-code-review.yml` (non-blocking) |
| Repo secrets holders | `<fill>` |

## 4. Runtime resources (in the live stack)

| Resource | Identifier | Notes |
|---|---|---|
| Step Functions | Standard + Express state machines | per `template.yaml` |
| Lambda | `console_api`, `evaluate_deps`, `check_assets`, `notify_asset_subscribers`, `query_subscriptions` | |
| DynamoDB tables | `<list/ARNs>` | enable `DeletionPolicy: Retain` + PITR (pre-release gap) |
| EventBridge bus/rules | `<fill>` | |
| S3 buckets | UI bucket + `<others>` | CloudFront OAC |
| CloudFront distribution | `<dist id>` | UI delivery; invalidate on UI deploy |
| Cognito user pool | `<pool id>` | console auth; admin needed to manage users |
| API Gateway | `<api id>` | `API_GATEWAY_URL` |

## 5. Access roster (who can do what)

| Capability | Who | Notes |
|---|---|---|
| Deploy to `slsflow-dev` | `<fill>` | sole holder today = bus-factor risk; add a backup |
| AWS console (admin) | `<fill>` | |
| GitHub admin | `<fill>` | |
| Rotate secrets | `<fill>` | |
| Domain / DNS (if any) | `<fill>` | |

**Action item:** SLSFlow currently has a **single operator**. Before public
release, give Myroslav (co-maintainer) deploy access and walk the
[`DEPLOYMENT_DRILL`](./DEPLOYMENT_DRILL.md) together so deploy/recovery is not a
one-person dependency.
