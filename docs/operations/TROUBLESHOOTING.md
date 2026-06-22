# Troubleshooting Guide

Common issues and solutions for slsflow operations.

> **API auth (`AUTH_ENABLED=true`):** every API call below except `/api/health*`
> and `/api/metrics` needs `-H "Authorization: Bearer <token>"` (a PAT `slsf_…`
> or a Cognito token). The `curl` examples omit it for brevity. A **401
> Unauthorized** means a missing/expired/revoked token — regenerate or revoke
> via the Console (avatar → API Tokens). See `docs/features/api-tokens.md`.

---

## Pipeline Issues

> **Note:** Table names follow the pattern `{namespace}-{stage}-slsflow-{table}`.
> Replace `${NAMESPACE}` and `${STAGE}` with your actual values (e.g., `mycompany-dev`).


### Pipeline doesn't start on schedule

**Symptoms:** Pipeline should run daily but doesn't trigger.

**Check:**
1. EventBridge rule exists and is enabled:
   ```bash
   aws events list-rules --name-prefix "slsflow"
   aws events describe-rule --name "your-pipeline-schedule"
   ```

2. Rule target has correct permissions:
   ```bash
   aws events list-targets-by-rule --rule "your-pipeline-schedule"
   ```

3. Pipeline is registered:
   ```bash
   aws dynamodb get-item \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-pipeline-registry \
     --key '{"pipeline_name": {"S": "your-pipeline"}}'
   ```

**Fix:** Re-deploy pipeline with `slsflow-deploy` or manually enable rule in AWS Console.

---

### Pipeline stuck in "running" state

**Symptoms:** Pipeline shows running but no tasks are active.

**Check:**
1. Step Functions execution status:
   ```bash
   aws stepfunctions list-executions \
     --state-machine-arn "arn:aws:states:..." \
     --status-filter RUNNING
   ```

2. Check for orphaned executions in DynamoDB.

**Fix:** Stop the stuck execution via Console UI or API:
```bash
curl -X POST https://api.example.com/api/execution-stop?id={arn}
```

---

## Task Issues

### Task stuck in "waiting"

**Symptoms:** Task shows "waiting" but dependencies are complete.

**Check:**
1. **Dependencies tab** in task modal — are all upstreams success/skipped?

2. **Subscription exists** in DynamoDB:
   ```bash
   aws dynamodb scan \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-dep-subscriptions \
     --filter-expression "contains(subscriber_name, :task)" \
     --expression-attribute-values '{":task": {"S": "your-task"}}'
   ```

3. **notify_dependents_helper** executed:
   - Open upstream task's wrapper execution in Step Functions Console
   - Check if "NotifyDependents" state ran successfully

4. **Wait token is valid** — tokens expire after 1 year, but executions timeout sooner.

**Fix:** 
- If subscription missing: restart the pipeline for this date
- If notify didn't run: check upstream task's failure handler
- Emergency: manually send task token:
  ```bash
  aws stepfunctions send-task-success \
    --task-token "aqc..." \
    --task-output '{"status": "success"}'
  ```

---

### Task stuck in "waiting_delay"

**Symptoms:** Task shows countdown but never proceeds.

**Check:**
1. `wait_delay_until_ms` timestamp — when should it end?
2. Server time sync — any clock skew?
3. Wrapper SFN execution — is Wait state active?

**Fix:** Usually resolves itself. If not, restart the task.

---

### Task fails immediately

**Symptoms:** Task goes to "failed" within seconds.

**Check:**
1. **Task ARN** is correct:
   ```bash
   aws stepfunctions describe-state-machine --state-machine-arn "your-task-arn"
   ```

