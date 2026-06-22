---
name: add-aws-service
description: Use when integrating a new AWS service into the SLSFlow stack beyond the ones already wired (Step Functions, Lambda, DynamoDB, EventBridge, SNS, SQS, S3, Glue, Athena, ECS, EMR, Batch, SageMaker, Bedrock, HTTP) — e.g. Kinesis, Redshift, a new compute target or data source. SLSFlow is a DSL→ASL compiler, so a first-class service is **primarily a library change** — a new `TaskTypeLiteral`, a `@task.<svc>` decorator (`slsflow/task.py`), and a codegen branch (`slsflow/generators.py`) — and only then SAM/IAM, cost, an ADR, and tests (ASL snapshots). Covers the SFN-first principle, the first-class-task vs inside-a-Lambda decision, and the full test surface. Trigger for "add/integrate <service>", "use <AWS service>", "new task type", or "new data source/sink".
---

# Integrating a new AWS service

SLSFlow compiles a Python DSL → Amazon States Language → Step Functions. So
"adding a service" is usually **a library change first** (a new task type the DSL
emits), then infra (SAM/IAM). It is also deliberately small and cheap
(~$31/month) — every service is standing cost + operational surface. Read the
cost and SFN-direction ADRs in `docs/reference/DESIGN_DECISIONS.md` first.

## Step 1 — Fit + pick the integration shape

Orchestration is **Step-Functions-first** (the async push-model, Phase 3, is
shelved — poor ROI, hurts debuggability). Two shapes, and the shape decides
whether you touch the library:

- **First-class SFN task** — `@task.<service>(...)` compiles to a native SFN
  service integration (`arn:aws:states:::<service>:<action>[.sync]`). This is the
  dominant existing pattern (glue, ecs, athena, sns, sqs, s3, dynamodb,
  eventbridge, bedrock, http). **Requires the library work in Step 2.**
- **Inside a Lambda** — the user's `@task.lambda_` / python function calls the
  service via boto3. **No library change** — only an IAM grant on the Lambda role
  (Step 3), plus a SAM resource if SLSFlow owns it. Skip Step 2.

Prefer serverless + on-demand + Express SFN over always-on infra; a
provisioned/clustered mode must be justified against the cost discipline. If the
service implies a fundamentally different orchestration model, stop and write the
ADR first (Step 6) — that is an architecture decision, not a wiring task.

## Step 2 — The library: new task type + codegen (first-class shape)

Mirror an existing service end-to-end — `glue` is the cleanest reference. Touch
points, in order:

1. **`slsflow/constants.py`** — add the value to the `TaskTypeLiteral` literal.
   (Task types are Python-only — they are **not** part of the enum-sync codegen,
   so no `make sync-constants` for this.)
2. **`slsflow/task.py`** —
   - add the service's config fields to the `Task` dataclass (mirror
     `glue_arguments`, `emr_step`, `batch_parameters`);
   - add a `@task.<service>(...)` classmethod to `TaskDecorator` (mirror `glue`
     ~L710 / `ecs` ~L765) — **the decorator signature is where required params are
     enforced**, so this is the real "validation";
   - add the new decorator to the "base `@task` is not allowed" error list.
3. **`slsflow/generators.py`** — the codegen, in **two** dispatch sites (keep them
   in sync):
   - write `_gen_<service>_state(step)` returning
     `{"Type":"Task","Resource":"arn:aws:states:::<service>:<action>[.sync]","Arguments":{…}}`
     (mirror `_gen_glue_state` ~L587), and register it in the state-generator
     **dispatch dict** (~L684);
   - add an `elif task.task_type == '<service>':` branch to the `task_config`
     builder (~L801) that carries the service config into DAG metadata;
   - add the type to `WRAPPER_STEP_TYPES` / `TRACKED_STEP_TYPES` (~L83/86) if it
     should get the started/failed wrapper and appear in DAG visualization.
   > **Deferred-refactor note:** the dispatch is split across the dict and the
   > `if/elif` on purpose-for-now. The `generators.py` registry refactor (so paid
   > emitters self-register without editing the free compiler) is deferred until
   > the **first paid** AWS service — its own stage + ADR. Until then, edit both
   > sites together.
4. **`slsflow/adapters/<service>.py`** — **only if it is a data source** that
   feeds the asset model (schema / DDL / partition inference), like
   `adapters/glue.py`. A pure compute target needs no adapter.

## Step 3 — SAM template + IAM

In `sam/template.yaml`:

1. Grant **least-privilege** IAM for the integration: the specific `<service>:…`
   actions on the **SFN execution role** (first-class task) or the **Lambda role**
   (inside-a-Lambda). Follow the existing role policies; do not widen a broad
   statement.
2. Add the resource (`AWS::SQS::Queue`, `AWS::SNS::Topic`, …) only if SLSFlow owns
   it, with sane defaults (encryption, retention, DLQ).
3. Pass ARNs via `!Ref` / `!GetAtt` as env vars or SFN parameters — never
   hard-coded.

Keep `sam build` working without `--use-container`: pure-Python deps only
(ADR #65). No native-wheel libraries in `console_api/requirements.txt`.

## Step 4 — Stateful resource safety

If the service stores state you can't lose (a new table, bucket, queue):
`DeletionPolicy: Retain` + `UpdateReplacePolicy: Retain`, and for DynamoDB
`PointInTimeRecoverySpecification`.

## Step 5 — Cost check

State the monthly delta before merging (requests × price + any always-on baseline
+ storage). If it materially moves ~$31/month, justify it in the ADR. On-demand /
pay-per-use shapes are preferred.

## Step 6 — Record the decision (ADR)

Add an ADR to `docs/reference/DESIGN_DECISIONS.md` (next number after the current
ceiling). Capture: what the service is for, why it vs alternatives, the cost
delta, and the orchestration shape (how it fits SFN-first).

## Step 7 — Surfaces that follow

- **Backend** route(s) to expose its data/status → `add-backend-route`
  (tier it: read = free, ops = Team, governance = Enterprise).
- **UI** to view it → `add-ui-feature` (same tier decision).

## Step 8 — Tests

- **ASL snapshot** (`tests/sdk/test_asl_snapshots_steps.py`) — the primary codegen
  test: add a `_build_…` DAG builder and a `test_snapshot_step_*` so the emitted
  `arn:aws:states:::<service>:…` state is pinned. Mirror the glue/ecs/athena
  builders already there.
- **Decorator / Task** (`tests/sdk/`, e.g. `test_schema.py`) — `@task.<service>(…)`
  produces the right `Task` and rejects missing required params.
- **Template drift** (`tests/sdk/test_sfn_template_drift.py`) stays green.
- **Adapter** (if added) — a `tests/sdk/test_adapters_<service>.py` mirroring
  `test_adapters_glue.py`.
- **Integration** (`tests/integration/`) for the real AWS shape; `pytest-mock`
  (ADR #26) at the boundary for unit.

Run the SDK/codegen suite directly while iterating:
`pip install -e . && pytest tests/sdk/ -v`.

## Step 9 — Verify

`make check` (lint + sync-constants + check-versions + smoke-pipelines + tests)
plus `cfn-lint` on the template. Confirm the SFN definition still validates and
the Express/Standard split is intact.
