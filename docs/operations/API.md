# polyris REST API Reference

## Base URL

```
https://{api-gateway-id}.execute-api.{region}.amazonaws.com
```

Or via CloudFront:
```
https://{cloudfront-domain}/api
```

All endpoints use query parameters for resource identification (not path params):
```
GET /api/pipeline-status?name=my-pipeline    # Correct
GET /api/pipeline/my-pipeline/status          # Wrong
```

## Authentication

When auth enforcement is on (`AUTH_ENABLED=true`), every request except
`/api/health*` and `/api/metrics` requires a bearer credential — either a
Cognito access token (browser) or a polyris Personal Access Token (scripts/CI):

```
Authorization: Bearer plrs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Generate and manage tokens via the Console (avatar → API Tokens) or the
`/api/tokens` endpoints. See [api-tokens.md](../features/api-tokens.md) for the
full how-to. The `http` examples below omit the header for brevity — add it to
every call.

Tokens are **scoped** (`read` ⊂ `write` ⊂ `admin`, ADR #66): a request whose
token scope is below what the route needs returns **403** (vs **401** for a
missing/invalid token). `GET` needs `read`, mutations need `write`, and
deletes / token management need `admin`.

---

## API Tokens (PAT)

Personal Access Tokens for scripts/CI (ADR #65). Full how-to:
[api-tokens.md](../features/api-tokens.md).

### Create token

```http
POST /api/tokens
{ "name": "ci-pipeline", "scope": "write", "expires_in_days": 90 }
// scope (read|write|admin) optional, default "read"; expires_in_days optional
```

Response (`201`) — the `token` field is returned **only here**, once:
```json
{ "token_id": "tok_ab12cd34", "name": "ci-pipeline", "scope": "write",
  "token": "plrs_…", "created_at": "…", "expires_at": "…", "revoked": false }