2. **IAM permissions** — wrapper role can invoke task:
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn "wrapper-role-arn" \
     --action-names "states:StartExecution" \
     --resource-arns "task-arn"
   ```

3. **Task logs** — check CloudWatch for the actual error.

**Fix:** Fix IAM permissions or task ARN, then restart.

---

### Task shows "upstream_failed"

**Symptoms:** Task blocked due to upstream failure.

**This is expected behavior** when `trigger_rule="all_success"` (default) and an upstream failed.

**Options:**
1. Fix and restart the failed upstream
2. Skip the failed upstream (task will re-evaluate)
3. Change `trigger_rule` to `none_failed` or `all_done`

---

## Asset Issues

### Pipeline not in UI after deploy

**Symptoms:** Deployed with `slsflow-deploy` but pipeline doesn't appear in sidebar.

**Check:**
1. `slsflow-deploy` output shows `PipelineRegistration` created:
   ```
   +  slsflow:PipelineRegistration  my-pipeline-reg  created (2s)
   ```

2. Pipeline exists in registry:
   ```bash
   aws dynamodb get-item \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-pipeline-registry \
     --key '{"pipeline_name": {"S": "my-pipeline"}}'
   ```

**Fix:**
- If PipelineRegistration failed: `slsflow-deploy` again (retry)
- If registration missing: `slsflow-register --name my-pipeline`
- Legacy environments without Dynamic Provider: wait 1-5 min for EventBridge auto-registration

---

### Asset-triggered pipeline doesn't run

**Symptoms:** Asset updated but consumer pipeline didn't start.

**Check:**
1. **Asset subscription exists**:
   ```bash
   aws dynamodb query \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-asset-subscriptions \
     --key-condition-expression "asset_name = :asset" \
     --expression-attribute-values '{":asset": {"S": "your-asset"}}'
   ```

2. **Asset event was emitted**:
   ```bash
   aws dynamodb query \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-asset-events \
     --key-condition-expression "asset_name = :asset" \
     --expression-attribute-values '{":asset": {"S": "your-asset"}}' \
     --scan-index-forward false \
     --limit 5
   ```

3. **For AND triggers** — check queued events:
   ```bash
   aws dynamodb query \
     --table-name ${NAMESPACE}-${STAGE}-slsflow-queued-asset-events \
     --key-condition-expression "dag_id_date = :key" \
     --expression-attribute-values '{":key": {"S": "your-dag#2026-01-15"}}'
   ```

**Fix:**
- If subscription missing: re-deploy consumer pipeline
- If event missing: manually trigger asset or re-run producer
- If AND queue incomplete: trigger missing assets or skip in queue

---

### Asset shows stale in UI

**Symptoms:** Asset materialized recently but UI shows old timestamp.

**Check:** Asset events table has the latest event.

**Fix:** Asset events are eventually consistent. Wait 30s or refresh. If persists, check `notify_asset_consumers` SFN execution history and `asset-events` DynamoDB table.

---

## Deployment Issues

### "alerts parameter is required"

Every DAG needs alerts configuration:

```python
# Option 1: Slack alerts (recommended)
with DAG("pipeline", alerts={"slack": "#your-channel"}) as dag:
    ...

# Option 2: PagerDuty
with DAG("pipeline", alerts={"pagerduty": "routing-key"}) as dag:
    ...

# Option 3: Explicitly disable (not recommended for production)
with DAG("test-pipeline", alerts=None) as dag:
    ...
```

---

### "SSM parameter not found" error

**Symptoms:** Pipeline deployment fails reading SSM parameters.

**Check:**
1. Shared infrastructure is deployed:
   ```bash
   cd sam
   # (set Stage=dev in samconfig.toml)
   aws cloudformation describe-stacks --stack-name slsflow-dev --query "Stacks[0].Outputs"
   ```

2. Run `sam deploy` first to write SSM parameters:
   ```toml
   # config.py ENVIRONMENTS
   bucket = "your-actual-state-bucket"
   role_arn = "arn:aws:iam::ACCOUNT:role/read-state"
   ```

3. IAM role can read state bucket.

---


**Symptoms:** `slsflow-deploy` fails with "stack already exists".

**Fix:**
```bash
# List stacks
aws cloudformation list-stacks

# Select existing stack


# Or remove and recreate
```

---

## Console UI Issues

### UI shows "Loading..." forever

**Check:**
1. API URL is correct in `public/config.js` or `.env.local`
2. CORS is configured on API Gateway
3. Browser console for errors (F12 → Console)

**Fix:** Run `./ui/deploy.sh` to regenerate `config.js`. For local dev, check `ui/public/config.js` or `ui/.env.local`.

---

### UI not updating automatically

**Symptoms:** Need to manually refresh to see changes.

**Check:** Polling is enabled (default 30s, 3s when active tasks).

**Fix:** Check browser console for polling errors. May indicate API issues.

---

## Lambda Issues

### evaluate_deps timeout

**Symptoms:** Dependency evaluation takes too long.

**Check:**
1. Number of dependencies — large fan-in can be slow
2. DynamoDB throttling — check CloudWatch metrics

**Fix:** 
- Increase Lambda timeout (default 30s)
- Enable DynamoDB auto-scaling
- Reduce dependency fan-in if possible

---

### console_api 502 errors

**Symptoms:** API returns 502 Bad Gateway.

**Check:**
1. Lambda execution logs in CloudWatch
2. Lambda memory/timeout settings
3. API Gateway integration timeout (29s max)

**Fix:** Increase Lambda memory (faster cold starts) or optimize slow routes.

---

## Emergency Procedures

### Stop runaway execution

```bash
# Via Console UI: Stop button

# Via API:
curl -X POST https://api.example.com/api/execution-stop?id={arn}

# Via AWS CLI:
aws stepfunctions stop-execution --execution-arn "arn:aws:states:..."
```

---

### Manually complete stuck task

**Use when:** Task is stuck but you verified work is done (checked logs, S3, etc.)

```bash
# Via Console UI: Task modal → "Mark Success" button

# Via API:
curl -X POST https://api.example.com/api/task-success?name={execution_name} \
  -H "Content-Type: application/json" \
  -d '{"reason": "Manually verified completion"}'
```

---

### Force restart pipeline for date

```bash
# Via Console UI: Pipeline → Run button → select date

# Via API:
curl -X POST https://api.example.com/api/pipeline-run?name={name} \
  -H "Content-Type: application/json" \
  -d '{"variables": {"current_date": "2026-01-15"}}'
```

---

### Clear all paused pipelines

```bash
# List paused
aws dynamodb scan \
  --table-name ${NAMESPACE}-${STAGE}-slsflow-pipeline-registry \
  --filter-expression "paused = :true" \
  --expression-attribute-values '{":true": {"BOOL": true}}'

# Resume via API
curl -X POST https://api.example.com/api/execution-resume?id={id}
```

---

## Common Setup Errors

### `ModuleNotFoundError: No module named 'slsflow'`


```yaml
runtime:
  name: python
  options:
    virtualenv: ../../.venv
```

Then install: `pip install -e .` from the project root.

### `KeyError: 'dev'` or stage not found

Your `config.py` is missing the stage. Add it to `ENVIRONMENTS`:

```python
ENVIRONMENTS = {
    "dev": {
        "namespace": "myorg",
        "stage": "dev",
        "region": "us-east-1",
    },
}
```

### `ValueError: DAG 'X': 'alerts' parameter is required`

Every DAG must have an `alerts` parameter. Use `alerts=None` to explicitly disable:

```python
with DAG("my-pipeline", schedule="@daily", alerts={"slack": "#alerts"}) as dag: ...
with DAG("my-pipeline", schedule="@daily", alerts=None) as dag: ...  # No alerts
```

---

## Getting Help

- **Logs:** CloudWatch Logs → `/aws/lambda/slsflow-*`
- **Executions:** Step Functions Console → State Machines
- **Data:** DynamoDB Console → Tables starting with `slsflow-`
- **Slack:** #slsflow-support