```

### List tokens

```http
GET /api/tokens
```
Returns `{ "tokens": [ { "token_id", "name", "created_at", "last_used_at",
"expires_at", "revoked" } ] }` — the secret hash is never returned.

### Revoke token

```http
DELETE /api/tokens?id=tok_ab12cd34
```
`200` on success, `404` if the id is unknown.

---

## Pipelines

### List Pipelines

```http
GET /api/pipelines?stats=true&date=2026-02-19
```

Response (with `stats=true`):
```json
{
  "pipelines": [
    {
      "name": "acme-daily",
      "arn": "arn:aws:states:...",
      "description": "Daily pipeline",
      "group": "acme",
      "schedule": "cron(0 10 ? * MON *)",
      "status": "failed",
      "paused": false,
      "sla": 85,
      "progress": 67,
      "today_stats": { "success": 2, "failed": 1, "running": 0, "waiting": 0, "skipped": 0, "total": 3 },
      "recent_runs": [
        { "date": "2026-02-19", "exec": "a1b2c3d4", "status": "running" },
        { "date": "2026-02-18", "exec": "e5f6g7h8", "status": "failed" },
        { "date": "2026-02-17", "exec": "i9j0k1l2", "status": "success" }
      ]
    }
  ]
}
```

Fields `schedule`, `recent_runs`, `sla`, `progress`, `today_stats` are only present when `stats=true`.

### Get Pipeline Status

```http
GET /api/pipeline-status?name={pipeline_name}
```

### Get Pipeline Executions

```http
GET /api/pipeline-executions?name={pipeline_name}
```

### Get Pipeline DAG

```http
GET /api/pipeline-dag?name={pipeline_name}&pipeline_execution={execution_name}
```

Returns DAG structure with lookup priority:
1. **Snapshot** — per-execution snapshot from `tokens_table` (if `pipeline_execution` provided)
2. **Registry** — current DAG from `pipeline_registry`
3. **Inferred** — reconstructed from task execution data

Response includes `dag_source` field: `'snapshot'` | `'registry'` | `'inferred'`

### Get Pipeline Metrics

```http
GET /api/pipeline-metrics?name={pipeline_name}
```

### Get Pipeline Logs

```http
GET /api/pipeline-logs?name={pipeline_name}
```

### Run Pipeline

```http
POST /api/pipeline-run?name={pipeline_name}
```

Body (optional): `{"variables": {"custom_var": "value"}}`

### Restart Pipeline

```http
POST /api/pipeline-restart?name={pipeline_name}
```

### Pause / Unpause Pipeline

```http
POST /api/pipeline-pause?name={pipeline_name}
```

Toggles pause state. Running tasks complete; new tasks wait (12h timeout).

### Register Pipeline

```http
POST /api/pipeline-register
```

Body: `{"pipeline_name": "...", "sfn_arn": "...", "dag": {...}}`

### Backfill (Unified, v0.78+)

> **Team edition.** Backfill is a Team-tier capability (ADR #99/#104). These
> `/api/backfill*` endpoints are served by the Team build; the open-source
> Console API does not register them.

Per **ADR #51**, six legacy code paths (pipeline-backfill, asset-backfill,
force-trigger, manual run, task-level run, matrix cell click) are
collapsed into a single endpoint:

```http
POST /api/backfill
```

Body:
```json
{
  "target": {"type": "asset", "name": "daily-etl/processed"},
  "partitions": {"start": "2026-01-01", "end": "2026-01-07"},
  "tasks": ["task_a"],
  "downstream": "auto",
  "upstream": "smart",
  "options": {
    "force": false,
    "skip_completed": true,
    "incremental": false,
    "max_parallel": 5,
    "variables": {"custom_key": "value"}
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target.type` | string | Yes | One of `pipeline`, `asset` |
| `target.name` | string | Yes | Pipeline or asset name |
| `partitions.start` / `partitions.end` | string | Range mode | Inclusive date range; format depends on granularity |
| `partitions.keys` | array | Keys mode | Explicit list (mutually exclusive with start/end) |
| `tasks` | array | No | Subset of tasks to run from the resolved pipeline |
| `downstream` | string | Asset only | Downstream cascade: `auto` (default) / `all` / `none`. (`cascade` is accepted as a deprecated alias and echoed back with a `deprecated_field` warning — ADR #91.) |
| `upstream` | string | Asset only | Upstream lineage build (ADR #92): `off` (default — producer only) / `smart` (build missing same-pipeline ancestors) / `force` (rebuild full lineage). |
| `options.force` | bool | No | Bypass safety checks |
| `options.skip_completed` | bool | No | Skip partitions that already completed (default `true`) |
| `options.incremental` | bool | No | Stop on first failure |
| `options.max_parallel` | int | No | Map concurrency 1–10 (default 5) |
| `options.variables` | object | No | Extra variables for child tasks |
| `options.allow_concurrent` | bool | No | Allow overlapping with running executions |

Query string: `?preview=true` returns the resolved plan — partition counts,
reused/skipped counts, upstream-lineage scope, and warnings — without starting
the bulk-backfill SFN. (There is no cost estimate; it was removed in v0.78.2,
ADR #62.)

Granularity is inferred from the resolved pipeline's cron schedule (ADR
#52); ambiguous crons default to `daily` and surface a warning.

Response (success, 202):
```json
{
  "backfill_id": "bf-a1b2c3d4",
  "target_pipeline": "daily-etl",
  "granularity_inferred": "daily",
  "partition_count_requested": 7,
  "partition_count_skipped_completed": 0,
  "partition_count_to_run": 7,
  "task_subset": ["task_a"],
  "downstream": null,
  "upstream": "smart",
  "upstream_lineage": {"tasks_to_run": 3, "partitions": 7},
  "warnings": [],
  "ui_url": "/backfills/bf-a1b2c3d4"
}
```

> **Note on `skip_completed`:** In v0.78, the API response always shows
> `partition_count_skipped_completed: 0` initially. The bulk-backfill
> SFN's per-iteration `Check_If_Done` Choice state queries DDB for
> each partition immediately before launching its child execution —
> that is the **real gate** and runs against live state at execution
> time. Setting `options.skip_completed=true` still works: already-
> complete partitions are skipped at the SFN level. Only the initial
> count in the API response stays conservative (the UI polls and
> updates the displayed completed-count as SFN flips state).

Error codes: `invalid_target`, `invalid_target_type`, `target_not_found`,
`no_producer`, `multi_producer_asset`, `producer_pipeline_missing`,
`unreachable_target_type`, `invalid_partitions`, `invalid_partition_format`,
`invalid_partition_keys`, `partition_keys_not_failed`, `range_too_large`
(>1000 partitions), `invalid_tasks`, `invalid_options`,
`invalid_downstream`, `invalid_downstream_for_pipeline_target` (the legacy
`invalid_cascade*` codes were renamed in v0.83 — ADR #91), `invalid_upstream`,
`invalid_upstream_for_pipeline_target`, `upstream_cycle` (asset graph has a
dependency cycle), `child_name_too_long`, `nothing_to_run` (after
skip_completed), `concurrent_backfill_active` (409 — active backfill running
for the same pipeline; pass `options.allow_concurrent=true` to override),
`throttled` (503 — retry), `misconfigured` (500), `sfn_start_failed`,
`internal_error`. The canonical, gated list lives in
`polyris/constants.py` as `BACKFILL_ERROR_CODES` (ADR #94).

#### Scale boundaries (v0.78)

| Limit | Value | Why |
|---|---|---|
| `partition_count` per backfill | **1000** | Bulk-backfill Inline Map history-event budget: ~20 events × 1000 = 20k events, under AWS 25k hard ceiling with headroom |
| `max_parallel` (Map MaxConcurrency) | **1..10** | AWS `StartExecution` burst limit 200/s; 10 concurrent × ~45ms iteration ≈ 220/s peak — under burst with shared-account headroom |
| `preview` partition scan | **<=100 partitions** | API Gateway 29s timeout; above this, `skip_completed` pre-flight is bypassed and SFN runs full set |
| Backfill record TTL in DDB | **30 days** | Matches execution retention |

**Out of scope for v0.78.** Backfills >1000 partitions must be chunked
client-side or via CLI (split start/end into 1000-day windows). The
underlying SFN uses **Inline Map** (one parent execution, parent owns
all iteration history). Migrating to Step Functions **Distributed Map**
would lift the partition ceiling to ~10k by giving each iteration its
own child execution — deferred until measured need (no user has
asked for >1000 partitions in one shot).

### List Backfills

```http
GET /api/backfills?status={active|pending|running|completed|failed|partial|canceled}&limit=50
```

Returns recent backfill summaries. Without `status` filter, returns all
recent regardless of status. With `status=active`, returns only `pending`
and `running`.

### Get Backfill Detail

```http
GET /api/backfills/by-id?id={backfill_id}
```

Returns the full backfill record with `partition_keys`, `children`
(child executions linked via `backfill_id` GSI), parsed `options`, and
`target_seed`. Returns 404 if not found.

### Cancel Backfill (Cooperative)

```http
POST /api/backfills/cancel?id={backfill_id}
```

Marks status as `canceled` in DynamoDB. The bulk-backfill SFN's Map
iterator checks status at each iteration and short-circuits remaining
partitions. In-flight child executions are **not** interrupted (per ADR
#54).

Returns 409 (`already_terminal` or `status_race`) if backfill is already
in a terminal state or status changed during the call.

### Retry Failed Partitions

```http
POST /api/backfills/retry-failed?id={backfill_id}
```

Creates a **new** Backfill containing only the failed partitions of the
parent, linked via `parent_backfill_id`. Only valid when parent status is
`failed` or `partial`. Returns the new `backfill_id` in the same shape
as `POST /api/backfill`.

---

## Tasks

### List All Tasks

```http
GET /api/tasks?pipeline={name}&status={status}&date={YYYY-MM-DD}
```

All query params optional. Returns tasks matching filters.

### Get/Update Task Config

```http
GET /api/task-config?name={execution_name}
PUT /api/task-config?name={execution_name}
```

### Get Task Events

```http
GET /api/task-events?name={execution_name}
```

### Task Actions

```http
POST /api/task-skip?name={execution_name}       # Skip waiting/failed task
POST /api/task-fail?name={execution_name}       # Mark as failed
POST /api/task-success?name={execution_name}    # Mark as successful
POST /api/task-stop?name={execution_name}       # Force-stop running task
POST /api/task-restart?name={execution_name}    # Restart terminal task (409 if not terminal)
POST /api/task-retry?name={execution_name}      # Retry with same params
```

`task-fail` and `task-success` accept optional body: `{"reason": "..."}`

---

## Executions

### List All Runs

```http
GET /api/runs?pipeline={name}&status={status}&date={YYYY-MM-DD}&limit=50
```

Unified Run/Activity feed (ADR #95). Returns a mixed, `started_at`-descending
list of pipeline executions **and** Backfills, discriminated by `kind`:

```jsonc
{
  "runs": [
    {
      "kind": "execution",
      "pipeline_name": "acme-daily",
      "pipeline_execution": "acme-daily-2026-05-31-ab12cd34",
      "pipeline_execution_short": "ab12cd34",
      "status": "succeeded",          // running | succeeded | failed | aborted
      "started_at": "...", "finished_at": "...",
      "date": "2026-05-31",
      "duration_ms": 42000,
      "backfill_id": null              // set if this execution belongs to a backfill
    },
    {
      "kind": "backfill",
      "id": "bf-1a2b3c4d",
      "backfill_id": "bf-1a2b3c4d",
      "pipeline_name": "acme-daily",   // = target_pipeline
      "status": "partial",             // pending | running | completed | failed | partial | canceled (ADR #56)
      "started_at": "...", "finished_at": "...",
      "started_by": "alice",
      "total_partitions": 10, "completed_partitions": 6,
      "failed_partitions": 4, "skipped_partitions": 0,
      "downstream": "auto", "granularity": "daily",
      "date": null,                    // backfills span a range, not one logical date
      "duration_ms": 123000
    }
  ],
  "count": 2,
  "filters": { "pipeline": "", "status": "", "date": "" }
}
```

Filter semantics (ADR #95):
- `status` — literal match against whichever vocabulary a row uses (`kind`
  tells you which); no normalization. `running`/`failed` match both kinds.
- `pipeline` — executions match `pipeline_name`; backfills match
  `target_pipeline` (a cross-pipeline backfill surfaces under its target only).
- `date` — executions match their logical date; a backfill matches when the
  date is within its `partition_keys` range (daily-oriented).
- Default window is the last 14 days for executions; backfills come from
  `list_recent` and may include one older than 14 days.

Expand a row on demand via `GET /api/execution-children?id=` (execution) or
`GET /api/backfills/by-id?id=` (backfill); children are not embedded.

### Execution Actions

```http
POST /api/execution-stop?id={execution_arn}
POST /api/execution-pause?id={pipeline_execution}
POST /api/execution-resume?id={pipeline_execution}
POST /api/execution-extend?id={pipeline_execution}   # +12h pause timeout
```

### Execution Info

```http
GET /api/execution-children?id={execution_name}
GET /api/execution-parent?id={execution_name}
```

---

## Assets

### List & Lineage

```http
GET /api/assets
GET /api/assets/lineage
GET /api/assets/queued?date={YYYY-MM-DD}
GET /api/assets/recent-events?limit=50&date={YYYY-MM-DD}
```

### Asset Events & Actions

```http
GET    /api/asset-events?name={asset_name}&limit=20
POST   /api/asset-trigger?name={asset_name}           # Body: {"date": "..."}
DELETE /api/asset-delete?name={asset_name}
```

### Queue Management

```http
POST /api/assets/skip-in-queue      # Body: {"dag_id", "asset_name", "date"}
POST /api/assets/clear-queue        # Body: {"dag_id", "date"}
POST /api/assets/delete-orphaned    # Body: {"dry_run": false}
```

Note: Asset backfills go through the unified `POST /api/backfill` with
`target.type='asset'` (see Backfill section above). The legacy
`POST /api/assets/backfill` endpoint was removed in v0.78 (ADR #51).

### Consecutive Progress (v68+)

```http
GET /api/assets/consecutive-progress?pipeline={name}&execution={exec_name}&date={YYYY-MM-DD}
```

Returns progress for tasks with `wait_for` consecutive asset dependencies. Shows which dates have events and which are missing.

```json
{
  "assets": [
    {
      "name": "daily_metrics",
      "consecutive_days": 7,
      "found_dates": ["2025-01-10", "2025-01-11", "2025-01-12"],
      "missing_dates": ["2025-01-13", "2025-01-14", "2025-01-15", "2025-01-16"],
      "ready": false
    }
  ]
}
```

---

## Notifications

```http
GET /api/notifications?limit=20&hours=4
```

---

## Slack Actions

Called by Slack interactive message buttons:

```http
GET /api/action/skip?execution_name={name}
GET /api/action/fail?execution_name={name}
GET /api/action/success?execution_name={name}
GET /api/action/restart?execution_name={name}
```

---

## Health

```http
GET /api/health          # Full check (DDB, SFN, circuit breaker)
GET /api/health/simple   # Liveness check
GET /api/metrics         # System metrics
```

---

## Error Responses

```json
{"error": "ERROR_CODE", "message": "Human readable message", "request_id": "abc123"}
```

| Code | Meaning |
|------|---------|
| 200 | Success |
| 202 | Accepted (async, e.g. orchestrated backfill) |
| 400 | Bad request / validation error |
| 404 | Resource not found |
| 409 | Conflict (race condition, e.g. restart non-terminal task) |
| 500 | Internal error |
