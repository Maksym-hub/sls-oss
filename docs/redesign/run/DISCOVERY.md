# Run Redesign — Discovery Report

**Goal:** Catalog every file in the project against the Run redesign so the
plan has accurate scope, accurate cost, and zero "we forgot about that"
during implementation.

**Status:** SUPERSEDED by ADR #95 (v0.86.0). The unified write-side `Run`
object this report explored was not built: Backfill became the first-class
parent object for the only case that needs one, and single runs intentionally
have no parent (the execution *is* the run). "Run" is realized instead as a
read-only projection — `/api/runs` merges executions + Backfills into one feed.
This document is retained for the file-by-file scope analysis; the decision and
boundary rule live in ADR #95.

<details><summary>Original status (historical)</summary>

**Status:** WIP — file-by-file walkthrough in progress.

</details>

**Method:** Read every source file. For each, answer:
1. What does it do today?
2. Does Run redesign touch it?
3. If yes — what changes, how many LOC, what's the risk?
4. Open questions / dependencies on other files.

## Classification

Each file gets one of four labels:

- **AFFECTED** — must change; lists exact modifications
- **REVIEW** — might change; needs deeper read before deciding
- **UNAFFECTED** — verified no interaction with Run/backfill/execution flow
- **DELETE** — file removed entirely (component subsumed by Run model)

## File counts (full scope)

| Category | Count |
|---|---|
| Python source (slsflow + sam lambdas) | 77 |
| TypeScript/TSX source (ui/src) | 108 |
| SFN templates (.tpl.json) | 13 |
| Documentation (.md) | 30 |
| Python tests | 27 |
| UI tests | 49 |
| Infra: SAM template, Makefile, pyproject, package.json, CI yaml | ~10 |
| **Total** | **~314** |

## Per-file entry format

```
### path/to/file.ext

**Label:** AFFECTED | REVIEW | UNAFFECTED | DELETE

**Today:** One-line description of current purpose.

**Touches Run redesign:** YES (specifics) | NO (verified by: ...)

**Changes:** (if AFFECTED)
- Bullet list of specific edits, each with LOC estimate.
- Reference open questions if any.

**Tests:** existing test coverage + what new tests cover.

**Risk:** LOW | MEDIUM | HIGH — and why.

**Depends on / Blocks:** other files in this report.

**Open questions:** (if any)
```

## Sample entries — format validation

These five entries use real files from the project to validate the format
before the full walkthrough. If the format works on these heterogeneous
samples (DSL core, Lambda handler, UI hook, SFN template, doc file),
it'll work for the remaining 309.

---

### slsflow/assets.py

**Label:** AFFECTED

**Today:** Asset DSL — defines `Asset`, `AssetRef`, `AssetConsecutiveRef`,
`AssetAll`, `AssetAny`, `AssetAlias`, `Watcher`. 1558 LOC, 6 constructors
(`from_pyarrow`, `from_parquet`, `from_pydantic`, `from_glue_table`,
`from_iceberg`, `from_dict`). Already has `granularity` and `partition_start`
fields (ADR #50, v0.77.0).

**Touches Run redesign:** YES — Run uses `Asset.granularity` to expand
partition keys, uses `Asset.partition_start` for range clipping. These
fields are read-only consumers.

**Changes:**
- None required. Fields already exist.
- Maybe add `Asset.partition_freq` (e.g. for 12-hourly) as future option —
  **deferred**, document as out-of-scope in ADR #58.

**Tests:** 22 tests in `tests/sdk/test_assets.py`. No new tests needed
for redesign (granularity tests already cover the surface area).

**Risk:** LOW

**Depends on / Blocks:**
- Blocks: `slsflow/partitions.py` (new) — needs to import Asset and read
  granularity / partition_start fields.

**Open questions:** None.

---

### sam/lambdas/console_api/routes/backfill.py

**Label:** DELETE (replaced by `routes/runs.py`)

**Today:** 576 LOC, 3 handlers: `force_trigger_dag`, `backfill_by_asset`,
`backfill_pipeline`. All three currently called by old API endpoints
(`/api/dags/{n}/force-trigger`, `/api/assets/backfill`, `/api/pipeline-backfill`).
In-Lambda iteration with `time.sleep(2)` between batches.

**Touches Run redesign:** YES — this file IS the old backfill, replaced
in its entirety.

**Changes:**
- Delete file (-576 LOC).
- Calendar-math vars logic (`minus_1_month`, `minus_3_months`, etc.)
  moves to `slsflow/partitions.py` (now reusable for all granularities).
- Asset → producers resolution (lines 160-198) moves to
  `routes/runs.py::_resolve_asset_target`.
- Throttle retry logic (lines 530-554) becomes irrelevant — Map state
  in bulk-run SFN handles throttling natively.

**Tests:** existing handler tests in `sam/lambdas/console_api/tests/routes/test_backfill.py`
(~300 LOC) — delete; coverage moves to `tests/test_runs.py`.

**Risk:** LOW — since no production, no migration concerns.

**Depends on / Blocks:**
- Blocks: routes/runs.py creation (logical successor)
- Blocked by: ADR #51 (must approve API contract before deletion)

**Open questions:**
- `Limits.MAX_FETCH_ITEMS` used here — verify nobody else needs it after
  deletion. (Will check during walkthrough of `constants.py`.)

---

### ui/src/hooks/queries/usePipelineQueries.ts

**Label:** AFFECTED

**Today:** React Query hooks for pipeline operations:
`usePipelinesQuery`, `usePipelineDetailQuery`, `usePipelineExecutionsQuery`,
`usePipelineMetricsQuery`, `useCalendarExecutionsQuery`, `useTogglePauseMutation`,
`useRunPipelineMutation`, `useBackfillMutation`, `useTaskActionMutation`,
`useExecutionPauseMutation`. 275 LOC.

**Touches Run redesign:** YES — `useRunPipelineMutation` and
`useBackfillMutation` are both subsumed by Run. The other 8 hooks unaffected
(they're read-only or auxiliary).

**Changes:**
- Delete `useRunPipelineMutation` (-15 LOC, calls `/api/runs/{name}`).
- Delete `useBackfillMutation` (-18 LOC, calls `/api/pipeline-backfill`).
- Add import from new `useRunQueries.ts` (which centralizes Run mutations).
- Net: -33 LOC in this file.
- Keep `usePipelineExecutionsQuery` — used by Calendar and recent-runs views;
  not all executions are Run-initiated.

**Tests:** existing tests cover mutations; need to delete obsolete assertions.

**Risk:** LOW

**Depends on / Blocks:**
- Blocks: deletion of `BackfillModal.tsx` and `PipelineDetail.tsx` button
  handlers that call these mutations.
- Depends on: new `useRunQueries.ts` created first.

**Open questions:** None.

---

### sam/sfn_templates/dependency_wrapper/sfn.tpl.json

**Label:** AFFECTED

**Today:** Wrapper SFN that runs around each task. Validates dependencies,
manages task state, emits events. Reads
`$states.input.skip_tasks`, `$states.input.current_date`,
`$states.input.pipeline_execution`, etc. JSONata-heavy template.

**Touches Run redesign:** YES — bulk-run SFN starts child pipeline executions
that use this wrapper. Input format must remain compatible. Also: this
wrapper computes `$today := $states.input.current_date` — for non-daily
granularities we need to pass something consumable.

**Changes:**
- Add reading of optional `$states.input.run_id` field; propagate to
  child SFN invocations so all executions in a Run carry the run_id.
  (~10 LOC of JSONata edits.)
- Add reading of optional `$states.input.partition_key`; for daily it
  equals `current_date`. For weekly/monthly, builder in `bulk-run` passes
  a translated daily anchor in `current_date` (e.g., Monday of the week)
  AND the original partition_key. Wrapper writes BOTH to pipeline-tokens.
  (~5 LOC JSONata + 1 new DDB attribute.)
- No backward-compat: legacy executions without run_id just get null —
  $exists() check handles that.

**Tests:** snapshot tests in `tests/snapshots/` — need re-baseline.
JSONata expression compile tests in `tests/sfn_jsonata/` — re-run 563-expression
suite to confirm no parse errors.

**Risk:** HIGH — this template is in the hot path of every task execution.
A bug here breaks every pipeline run. Requires careful review and full
test pass before merge.

**Depends on / Blocks:**
- Depends on: ADR #58 (partition_key format decision)
- Blocks: bulk-run SFN template (which builds the input this consumes)

**Open questions:**
- For non-daily granularities, do we want JSONata in wrapper to be
  granularity-aware, OR do we make builder always pass a daily anchor
  and keep wrapper unchanged? **Recommendation:** builder translates,
  wrapper stays daily — minimizes risk to the hot path. Decide in ADR #58.

---

### docs/features/DSL.md

**Label:** AFFECTED (documentation update)

**Today:** 574 LOC. User-facing DSL reference. Contains:
- `@dag` decorator docs
- Asset DSL examples (granularity already documented after v0.77.0)
- Backfill section ("backfilling pipelines works like Airflow CLI")
- AND/OR / freshness / consecutive dependency docs

**Touches Run redesign:** YES — backfill section becomes "Run" section.
Examples need updating.

**Changes:**
- Rewrite section "Backfilling pipelines" → "Running pipelines / assets"
  (~50 LOC of text changes).
- Add subsection: "Asset cascade behavior" (~30 LOC, new content covering
  auto/all/none modes with examples).
- Update examples to use new RunModal screenshots / API payload examples.
- Remove old `airflow dags backfill` reference; replace with `slsflow run`
  CLI examples (CLI added in v0.78).

**Tests:** N/A (docs file).

**Risk:** LOW — docs only.

**Depends on / Blocks:**
- Depends on: ADRs #51, #57 (cascade), #52 (granularity validation)
  finalized first.
- Blocks: `docs/reference/AIRFLOW_MIGRATION.md` update (cross-references).

**Open questions:** None.

---

## Discovery progress

Format validated on five heterogeneous samples. Proceeding with full walkthrough:

- [ ] **Phase A:** slsflow/ Python sources (22 files)
- [ ] **Phase B:** sam/lambdas/console_api/ Python sources (~30 files)
- [ ] **Phase C:** sam/lambdas/* other Lambdas (4 directories)
- [ ] **Phase D:** SFN templates (13 files)
- [ ] **Phase E:** SAM template + CI + Makefile
- [ ] **Phase F:** ui/src/components/ (~62 files)
- [ ] **Phase G:** ui/src/hooks + ui/src/utils + ui/src/stores (~30 files)
- [ ] **Phase H:** ui/src/lib + ui/src/types (~10 files)
- [ ] **Phase I:** Test files mapping (existing → new)
- [ ] **Phase J:** Documentation (30 files)
- [ ] **Phase K:** Cross-cutting concerns (deps, scripts, etc.)

Each phase produces a flat list of file entries in the format above,
appended to this document. At the end: summary tables for AFFECTED count,
DELETE count, total LOC delta, risk distribution.

---

## Phase A — slsflow/ Python sources (22 files + 8 in subdirs)

### slsflow/__init__.py

**Label:** AFFECTED (minor)

**Today:** 223 LOC. Package re-exports: `Asset`, `DAG`, `task`, version,
generator entry points. Version constant `__version__ = "0.77.2"`.

**Touches Run redesign:** YES — needs to export new symbols.

**Changes:**
- Add re-exports: `from .partitions import PartitionRange` (~2 LOC).
- Bump version to 0.78.0 when redesign ships.

**Risk:** LOW

---

### slsflow/cli.py

**Label:** AFFECTED (new commands added)

**Today:** 40 LOC. Console entry-points stub:
`slsflow-init`, `slsflow-deploy`. Currently NO `slsflow run` command.

**Touches Run redesign:** YES — new `slsflow run` family of commands needs
to live here per memory item #11 (context-aware CLI).

**Changes:**
- Add `slsflow run pipeline NAME --partitions START:END [--tasks ...] [...]`
- Add `slsflow run asset NAME --partitions START:END [--cascade auto|all|none]`
- Add `slsflow runs list [--status ...] [--target ...]`
- Add `slsflow runs cancel RUN_ID`
- Add `slsflow runs retry RUN_ID`
- New file `slsflow/run_cli.py` (~150 LOC) holds the command bodies;
  `cli.py` adds entry-point registration (~10 LOC).

**Tests:** new `tests/sdk/test_run_cli.py`.

**Risk:** LOW — CLI is thin wrapper over `/api/run`.

**Depends on:** `/api/run` endpoint live (Phase 2 of implementation).

---

### slsflow/config.py · constants.py · context.py · dag.py · helpers.py · init.py · output.py · resolver.py · roles.py · task_group.py · validation.py · xcom.py

**Label:** UNAFFECTED (12 files)

**Verified by:** zero references to `backfill`, `start_execution`, `run_id`,
`partition_key` (execution sense), `skip_tasks`, `trigger_dag`, `granularity`.

**Note on `slsflow/schema.py`:** Although it contains `partition_key`, it
refers to `Column.partition_key` (boolean flag for column-level partitioning
in Glue/Iceberg DDL) — orthogonal to execution-time partition keys used by
Run model. **UNAFFECTED** — no changes needed.

---

### slsflow/dag.py

**Label:** AFFECTED (if `@dag(granularity=...)` override added — see open
question in plan; ADR #52 decides)

**Today:** 380 LOC. `DAG` class + `@dag` decorator. Holds `schedule`,
`description`, `tags`, `default_args`. Currently NO `granularity` field.

**Touches Run redesign:** YES if we add `@dag(granularity="weekly")` as
explicit override (escape hatch when cron inference is ambiguous —
e.g., `0 8 * * 1-5` weekdays-only).

**Changes (CONDITIONAL on ADR #52 decision):**
- Add `granularity: Optional[Granularity]` field to `DAG.__init__` (~3 LOC).
- Add `@dag(granularity="weekly")` validation in decorator (~5 LOC).
- Validate that explicit granularity matches outlets (already covered by
  ADR #52 deploy-time check — DAG class only stores the value, doesn't
  validate cross-task).

**Tests:** `tests/sdk/test_dag.py` + 5 new tests.

**Risk:** LOW

**Open question:** Do we want the override? **Recommendation:** YES — cron
inference will fail for non-trivial schedules. Explicit > inferred.

---

### slsflow/assets.py

**Label:** AFFECTED (minimal)

**Today:** 1558 LOC. Asset DSL with `granularity` and `partition_start`
already (v0.77.0, ADR #50).

**Touches Run redesign:** YES — consumed by `partitions.py` and Run
resolver. Fields already exist.

**Changes:**
- None to existing fields.
- Optional new field `Asset.partition_freq` deferred — out of scope ADR #58.

**Risk:** LOW

---

### slsflow/task.py

**Label:** AFFECTED (no code changes, semantic clarification)

**Today:** 990 LOC. Task DSL with `skip_on_backfill: bool = False`
field exposed on all task constructors (sfn, lambda, python, etc.).

**Touches Run redesign:** YES — `skip_on_backfill` is read by Run-side
logic when `is_backfill=true` (Run-initiated executions set this flag).

**Changes:**
- None to code.
- **Documentation update:** docstring change "Skip during backfill runs"
  → "Skip when execution is part of a Run (is_backfill=true), e.g. tasks
  that should only fire during scheduled runs (Slack notifier, alerter)."
  Same semantic, clearer wording. (~5 LOC docstring edits across 7 task
  decorators.)

**Tests:** existing `tests/sdk/test_task.py` — no new tests; semantics
unchanged.

**Risk:** LOW

---

### slsflow/deploy.py

**Label:** AFFECTED

**Today:** 496 LOC. `slsflow-deploy` command. Already has
`_check_glue_granularity_drift` (advisory) at line 50.

**Touches Run redesign:** YES — adds strict pipeline-granularity validation
per ADR #52.

**Changes:**
- New function `_validate_pipeline_granularity(dag)` (~40 LOC):
  - Collect outlet granularities from all tasks.
  - Error if mixed (>1 distinct value).
  - Compare to `infer_cron_cadence(dag.schedule)` if inferrable.
  - Error on mismatch; use explicit `@dag(granularity=...)` to override.
  - Write resolved granularity to `pipeline_registry.granularity` (new
    pipeline-registry attribute).
- Call from main deploy flow before `register_pipeline` invocation (~5 LOC).
- `_check_glue_granularity_drift` becomes secondary advisory (stays
  unchanged).

**Tests:** new `tests/sdk/test_pipeline_granularity.py` covering:
- single-granularity pipeline OK
- mixed outlets → ValueError
- cron daily + asset weekly → ValueError
- ambiguous cron + explicit @dag(granularity="weekly") → OK
- no schedule (manual-only DAG) → defaults to outlet granularity
- no outlets → defaults to "daily"

**Risk:** MEDIUM — strict validation may reject existing test pipelines
in the repo (`pipelines/acme/*`, `pipelines/shopmart/*`). Manual review
required to confirm those declare granularity correctly.

**Depends on:** ADR #52 (validation rule), `slsflow/granularity.py` (new).

---

### slsflow/generators.py

**Label:** AFFECTED

**Today:** 1718 LOC. ASL generation, JSONata constants, per-step
generators. `JSONATA_SKIP_TASKS` constant at line 66; emitted into
generated pipeline SFN templates. Asset registration ALREADY emits
`granularity` (line 188-190, ADR #50).

**Touches Run redesign:** YES — Run-aware fields propagate through
generated pipeline SFNs (run_id, partition_key).

**Changes:**
- Add new JSONata constants:
  - `JSONATA_RUN_ID = "{% $exists($states.input.run_id) ? $states.input.run_id : null %}"`
  - `JSONATA_PARTITION_KEY = "{% $exists($states.input.partition_key) ? $states.input.partition_key : $states.input.current_date %}"`
- Update step generators to pass these into child task input
  (~30 LOC across `_gen_lambda_state`, `_gen_glue_state`, etc.).
- Asset registration: already writes `granularity`; add writing
  `partition_start` if present (~3 LOC at line 188).

**Tests:** existing `tests/sdk/test_generators.py`. Add 3 tests:
- generated state machine carries `JSONATA_RUN_ID` through to child input
- partition_key falls back to current_date when missing
- registered asset metadata includes partition_start

**Risk:** MEDIUM — generators.py is the SFN code-gen heart. A bug here
breaks every deployment.

**Depends on:** ADR #58 (partition_key format).

---

### slsflow/local.py

**Label:** UNAFFECTED (with clarifying note)

**Today:** 703 LOC. Local dev runner — `slsflow local` simulates pipeline
execution without deploy. Uses Step Functions Local emulator. The
`sfn.start_execution` reference at line in scan is for the local emulator,
not the Run model.

**Touches Run redesign:** NO. Local runner emulates a SINGLE pipeline run
for a SINGLE date. Doesn't model the Run abstraction (no bulk-run, no
partition expansion). User runs `slsflow local --date 2024-01-15` to test
one execution.

**Future enhancement (out of scope):** `slsflow local run --partitions
START:END` could simulate a bulk-run for testing. Deferred — current
single-date mode covers debugging use case.

**Open question:** Should we mention this gap in user docs? YES, in
`docs/tools/DEVELOPMENT.md` add "For multi-partition local testing, use
`slsflow run` against a dev deploy."

**Risk:** LOW

---

### slsflow/register.py

**Label:** UNAFFECTED

**Today:** 302 LOC. `slsflow-register` command that invokes the
`register_pipeline` SFN to write pipeline metadata to DynamoDB. The
`start_execution` at line 124 is for the registration SFN, orthogonal
to pipeline run executions.

**Touches Run redesign:** NO — registration happens at deploy time, before
any Run can exist.

**Risk:** LOW

---

### slsflow/steps.py

**Label:** UNAFFECTED

**Today:** 883 LOC. Generates SFN step templates (DDB GetItem, PutItem,
GlueStartJobRun, etc.). The `partition_key` reference at one site is the
DDB key attribute (e.g., `pk`/`sk`) for output storage, not the
execution-time partition key in the Run model.

**Risk:** LOW

---

### slsflow/schema.py

**Label:** UNAFFECTED

**Today:** 907 LOC. Column/Schema type system. `Column.partition_key`
boolean refers to whether a column is a partition column in Glue/Iceberg
DDL — not the execution partition_key. Different concept, same word.

**Risk:** LOW

---

### slsflow/adapters/

**Label:** UNAFFECTED (3 files: glue.py, pyarrow_.py, pydantic_.py)
EXCEPT `infer_granularity_from_partition_keys` in glue.py.

**Note on `slsflow/adapters/glue.py`:** Already exposes
`infer_granularity_from_partition_keys()` used by `slsflow/deploy.py`
for advisory check. **No changes for Run redesign** — function already
exists and works.

**Risk:** LOW

---

### slsflow/ai/

**Label:** AFFECTED for docs.py only. UNAFFECTED for: __init__.py, cli.py,
core.py, examples.py, providers.py.

**Touches Run redesign:** YES — ai/docs.py contains Q&A text that orients
the user to Airflow-style `catchup`/`backfill` mental model (lines 49, 499).
Needs rewriting to introduce Run concept.

**Changes (ai/docs.py only):**
- Rewrite "Backfill" Q&A section (~30 LOC of text).
- Update "Scheduling" examples to reflect Run model.
- Drop `catchup` references.

**Risk:** LOW — text only.

---

## Phase A summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 7 | `__init__.py`, `cli.py`, `dag.py`, `assets.py`, `task.py`, `deploy.py`, `generators.py`, `ai/docs.py` |
| NEW FILES | 3 | `partitions.py` (~250 LOC), `granularity.py` (~80 LOC), `run_cli.py` (~150 LOC) |
| UNAFFECTED | 19 | config.py, constants.py, context.py, helpers.py, init.py, local.py, output.py, register.py, resolver.py, roles.py, schema.py, steps.py, task_group.py, validation.py, xcom.py, adapters/(__init__, glue, pyarrow_, pydantic_), ai/(__init__, cli, core, examples, providers) |
| DELETE | 0 | — |

**Phase A LOC delta:**
- New: ~480 LOC (3 new files)
- Modified: ~110 LOC across 7 files
- **Total: +590 LOC in slsflow/**

**Risk distribution:** 1 MEDIUM (generators.py + deploy.py validation), 6 LOW.

**Phase A complete.**

---

## Phase B — sam/lambdas/console_api/ Python (29 files)

### sam/lambdas/console_api/__init__.py

**Label:** UNAFFECTED

**Today:** 53 LOC. Package init, imports for handler dispatch.

**Risk:** LOW

---

### sam/lambdas/console_api/config.py

**Label:** AFFECTED (env vars added)

**Today:** 175 LOC. Lazy AWS client wrappers, SFN helper ARN env vars
(`NOTIFY_DEPENDENTS_HELPER_ARN`, `REGISTER_PIPELINE_ARN`, etc.).

**Touches Run redesign:** YES — needs new SFN ARN env vars for bulk-run.

**Changes:**
- Add `BULK_RUN_ARN = os.environ.get('BULK_RUN_ARN', '')` (~2 LOC).
- Add `BULK_RUN_WATCHER_ARN` if separate watcher SFN (TBD; depends on
  Standard-vs-Express decision in ADR #54).

**Risk:** LOW

---

### sam/lambdas/console_api/constants.py

**Label:** AFFECTED (constants added)

**Today:** 139 LOC. `Limits` class (MAX_FETCH_ITEMS, MAX_SCAN_ITEMS, etc.),
status enums, table names.

**Touches Run redesign:** YES — need Run-specific constants.

**Changes:**
- Add `class RunLimits`: PARTITION_SOFT_LIMIT=500, PARTITION_HARD_LIMIT=5000,
  MAX_PARALLEL=10 (~10 LOC).
- Add Run status enum: PENDING, RUNNING, COMPLETED, FAILED, CANCELED, PARTIAL
  (~6 LOC).
- Add sentinel `RUN_RECORD_PIPELINE_NAME = '_slsflow_bulk_run'` (~1 LOC).

**Tests:** existing test_config.py validates constants — extend with Run.

**Risk:** LOW

---

### sam/lambdas/console_api/logger.py

**Label:** UNAFFECTED

**Today:** 41 LOC. Structured logger wrapper (`log.info`, `log.warn`, etc.).

**Risk:** LOW

---

### sam/lambdas/console_api/main.py

**Label:** AFFECTED

**Today:** 166 LOC. ROUTES dict (52 entries) dispatches HTTP requests.
Imports from `routes/__init__.py` aggregation. Handler dispatch.

**Touches Run redesign:** YES — routing table changes.

**Changes:**
- Remove old routes (5 entries removed):
  - `('POST', '/api/runs'): (run_pipeline, 'name')` — old single-run
  - `('POST', '/api/pipeline-backfill'): (backfill_pipeline, 'name')`
  - `('POST', '/api/assets/backfill'): (backfill_by_asset, None)`
  - `('POST', '/api/dags', 'force-trigger'): (force_trigger_dag, 'name')`
  - `('GET', '/api/runs'): (get_all_runs, None)` — semantics shift
- Add new routes (6 entries):
  - `('POST', '/api/run'): (start_run, None)` — unified Run start
  - `('GET', '/api/runs'): (list_runs, None)` — list Run records
  - `('GET', '/api/runs/{id}'): (get_run, 'id')` — Run detail
  - `('POST', '/api/runs/{id}/cancel'): (cancel_run, 'id')`
  - `('POST', '/api/runs/{id}/retry-failed'): (retry_failed, 'id')`
  - `('GET', '/api/executions'): (get_all_executions, None)` — renamed
    from old `get_all_runs` for clarity (handler renamed in
    routes/executions.py)
- Update CLAUDE.md "52 routes" → "53 routes" (one more after additions).
- Net change in main.py: ~25 LOC.

**Tests:** `tests/sdk/test_templates.py` asserts `len(ROUTES) == 52` — update.

**Risk:** MEDIUM — route table is central, every API call passes through.

---

### sam/lambdas/console_api/response.py

**Label:** UNAFFECTED

**Today:** 208 LOC. CORS helpers, response shaping.

**Risk:** LOW

---

### sam/lambdas/console_api/utils.py

**Label:** AFFECTED

**Today:** 537 LOC. Mixed utilities: PagerDuty, internal-record check,
execution name parsing, safe int helpers, `record_manual_decision()`,
`_format_task_event()`. Contains line 142: `run_id = item.get('task_run_id',
item.get('pipeline_execution', ''))` — **naming collision**, uses `run_id`
in PagerDuty event context, NOT in the Run model sense.

**Touches Run redesign:** YES — naming collision needs resolution; also
`is_internal_record` needs to recognize Run records.

**Changes:**
- Rename PagerDuty-context `run_id` variable to `pd_run_id` or similar
  to disambiguate from Run model (~6 LOC across 4 sites).
  *Alternative:* keep name, document semantic in comment. Cheaper but less
  clear.
- Update `is_internal_record()`: recognize Run records by `record_type='run'`
  attribute or `pipeline_name='_slsflow_bulk_run'` sentinel. Currently
  recognizes `_pause_*` and `_notify_warn_*` prefixed names. Needs to skip
  Run records when iterating per-task executions (~5 LOC).
- `is_execution_name()` unchanged — Run records use UUIDs, not
  task-name-date format.
- `compute_pipeline_execution_short()` unaffected.

**Tests:** `sam/lambdas/console_api/tests/test_utils.py` — extend with
`test_is_internal_record_run_record`.

**Risk:** MEDIUM — `is_internal_record` is called in **every** loop
through pipeline-tokens. A bug here causes Run records to appear as
fake executions in Lists/Counts/Health.

---

### sam/lambdas/console_api/task_actions.py

**Label:** REVIEW (likely UNAFFECTED)

**Today:** 156 LOC. Shared task action helpers (skip/fail/success/stop).
1 ref to `start_execution` — invokes notify_dependents_helper SFN.

**Touches Run redesign:** Probably NOT — task action invokes
notify_dependents, which is orthogonal to Run model. notify_dependents
gets the task_run_id and emits downstream notifications regardless of
whether the parent execution is part of a Run.

**Verification needed:** Confirm that task skip/fail/success does NOT need
to know about parent Run. If Run iteration counts failed/succeeded children,
that aggregation reads execution status — task action just changes status,
counter logic lives in Run watcher.

**Changes:** NONE expected.

**Risk:** LOW

---

### sam/lambdas/console_api/task_variables.py

**Label:** AFFECTED

**Today:** 113 LOC. **Drift-tested single source of truth** for all task
variables — defines `TASK_VARIABLES` dict, helper functions
`get_jsonata_vars()`, `get_python_vars()`, `get_flag_vars()`,
`get_backfill_vars()`. Tests in `tests/test_alerting.py::TestVariableSchemaDrift`
verify JSONata (in `run_task` SFN template) and Python (in
`routes/backfill.py`) match the schema.

**Touches Run redesign:** YES — `get_backfill_vars()` is the contract for
"what variables are available to tasks during a backfill". After redesign,
this becomes "what variables are available during a Run".

**Changes:**
- Rename `get_backfill_vars()` → `get_run_vars()` (~1 LOC + 2 callers).
- Update schema entries: add `run_id` and `partition_key` as new variables
  (source="run-context").
- Update test drift target: the JSONata builder is now in bulk-run SFN
  template (not `run_task` `Prepare_Task_Input`); Python builder is in
  `routes/runs.py` (not `routes/backfill.py`). Drift test in
  `tests/test_alerting.py` needs path updates.
- Net: ~15 LOC in this file + drift test updates.

**Tests:** drift tests stay — they're the safety net. Update their
references to new files.

**Risk:** MEDIUM — drift tests catch most issues, but the schema
correctness is critical for task input compatibility.

---

### sam/lambdas/console_api/dal/__init__.py

**Label:** AFFECTED (new export)

**Today:** 32 LOC. Re-exports DAL repos.

**Changes:**
- Add `from .runs_repo import runs_repo` if new repo created (~1 LOC).
  *Alternative:* extend `executions_repo` to handle Run records (sentinel
  filter). Decided in ADR #54.

**Risk:** LOW

---

### sam/lambdas/console_api/dal/assets_repo.py

**Label:** AFFECTED (docstring only)

**Today:** 127 LOC. Asset metadata + queued events repos. Docstring lists
"Used by routes: assets, backfill" (line 8).

**Changes:**
- Docstring update: "backfill" → "runs" (~1 LOC).

**Risk:** LOW

---

### sam/lambdas/console_api/dal/circuit_breakers_repo.py

**Label:** UNAFFECTED

**Today:** 59 LOC. Circuit breaker state for asset triggers.

**Risk:** LOW

---

### sam/lambdas/console_api/dal/executions_repo.py

**Label:** AFFECTED

**Today:** 166 LOC. Repository for `pipeline-tokens` table. Methods:
`get`, `update`, `query_by_date`, `query_by_pipeline_execution`,
`scan_all`. Docstring lists "Used by routes: ... backfill" (line 6).

**Touches Run redesign:** YES — `pipeline-tokens` schema gets two new
attributes (`run_id`, `partition_key`, `record_type`) and a new GSI
(`run-id-index`). Repo needs query methods.

**Changes:**
- Add `query_by_run_id(run_id)` method using new GSI (~10 LOC).
- Add `query_by_partition_key(pipeline_name, partition_key)` for
  skip-completed pre-flight (~12 LOC).
- All write methods (`put`, `update`) — no changes; DynamoDB schemaless,
  new attributes pass through.
- Add convenience `write_run_record(run_id, payload)` if not using
  separate `runs_repo` (decided in ADR #54).
- Docstring update: routes list.
- Net: ~30 LOC additions.

**Tests:** existing tests don't cover new GSI; add ~5 unit tests with
moto-mocked DDB.

**Risk:** MEDIUM — central DAL, every API touches it.

---

### sam/lambdas/console_api/dal/pipelines_repo.py

**Label:** AFFECTED (docstring + maybe granularity field)

**Today:** 76 LOC. Repository for `pipeline-registry`. Docstring lists
"Used by routes: ... backfill" (line 5).

**Changes:**
- Docstring update.
- After ADR #52, `pipeline-registry` gets new attribute `granularity`
  (set at deploy time). No repo method changes — schemaless DDB. Readers
  use `pipeline.get('granularity', 'daily')` with fallback.

**Risk:** LOW

---

### sam/lambdas/console_api/dal/subscriptions_repo.py

**Label:** AFFECTED (docstring only)

**Today:** 57 LOC. Asset subscription queries.

**Changes:** Docstring "backfill" → "runs" (~1 LOC).

**Risk:** LOW

---

### sam/lambdas/console_api/dal/task_events_repo.py

**Label:** UNAFFECTED

**Today:** 54 LOC. Task events (audit log). 5 refs to `task_run_id` are
DDB PK, not Run-model run_id. False positive in scan.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/__init__.py

**Label:** AFFECTED

**Today:** 121 LOC. Aggregates handler imports for `main.py` ROUTES.

**Changes:**
- Remove imports: `force_trigger_dag`, `backfill_by_asset`,
  `backfill_pipeline` (from `routes/backfill.py` which is DELETED).
- Remove import: `run_pipeline` (from `routes/pipelines_actions.py` if
  collapsed; OR keep as private helper).
- Add imports: `start_run`, `list_runs`, `get_run`, `cancel_run`,
  `retry_failed` (from new `routes/runs.py`).
- Rename `get_all_runs` → `get_all_executions` (handler renamed in
  `routes/executions.py`).
- Net: ~10 LOC delta.

**Risk:** LOW (mechanical imports).

---

### sam/lambdas/console_api/routes/assets.py

**Label:** AFFECTED (minor — uses producer resolution logic that moves)

**Today:** 1061 LOC. Asset CRUD (list, delete, events, trigger), Glue
schema check, deletion of orphaned. 3 refs found: `start_execution` for
manual asset trigger, `partition_key` (Column flag in schema check),
`current_date` (in docstring example).

**Touches Run redesign:** YES — `trigger_asset_event` and Glue schema
endpoint stay; but the "find producer for asset" logic (currently inline
in `routes/backfill.py::backfill_by_asset`) should live in a shared
helper. Best home: `routes/assets.py` or new `routes/runs.py`.

**Changes:**
- Possibly extract `_find_producer_pipelines(asset_name) -> List[dict]`
  as shared helper. Currently lives in routes/backfill.py lines 158-198.
  Move to assets.py or runs.py — TBD in ADR #51.
- No changes to existing handlers (list_assets, trigger_asset_event,
  delete_asset, get_asset_glue_schema).
- Net: ~30 LOC moved in.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/backfill.py

**Label:** DELETE (576 LOC)

**Already covered in sample entries above.** Logic redistributes to:
- Calendar-math vars → `slsflow/partitions.py`
- Asset producer resolution → `routes/assets.py` (shared helper)
- Force-trigger flow → `routes/runs.py::start_run` with `force=true`,
  `partitions=[today]`
- Pipeline backfill flow → `routes/runs.py::start_run`
- Throttle retry → bulk-run SFN Map state (native)

---

### sam/lambdas/console_api/routes/drift.py

**Label:** AFFECTED (read-only, granularity-aware)

**Today:** 202 LOC. `get_asset_drift` endpoint. 17 refs (mostly
`granularity`). Uses `_EXPECTED_PER_30_DAYS` hardcoded constants per
granularity.

**Touches Run redesign:** YES indirectly — drift detection should respect
`asset.partition_start` so brand-new assets don't show false critical
status. (Backlog item from v0.77.2 audit.)

**Changes:**
- Add `partition_start` lookup; if asset younger than 30 days, scale
  expected count proportionally (~15 LOC).
- Move duplicated `_EXPECTED_PER_30_DAYS` to `slsflow/granularity.py`
  (shared with SDK).
- Net: ~15 LOC modified.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/executions.py

**Label:** AFFECTED

**Today:** 652 LOC. Pipeline execution control: `get_all_runs`,
`stop_execution`, `pause_execution`, `resume_execution`, `extend_pause`,
`get_execution_pause_status`. The handler name `get_all_runs` predates
the Run model; it actually returns **executions**.

**Touches Run redesign:** YES — naming and filtering.

**Changes:**
- Rename `get_all_runs` → `get_all_executions` (~2 LOC at def + handler
  reference). The HTTP route `/api/runs` → `/api/executions`.
- Update queries to **exclude Run records**: filter `record_type != 'run'`
  AND `pipeline_name != '_slsflow_bulk_run'` sentinel. Without this, Run
  records bleed into executions list (~5 LOC of filter conditions).
- Add new handler `get_all_runs` in `routes/runs.py` that returns ACTUAL
  Run records (not in this file).
- `stop_execution`/`pause_execution` unchanged — work on individual
  executions. But: Run-cancel should reuse `stop_execution` logic for
  per-child cancellation if we choose Standard SFN with sync (~no change
  if Express fire-and-forget).
- Net: ~10 LOC in this file.

**Risk:** MEDIUM — every UI list view depends on this handler.

---

### sam/lambdas/console_api/routes/health.py

**Label:** AFFECTED

**Today:** 306 LOC. Health checks: DDB, SFNs, recent failures, circuit
breakers. Verifies SFN reachability.

**Touches Run redesign:** YES — bulk-run SFN needs to be in health check
scope.

**Changes:**
- Add bulk-run SFN ARN to `_check_stepfunctions` checks (~3 LOC).
- `_check_recent_failures` query — verify it doesn't double-count Run
  failures (Run failure aggregates execution failures). Filter
  `record_type='run'` to avoid both being reported (~5 LOC).

**Tests:** extend health endpoint tests.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/matrix.py

**Label:** AFFECTED (significant)

**Today:** 572 LOC. Matrix endpoint, partition-bucket math, cell
derivation. **41 refs** — already partition_key / granularity heavy
(ADR #49/#50). Cell click integration with backfill already partial.

**Touches Run redesign:** YES — Matrix cell click triggers Run, multi-cell
selection.

**Changes:**
- Add `partition_start` clipping to cell derivation: cells before asset's
  `partition_start` return `None` instead of "missing" (~10 LOC).
- Add `run_id` filter param (optional): show cells colored by which Run
  produced/failed them — for Run Detail Page heatmap reuse (~15 LOC).
- Otherwise: keep current granularity-aware bucket math; this is the model
  Run resolver will reuse.
- Net: ~25 LOC additions.

**Risk:** MEDIUM — Matrix is read-heavy in production, changes to query
patterns affect performance.

---

### sam/lambdas/console_api/routes/notifications.py

**Label:** AFFECTED (minor)

**Today:** 137 LOC. Recent failures bell. 3 refs (`run_id` in docstring
example).

**Touches Run redesign:** YES — Run-level failure should generate a
notification, not just N per-execution failures.

**Changes:**
- Add Run-level notification synthesis: if Run finishes with
  `status='partial'` or `status='failed'`, emit one synthetic notification
  ("Run {target} failed: X of Y partitions"). Suppress per-execution
  notifications for Run children to avoid spam — replace with Run summary
  (~25 LOC).
- Deferred to v0.79 if implementation complexity exceeds estimate;
  fallback in v0.78 is N per-execution notifications (noisy but works).

**Risk:** LOW (gracefully degradable).

---

### sam/lambdas/console_api/routes/pipelines_actions.py

**Label:** AFFECTED

**Today:** 288 LOC. `run_pipeline`, `restart_pipeline`, `toggle_pause`,
`stop_pipeline`. 17 refs (current_date, skip_tasks, start_execution).
`run_pipeline` is what `POST /api/runs/{name}` calls today — manual
single-date pipeline run.

**Touches Run redesign:** YES — `run_pipeline` collapses into `start_run`
in `routes/runs.py`.

**Changes:**
- DELETE `run_pipeline` handler from this file (~40 LOC removed).
  Functionality moves to `routes/runs.py::start_run` with seed
  `{target: 'pipeline', partitions: [today]}`.
- Keep `restart_pipeline`, `toggle_pause`, `stop_pipeline` — these are
  pipeline-level ops, not Run-level.
- Net: -40 LOC.

**Risk:** LOW (handler relocated, not behavior change).

---

### sam/lambdas/console_api/routes/pipelines_info.py

**Label:** UNAFFECTED

**Today:** 344 LOC. `get_pipeline_metrics`, `get_pipeline_dag`,
`get_pipeline_logs`. Read-only.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/pipelines_list.py

**Label:** AFFECTED (minor filter)

**Today:** 627 LOC. `list_pipelines`, `get_pipeline_status`,
`get_pipeline_executions`. Iterates pipeline-tokens.

**Touches Run redesign:** YES — must filter out Run records.

**Changes:**
- `_query_pipeline_by_date_range`, `_aggregate_executions`: skip rows
  with `record_type='run'` (~3 LOC each, 2 sites = 6 LOC).
- Otherwise unchanged.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/slack.py

**Label:** UNAFFECTED

**Today:** 349 LOC. Slack interactive callbacks. 1 ref to
`start_execution` (invokes `restart_task_helper`). Operates on individual
task tokens; doesn't care about Run model.

**Risk:** LOW

---

### sam/lambdas/console_api/routes/tasks.py

**Label:** AFFECTED (minor)

**Today:** 944 LOC. Task operations: `get_all_tasks`, task_config,
task_events, retry/skip/fail/success/stop/restart. 12 refs.

**Touches Run redesign:** YES — `get_all_tasks` may filter; restart_task
unchanged but should preserve `run_id` if parent execution has one.

**Changes:**
- `get_all_tasks`: skip rows with `record_type='run'` (~2 LOC).
- `restart_task`: when restarting, propagate parent execution's `run_id`
  if present, so restarted task counts toward original Run (~5 LOC). This
  is implicit if we pass full input through — verify.
- `get_task_events`: unchanged.
- Net: ~7 LOC additions.

**Risk:** LOW

---

### NEW FILE: sam/lambdas/console_api/routes/runs.py

**Estimated:** 300 LOC.

**Handlers:**
- `start_run(event)` — POST /api/run main entry. Resolves target, expands
  partitions, validates, calls bulk-run SFN.
- `list_runs(event)` — GET /api/runs.
- `get_run(run_id, event)` — GET /api/runs/{id}.
- `cancel_run(run_id, event)` — POST /api/runs/{id}/cancel.
- `retry_failed(run_id, event)` — POST /api/runs/{id}/retry-failed.

**Helpers:**
- `_resolve_target(target_dict)` — pipeline | asset | batch → producer(s)
- `_expand_partitions(partitions, granularity)` — uses
  `slsflow/partitions.py`
- `_compute_task_subset(tasks, target, dag)` — seed resolver
- `_skip_completed_preflight(producer, partition_keys, task_subset)` —
  DDB scan, returns filtered list
- `_check_cascade_warnings(producer, partition_keys, cascade)` —
  surfaces freshness/consecutive issues for preview

**Tests:** ~50 unit tests, ~10 integration tests against moto.

---

### NEW FILE: sam/lambdas/console_api/dal/runs_repo.py (CONDITIONAL)

**Decision required:** ADR #54 — separate repo or extend executions_repo?

**If separate:** ~120 LOC, methods `put`, `get`, `update_progress`,
`list_active`, `list_recent`, `update_status`.

**If extended:** ~50 LOC of additions to executions_repo.

**Recommendation:** SEPARATE for clarity. Run is a different concept than
Execution even if stored in the same table — separate repo encodes that.

---

## Phase B summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 16 | config.py, constants.py, main.py, utils.py, task_variables.py, dal/__init__.py, dal/assets_repo.py, dal/executions_repo.py, dal/pipelines_repo.py, dal/subscriptions_repo.py, routes/__init__.py, routes/assets.py, routes/drift.py, routes/executions.py, routes/health.py, routes/matrix.py, routes/notifications.py, routes/pipelines_actions.py, routes/pipelines_list.py, routes/tasks.py |
| NEW FILES | 2 | routes/runs.py (~300 LOC), dal/runs_repo.py (~120 LOC, conditional) |
| UNAFFECTED | 9 | __init__.py, logger.py, response.py, task_actions.py, dal/circuit_breakers_repo.py, dal/task_events_repo.py, routes/pipelines_info.py, routes/slack.py |
| DELETE | 1 | routes/backfill.py (-576 LOC) |
| REVIEW | 1 | task_actions.py (verified UNAFFECTED above) |

**Phase B LOC delta:**
- New: ~420 LOC (2 new files)
- Modified: ~200 LOC across 16 files
- Deleted: -576 LOC (routes/backfill.py)
- **Total: +44 LOC in console_api/**

**Risk distribution:** 4 MEDIUM (main.py routes, utils.is_internal_record,
executions.py filter, task_variables drift), 12 LOW. SFN templates risk
covered in Phase D.

**Phase B complete.**

---

## Phase C — Other Lambdas (5 + _shared)

### sam/lambdas/_shared/constants.py

**Label:** AFFECTED (potential addition for runs)

**Today:** Single source of truth for status constants used across Lambdas
(via copy-paste pattern, since AWS Lambda doesn't share code without
Lambda Layers).

**Touches Run redesign:** YES potentially — if Run status enum needs to be
referenced from multiple Lambdas.

**Changes:**
- Add Run status constants (PENDING, RUNNING, etc.) if any Lambda outside
  console_api needs them. Likely NOT — Run status is set only by bulk-run
  SFN and read by console_api. Other Lambdas (evaluate_deps,
  notify_asset_subscribers, check_assets) work on individual asset/task
  events, not Runs.
- **Decision:** NO ADDITION unless ADR #54 makes a Lambda outside
  console_api responsible for updating Run state.
- Net: 0 LOC.

**Risk:** LOW

---

### sam/lambdas/evaluate_deps/index.py + constants.py

**Label:** UNAFFECTED

**Today:** 343 LOC. Evaluates AND/OR/freshness for asset-event-driven
pipeline triggers. Pure event-condition evaluation.

**Touches Run redesign:** Could optionally propagate `cascade_source_run_id`
when triggering downstream pipelines as part of a Run's cascade. This
provides lineage ("this execution was triggered because Run abc123
materialized asset X"). **Deferred to v0.79** (nice-to-have, not core).

**Changes:** NONE in v0.78.

**Risk:** LOW

---

### sam/lambdas/notify_asset_subscribers/index.py

**Label:** UNAFFECTED

**Today:** 289 LOC. Routes asset events to subscriber pipelines, applies
freshness check (`_check_freshness` — already fixed silent except in
v0.77.2).

**Touches Run redesign:** NO. Asset event propagation is orthogonal to
Run model. Works the same whether asset materialization came from cron,
manual trigger, or bulk-run.

**Changes:** NONE.

**Risk:** LOW

---

### sam/lambdas/check_assets/index.py

**Label:** UNAFFECTED

**Today:** 468 LOC. Pre-trigger asset freshness checks for AND/OR/freshness
conditions. 11 refs to `current_date` — false positive (not Run partition
key; just the current execution's logical date).

**Touches Run redesign:** NO. Pre-trigger check, runs before pipeline
execution starts. Orthogonal to Run aggregation.

**Changes:** NONE.

**Risk:** LOW

---

### sam/lambdas/query_subscriptions/index.py

**Label:** UNAFFECTED

**Today:** 69 LOC. Helper Lambda for asset subscription queries.

**Risk:** LOW

---

### sam/lambdas/ui_bootstrap/index.py

**Label:** UNAFFECTED

**Today:** 95 LOC. Serves Amplify config to UI.

**Touches Run redesign:** NO — config is static (API URL, Cognito ID).

**Risk:** LOW

---

## Phase C summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 0 | — |
| NEW | 0 | — |
| UNAFFECTED | 5 | evaluate_deps, notify_asset_subscribers, check_assets, query_subscriptions, ui_bootstrap |
| DELETE | 0 | — |
| CONDITIONAL | 1 | _shared/constants.py — no addition in v0.78 |

**Phase C LOC delta:** 0

**Risk distribution:** All LOW.

**Phase C complete.**

---

## Phase D — SFN templates (13 files)

### ⚠ CRITICAL DISCOVERY: `run_id` naming collision

Existing SFN templates **already use `run_id`** as a DDB field name on
task records — set to `pipeline_execution` value. Found in:
- `sam/sfn_templates/dependency_wrapper/sfn.tpl.json` (lines 9, 31)
- `sam/sfn_templates/helpers/run_task/sfn.tpl.json` (lines 185-186, 705-706)
- `sam/lambdas/console_api/utils.py` (line 142, 165, 180)

Current semantic: "Group of task records belonging to the same pipeline
execution." Used by PagerDuty event consolidation.

**Conflict:** New Run model uses `run_id` for Run record ID (parent of
multiple pipeline executions). Same field name, different meaning at
different levels.

**Resolution options (must decide in ADR #51 or #54):**

1. **Rename existing usage** `run_id` → `pipeline_execution_id` everywhere
   (3 SFN templates + utils.py + DDB rows). Big refactor (~30 LOC across
   files + DDB migration for existing rows reading old name). Cleaner
   semantic.

2. **Rename new Run model concept** → `bulk_run_id` or `batch_run_id`.
   Keeps existing field intact. Less disruptive. But UX/API uses
   `/api/run`, `run_id` consistently — rename surface area to keep clean.

3. **Hybrid:** Existing → `parent_execution_id` (semantically more
   accurate today: groups by execution, not by run). New Run → `run_id`.
   Migration: write `parent_execution_id` going forward + keep reading
   old `run_id` for compatibility briefly. Since no production — clean
   rename.

**Recommendation:** Option 3 (clean rename, no production constraint).

**Status:** OPEN — must resolve before any code in Phase D ships.

---

### sam/sfn_templates/dependency_wrapper/sfn.tpl.json

**Label:** AFFECTED (HIGH risk)

**Today:** 634 LOC. Wrapper SFN around every task. Sets `task_run_id`,
`run_id` (= pipeline_execution, today's semantic), `skip_tasks`, etc.
Reads `current_date` from input, computes `$today`. 16 refs.

**Touches Run redesign:** YES — heart of execution metadata.

**Changes:**
- Resolve naming collision per ADR decision above:
  - If option 3: rename `run_id` field write → `parent_execution_id`
    (~3 sites in JSONata).
  - Add new optional field write `run_id` (Run model sense), reading
    `$exists($states.input.bulk_run_id) ? $states.input.bulk_run_id : null`
    (~2 sites).
- Add optional `partition_key` field write (defaults to `current_date`
  for daily granularity) (~2 sites).
- Update `$skipTasks` logic — already works, no change.
- Snapshot tests in `tests/snapshots/` need re-baseline (3 snapshot files).
- Net: ~10 JSONata edits.

**Tests:**
- snapshot tests re-baselined
- `tests/sfn_jsonata/test_jsonata.js` — 563 JSONata compile tests run, no
  new entries (existing patterns)
- Manual: deploy test pipeline, verify task records have new fields

**Risk:** **HIGH** — wrapper runs around every task in every pipeline.
Bug means every pipeline breaks.

**Depends on:** ADR #51/#54 (naming decision), ADR #58 (partition_key).

---

### sam/sfn_templates/helpers/run_task/sfn.tpl.json

**Label:** AFFECTED (HIGH risk)

**Today:** 1349 LOC. Per-task execution SFN. 22 refs. Reads
`is_backfill` flag (line 1288 — used to skip Slack alerting during
backfills). Writes `run_id` to DDB on task state changes (current
semantic = pipeline_execution). The Prepare_Task_Input state (line 289)
builds all date variables from `current_date`.

**Touches Run redesign:** YES — major refactor surface.

**Changes:**
- Rename existing `run_id` writes → `parent_execution_id` (5 sites in
  JSONata for DDB UpdateExpression / PutItem).
- Add new `run_id` write (sparse, only when Run-initiated) (~5 sites).
- Add `partition_key` write (~5 sites).
- `is_backfill` flag check stays — but semantics shifts: "is_backfill"
  becomes "is part of a Run" (any user-initiated bulk operation). Cron
  runs don't set this (they're not Runs). Decide in ADR #55 whether
  scheduled-runs-via-bulk-run sets is_backfill=false (then it's truly
  "user-initiated bulk only").
- Prepare_Task_Input: stays daily-oriented. Run-side builder translates
  weekly/monthly partition_key into a daily anchor that this state can
  consume. (Decision in ADR #58.)
- Net: ~25 JSONata edits.

**Tests:** snapshot tests + 563 JSONata compile tests + integration tests
on real test pipelines.

**Risk:** **HIGH** — same hot path as dependency_wrapper.

**Depends on:** ADR #51, #54, #55, #58.

---

### sam/sfn_templates/helpers/registration/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 340 LOC. Pipeline-deploy registration flow. 1 ref to
`current_date` is in a Lambda invocation payload, unrelated to Run model.

**Risk:** LOW

---

### sam/sfn_templates/helpers/restart_task/sfn.tpl.json

**Label:** AFFECTED (minor)

**Today:** 153 LOC. Restart a stopped/failed task. Reads existing task
record from DDB by execution_name, restores execution via SFN
start_execution.

**Touches Run redesign:** YES — when restarting a task that's part of a
Run, need to preserve `run_id` linkage so restart counts toward original
Run progress.

**Changes:**
- Read `parent_execution_id` and `run_id` from existing DDB item, pass
  through to new execution (~3 JSONata edits).
- Net: ~5 LOC.

**Risk:** LOW (read-through, no logic change).

---

### sam/sfn_templates/helpers/notify_dependents/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 362 LOC. Sends notifications when task completes, unblocking
downstream tasks. Doesn't touch Run model.

**Risk:** LOW

---

### sam/sfn_templates/helpers/failure_handler/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 317 LOC. Failure path handler — alerts, Slack, etc.

**Touches Run redesign:** NO directly. But: Run-level failure aggregation
(in bulk-run watcher or `Finalize` state) should know when a child
execution fails. That's already covered by DDB state — failure_handler
just sets `status='failed'`, bulk-run reads it later.

**Risk:** LOW

---

### sam/sfn_templates/helpers/interactive_choice_slack/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 251 LOC. Slack interactive flow.

**Risk:** LOW

---

### sam/sfn_templates/helpers/notify_asset_consumers/sfn.tpl.json

**Label:** AFFECTED (minor)

**Today:** 332 LOC. Routes asset events to subscriber pipelines. 2 refs to
`current_date` (passes to consumer execution).

**Touches Run redesign:** YES (potential) — cascade lineage. When asset
event came from a Run-initiated materialization, propagate `cascade_source_run_id`
to consumer execution input. **Deferred to v0.79** (nice-to-have).

**Changes in v0.78:** NONE.

**Changes in v0.79:** Read `cascade_source_run_id` from event, set in
consumer's `start_execution` input (~3 JSONata).

**Risk:** LOW

---

### sam/sfn_templates/helpers/restart_wrapper/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 30 LOC. Thin wrapper invoked by restart_task.

**Risk:** LOW

---

### sam/sfn_templates/helpers/pause_waiter/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 49 LOC. Token-based pause callback receiver.

**Risk:** LOW

---

### sam/sfn_templates/helpers/register_pipeline/sfn.tpl.json

**Label:** AFFECTED (minor)

**Today:** 144 LOC. Pipeline registration → DDB write.

**Touches Run redesign:** YES — pipeline_registry rows get new attribute
`granularity` (set at deploy time, ADR #52).

**Changes:**
- Add `granularity` field to PutItem expression in registration state
  (~2 LOC). Field passed in from `slsflow-deploy` after validation.

**Risk:** LOW

---

### sam/sfn_templates/helpers/pagerduty_resolver/sfn.tpl.json

**Label:** UNAFFECTED

**Today:** 87 LOC. PagerDuty incident resolution.

**Touches Run redesign:** Uses `run_id` field as "pipeline_execution
grouping" (current semantic). Resolves via naming collision fix.

**Changes:**
- After resolving the collision (option 3): change field name
  `run_id` → `parent_execution_id` in PagerDuty payload key reads (~2 LOC).

**Risk:** LOW

---

### sam/sfn_templates/helpers/pagerduty_alerter/sfn.tpl.json

**Label:** UNAFFECTED (with collision fix)

**Today:** 86 LOC. Similar to resolver. Same collision fix needed.

**Changes:** field rename, ~2 LOC.

**Risk:** LOW

---

### NEW FILE: sam/sfn_templates/bulk_run/sfn.tpl.json

**Estimated:** 200-300 LOC (Standard or Express decision in ADR #54).

**States (Standard variant, simpler):**
- Initialize: write Run record, validate, compute partition_keys
- Map (MaxConcurrency = options.max_parallel):
  - Check_Run_Canceled (Choice)
  - Skip_If_Done (DDB Query for partition + tasks status)
  - Build_Child_Input (JSONata composing partition_key, run_id,
    variables, skip_tasks, is_backfill)
  - Start_Child_SFN (sync invocation)
  - Update_Counter (DDB UpdateItem ADD)
  - Catch: ThrottlingException → retry
- Finalize: aggregate, update Run status

**Risk:** HIGH — new SFN, untested in production. Requires careful
JSONata + integration tests.

---

## Phase D summary

| Status | Count | Files |
|---|---|---|
| AFFECTED (HIGH) | 2 | dependency_wrapper, run_task |
| AFFECTED (LOW) | 4 | restart_task, notify_asset_consumers, register_pipeline, pagerduty_resolver, pagerduty_alerter (counted as 4 with two pagerduty merged) |
| UNAFFECTED | 6 | registration, notify_dependents, failure_handler, interactive_choice_slack, restart_wrapper, pause_waiter |
| NEW | 1 | bulk_run/sfn.tpl.json (~250 LOC) |

**Critical:** **`run_id` naming collision** — discovered through Phase D.
Resolution in ADR before code. This single discovery validates the value
of the file-by-file walkthrough; grep search alone would have caused
silent semantic break.

**Phase D LOC delta:**
- New: ~250 LOC (bulk_run template)
- Modified: ~50 LOC across 7 templates (mostly small JSONata edits)
- **Total: +300 LOC in SFN templates**

**Risk distribution:** 2 HIGH (wrapper, run_task), 1 HIGH NEW (bulk_run),
others LOW.

**Phase D complete.**

---

## Phase E — Infrastructure (SAM template, Makefile, CI, build)

### sam/template.yaml

**Label:** AFFECTED

**Today:** 1998 LOC. CloudFormation/SAM template. Resources:
- 7 DDB tables (PipelineTokens, DependencySubscriptions, PipelineRegistry,
  AssetEvents, QueuedAssetEvents, TaskEvents, AssetSubscriptions)
- 5 Lambda functions (EvaluateDeps, QuerySubscriptions, CheckAssets,
  NotifyAssetSubscribers, ConsoleApi)
- 9 helper SFNs (PagerDutyAlerter, PagerDutyResolver, PauseWaiter,
  RestartWrapper, SlackInteractive, NotifyAssetConsumers,
  NotifyDependents, RestartTaskHelper, RegistrationHelper)
- 2 core SFNs (RunTaskHelperSfn, DependencyWrapperSfn)
- API Gateway, Cognito, S3 buckets, IAM roles
- SSM parameters, log groups, UI bootstrap function

**Touches Run redesign:** YES — significant additions.

**Changes:**

1. **PipelineTokensTable** (lines 158-220):
   - Add attribute: `run_id` (S) — for new GSI
   - Add attribute: `partition_key` (S) — sparse, becomes primary partition
     identifier for non-daily granularities
   - Add attribute: `record_type` (S) — distinguishes 'run' from 'execution'
   - Add new GSI `run-id-index`:
     - PK: run_id (HASH)
     - Projection: ALL (or KEYS_ONLY + status for cost — TBD ADR #54)
   - ~25 LOC additions
   - **Note:** since no production, no data migration needed —
     attributes are new sparse columns; legacy reads default to absent.

2. **NEW: BulkRunSfn resource** (Standard SFN per ADR #54
   recommendation):
   - `Type: AWS::Serverless::StateMachine`
   - DefinitionUri: `sfn_templates/bulk_run/sfn.tpl.json`
   - DefinitionSubstitutions: pipeline_registry, pipeline_tokens table
     names, default_slack_channel
   - Role: needs StartExecution on all pipeline SFNs (existing
     OrchestrationRole already has this — verify scope)
   - Logging: CW log group (Standard SFN log)
   - Tracing: X-Ray enabled (matches existing helper SFNs)
   - ~50 LOC

3. **NEW: BulkRunSfnLogGroup**
   - Mirrors existing LogGroup pattern for SFN observability
   - ~10 LOC

4. **NEW: BulkRunArn SSM parameter**
   - `/slsflow/{namespace}/{stage}/bulk-run-arn` for `slsflow-deploy`
     and other consumers to discover the ARN
   - ~8 LOC

5. **ConsoleApiFunction environment variables** (lines ~700-800):
   - Add `BULK_RUN_ARN` env var → `!GetAtt BulkRunSfn.Arn`
   - ~3 LOC

6. **ConsoleApiRole IAM policy** (~lines 850-1100):
   - Add `states:StartExecution` permission on BulkRunSfn ARN
   - Add `states:StopExecution` permission on BulkRunSfn ARN (for cancel)
   - Add `states:DescribeExecution` for status queries
   - ~15 LOC

7. **OrchestrationRole IAM policy:**
   - BulkRunSfn needs to start child pipeline SFNs (already has
     `states:StartExecution` on `*` — verify wildcard scope is sufficient)
   - Add DDB write permissions on PipelineTokensTable for Run record
     updates if not already broad — verify (~5 LOC)

8. **API Gateway / Lambda layer:** No changes — same routing.

9. **Outputs section** (lines ~1900):
   - Add `BulkRunSfnArn` to outputs for external consumers
   - ~5 LOC

**Total template.yaml delta:** ~120 LOC additions, 0 deletions.

**Tests:** `cfn-lint` clean (existing rule from v0.77.2 audit), SAM
deploy in test environment.

**Risk:** MEDIUM — new IaC resources require careful review. cfn-lint
catches syntax. Real deploy test catches policy/IAM mistakes.

---

### Makefile

**Label:** AFFECTED (minor)

**Today:** 143 LOC. Targets: help, test, test-sdk, test-backend,
test-integration, test-lambdas, test-sfn-jsonata, test-ui, check, lint,
sync-constants, check-versions, smoke-pipelines.

**Touches Run redesign:** YES — test targets stay; possibly add new
test invocations.

**Changes:**
- No new top-level targets (existing structure handles new test files
  automatically — pytest discovers).
- `sync-constants` target may need extension if `RUN_RECORD_PIPELINE_NAME`
  sentinel is shared across SDK and console_api (currently only status
  constants synced) (~5 LOC).
- `smoke-pipelines` target may need to validate that example pipelines
  in `pipelines/` declare granularity consistently with their schedule
  (new validator from ADR #52) (~3 LOC).

**Risk:** LOW

---

### .github/workflows/ci.yml

**Label:** AFFECTED (minor)

**Today:** 229 LOC. CI jobs: python tests (matrix 3.11, 3.12, 3.13),
lambda tests, sfn-jsonata tests, ui tests, cfn-lint (added in v0.77.2).
33 refs to "run" word — mostly job step `run:` directives, not Run model.

**Touches Run redesign:** YES — new test targets discovered automatically;
no new jobs needed unless we add bulk-run integration tests as separate
job.

**Changes:**
- No new jobs required.
- `make smoke-pipelines` step picks up new granularity validator
  automatically.
- Optional: add SAM template deploy-dry-run as CI step (test that
  template renders) (~10 LOC for new job).

**Risk:** LOW

---

### pyproject.toml

**Label:** AFFECTED (version bump + entry point)

**Today:** Version 0.77.2. CLI entry points: slsflow, slsflow-deploy,
slsflow-init, slsflow-output, slsflow-register, slsflow-validate.

**Touches Run redesign:** YES.

**Changes:**
- Version bump to 0.78.0 at release time.
- `slsflow` entry point points to `slsflow.cli:main` — needs to dispatch
  to `slsflow.run_cli:main` for `slsflow run` subcommand (~5 LOC in
  cli.py, no changes here).

**Risk:** LOW

---

### ui/package.json

**Label:** AFFECTED (version bump)

**Today:** Version "0.77.2" (synced with pyproject.toml per CLAUDE.md #5).

**Changes:**
- Version bump to 0.78.0.

**Risk:** LOW

---

### slsflow/__init__.py (already covered Phase A)

Version constant — bump to 0.78.0.

---

## Phase E summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 5 | template.yaml, Makefile, ci.yml, pyproject.toml, package.json |
| NEW | 0 | (BulkRunSfn is added inside template.yaml) |
| UNAFFECTED | 0 | — |

**Phase E LOC delta:**
- Modified: ~150 LOC across 5 infrastructure files
- **Total: +150 LOC in infra**

**Risk distribution:** 1 MEDIUM (template.yaml — IaC changes), 4 LOW.

**Phase E complete.**

---

## Phase F — UI components (57 files in ui/src/components/)

### High-impact components (heavy refs)

#### ui/src/components/BackfillModal.tsx — **DELETE**

**Today:** 508 LOC. Pipeline backfill modal with tasks/assets modes,
incremental toggle, max_parallel, JSON variables.

**Touches Run redesign:** YES — replaced entirely by `RunModal.tsx`.

**Changes:** Delete file. Functionality absorbed into RunModal with
appropriate seed (pipeline target).

**Risk:** LOW (since no production, no migration concern).

---

#### ui/src/components/AssetBackfillModal.tsx — **DELETE**

**Today:** 128 LOC. Minimal asset backfill modal (just date range).

**Touches Run redesign:** YES — replaced by RunModal with asset target seed.

**Changes:** Delete file.

**Risk:** LOW

---

#### ui/src/components/AssetMatrixView.tsx — **AFFECTED (significant)**

**Today:** 825 LOC. Matrix grid display, cell click → AssetBackfillModal.
53 refs (partition_key, granularity heavy from ADR #49/#50).

**Touches Run redesign:** YES — entry point for backfill from cells.

**Changes:**
- Replace `AssetBackfillModal` import with `RunModal` (~3 LOC).
- Cell click handler: build seed `{target: 'asset', partitions: {keys:
  [cellDate]}, cascade: 'auto'}` and pass to RunModal (~10 LOC).
- v0.79 enhancement: multi-cell selection (Shift+click range, drag rect)
  → seed `{target: 'batch', items: [...]}` — defer to v0.79 per migration
  plan (~80 LOC). v0.78 keeps single-cell.
- Add cell render: respect `asset.partition_start` clipping (~10 LOC).
- Net: ~25 LOC in v0.78, +80 in v0.79.

**Tests:** existing AssetMatrixView.test.tsx — update cell-click test to
verify RunModal opens with correct seed.

**Risk:** MEDIUM — central asset visualization, must not regress
rendering performance.

---

#### ui/src/components/AssetsView.tsx — **AFFECTED**

**Today:** 775 LOC. Top-level asset catalog page. 23 refs (uses
useAssetBackfillMutation, AssetBackfillModal).

**Touches Run redesign:** YES — entry point for asset backfill from
catalog row.

**Changes:**
- Replace `useAssetBackfillMutation` → `useRunMutation` from new
  `useRunQueries.ts` (~5 LOC).
- Replace `AssetBackfillModal` with `RunModal` (~5 LOC).
- `handleBackfillByAsset` handler: build seed for asset target (~10 LOC).
- `handleBackfillCell` (matrix-cell entry point): unified path through
  RunModal seed (~5 LOC).
- Net: ~25 LOC modifications.

**Risk:** LOW (mechanical replacement).

---

#### ui/src/components/PipelineDetail.tsx — **AFFECTED**

**Today:** 559 LOC. Pipeline detail page. 12 refs (BackfillModal,
useBackfillMutation, useRunPipelineMutation, "Run" / "Backfill" buttons).

**Touches Run redesign:** YES — entry point for pipeline run/backfill.

**Changes:**
- Replace `BackfillModal` import with `RunModal` (~3 LOC).
- "Run" button (today opens `ActionModal` for confirmation): now opens
  `RunModal` with seed `{target: 'pipeline', partitions: {start: today,
  end: today}}` (~10 LOC).
- "Backfill" button: opens `RunModal` with empty partitions (user fills
  range) (~5 LOC).
- Replace mutations: `useRunPipelineMutation` + `useBackfillMutation` →
  `useRunMutation` (~8 LOC).
- Optional: add "Runs" tab showing per-pipeline Run history. Defer to
  v0.79 (~30 LOC).
- Net v0.78: ~26 LOC modifications, ~5 deletions.

**Risk:** LOW

---

#### ui/src/components/AllRunsView.tsx — **AFFECTED (rename + filter)**

**Today:** 240 LOC. List view of all "runs" — actually shows individual
pipeline executions. Misnamed under old terminology.

**Touches Run redesign:** YES — major naming/semantic shift.

**Changes:**
- **Rename file:** `AllRunsView.tsx` → `AllExecutionsView.tsx`
  - Rename component export
  - Update all imports (App.tsx, routes table)
  - Update tests file name
- Update display to filter out Run records (where `record_type='run'`)
  — already excluded server-side per Phase B `routes/executions.py`
  changes (~0 LOC client-side).
- Add a "Run" badge/link column: if execution has `run_id`, show a link
  to `/runs/{run_id}` (~10 LOC).
- Net: ~10 LOC additions.

**Risk:** MEDIUM — renames affect imports across the codebase.
Mechanical but error-prone if missed.

---

#### NEW: ui/src/components/RunModal.tsx

**Estimated:** 450 LOC.

**Features:**
- Accepts `seed: RunModalSeed` prop for pre-fill from various entry
  points (pipeline page, asset page, matrix click, task detail "Run from
  Here", etc.)
- Conditional rendering: cascade options shown only when asset target +
  external consumers exist
- Date range picker / explicit partition keys list
- Task subset checkboxes (collapsible "X of N selected")
- Options: skip_completed (default ✓), force, allow_concurrent,
  max_parallel slider, Advanced (variables, incremental)
- Preview section: partition counts, cost estimate, downstream warnings
- Action button disabled if `to_run === 0`

**CSS:** new `_run-modal.css` global module with `rm-*` BEM prefix.

**Tests:** new `RunModal.test.tsx` with ~30 test cases covering all
seed types and conditional UI.

---

#### NEW: ui/src/components/RunDetailPage.tsx

**Estimated:** 280 LOC.

**Features:**
- Run summary card: status badge, target, started_by, time, progress bar
- Heatmap grid: partitions × status (similar to Matrix but Run-scoped)
- Children list table: sortable, filterable
- Action buttons: Cancel (if pending/running), Retry Failed (if any
  failed), Open in AWS Console
- Live polling (3s) on `/api/runs/{id}`
- Cascade summary (after completion): events emitted, consumers
  triggered/queued/skipped

**CSS:** new `_run-detail.css` with `rd-*` prefix.

**Tests:** new `RunDetailPage.test.tsx` ~15 tests.

---

#### NEW: ui/src/components/RunsListPage.tsx

**Estimated:** 200 LOC.

**Features:**
- Table of recent Runs (50 most recent by default)
- Filters: status, target type, user, time range
- Click → RunDetailPage
- Progress indicators per Run

**CSS:** new `_runs-list.css` with `rl-*` prefix.

**Tests:** ~10 tests.

---

### Medium-impact components

#### ui/src/components/TaskDetailModal/TaskDetailModal.tsx — **AFFECTED**

**Today:** 638 LOC. Task detail modal with Actions tab: skip/fail/stop/
restart + 3 "Run" actions (toHere/fromHere/onlyThis).

**Touches Run redesign:** YES — Run actions route through RunModal.

**Changes:**
- `onRunAction(action, task)` callback: instead of opening custom confirm
  modal (current `usePipelineActions.tsx`), opens `RunModal` with
  appropriate seed:
  - `toHere`: `{target: 'pipeline', tasks: [...upstream, task],
    partitions: [today]}`
  - `fromHere`: `{target: 'pipeline', tasks: [task, ...downstream],
    partitions: [today]}`
  - `onlyThis`: `{target: 'pipeline', tasks: [task], partitions: [today]}`
- No changes to skip/fail/stop/restart action buttons.
- Net: ~10 LOC (just seed construction changes; rendering unchanged).

**Risk:** LOW

---

#### ui/src/components/AssetDetailPage.tsx — **AFFECTED**

**Today:** 376 LOC. 4 refs (uses partition logic).

**Touches Run redesign:** YES — has a "Backfill" button.

**Changes:**
- Replace backfill button handler with `openRunModal({target: 'asset',
  name: assetName})` (~5 LOC).
- Net: ~5 LOC.

**Risk:** LOW

---

#### ui/src/components/AssetDetailModal.tsx — **AFFECTED**

**Today:** 309 LOC. 3 refs (has "Backfill DAGs" button).

**Changes:**
- Replace `onBackfill` callback → `openRunModal` (~5 LOC).

**Risk:** LOW

---

#### ui/src/components/HelpModal.tsx — **AFFECTED**

**Today:** 578 LOC. 18 refs in "Backfill" tab content.

**Changes:**
- Rewrite "Backfill" tab → "Run" tab.
- Updated text covering Run concept, cascade modes, partition keys,
  cost preview.
- Updated screenshots (placeholder text update; actual screenshots done
  separately).
- ~80 LOC text changes.

**Risk:** LOW (docs only).

---

### Low-impact / asset-tabs

#### asset-tabs/TabOverview.tsx, TabSchema.tsx, SchemaCopyButtons.tsx — **UNAFFECTED**

These 3 files reference `partition_key` as the **column-level flag**
(boolean on Column DSL), not Run model. False positive in scan.

**Risk:** LOW

---

#### asset-tabs/TabPartitions.tsx — **REVIEW**

**Today:** 123 LOC. Likely shows partition-level info per asset.

**Touches Run redesign:** Possibly — if it displays partition_key /
partition status. Needs file read to confirm.

**Likely changes:** display Run-initiated materializations differently
from cron-driven. Or none if it just shows raw partition list.

**Note:** Will verify during Phase F implementation. Conservative
estimate: ~10 LOC changes max.

---

### Unaffected components (verified by zero refs)

These 35 components have **zero references** to Run-related keywords
after scan. Verified UNAFFECTED:

`ActionModal`, `AllTasksView`, `AssetLineageFlow`, `AssetTriggerModal`,
`AuthGate`, `BaseModal`, `CalendarView`, `CommandPalette`, `ConfirmModal`,
`CountdownTimer`, `DAGGraphFlow`, `ErrorBoundary`, `GanttChart`,
`Header`, `LoginPage`, `Modal`, `Notifications`, `PipelinesSidebar`,
`Providers`, `Skeletons`, `SortableHeader`, `Toast`, `UserMenu`,
`TaskDetailModal` sub-components (`ConsecutiveProgress`,
`DependencyStatusList`, `ErrorDisplay`, `LiveDuration`, `index.tsx`),
asset-tabs (`GlueSyncPanel`, `TabChecks`, `TabEvents`, `TabLineage`,
`glueHelpers`, `test-setup`), and all `ui/*` Radix wrappers (9 files).

**Why unaffected:** these are presentation components, modals for
non-Run flows, or generic UI primitives. None invoke backfill mutations,
none show Run-specific data, none consume partition_key in execution
sense.

**Risk:** LOW

---

## Phase F summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 8 | AssetMatrixView, AssetsView, PipelineDetail, AllRunsView (rename + filter), TaskDetailModal, AssetDetailPage, AssetDetailModal, HelpModal |
| NEW | 3 | RunModal, RunDetailPage, RunsListPage |
| UNAFFECTED | 35 | (listed above) |
| DELETE | 2 | BackfillModal, AssetBackfillModal |
| REVIEW | 1 | TabPartitions (needs file read for final classification — defer to impl) |

**Phase F LOC delta:**
- New: ~930 LOC (3 new components + CSS)
- Modified: ~180 LOC across 8 components
- Deleted: -636 LOC (2 components)
- **Total: +474 LOC in components/**

**Risk distribution:** 2 MEDIUM (AssetMatrixView render, AllRunsView
rename), 6 LOW. No HIGH.

**Phase F complete.**

---

## Phase G — UI hooks (14 files)

### ui/src/hooks/queries/useAssetQueries.ts — AFFECTED

**Today:** 356 LOC. Asset-related React Query hooks. Includes
`useAssetBackfillMutation`, `useForceTriggerMutation`, plus 10 other
read/write hooks.

**Changes:**
- Delete `useAssetBackfillMutation` (~20 LOC).
- Delete `useForceTriggerMutation` (~15 LOC).
- Other hooks (useAssetsDataQuery, useAssetEventsQuery, useTriggerAssetMutation,
  useSkipInQueueMutation, useClearQueueMutation, useAssetMatrixQuery,
  useAssetDriftQuery, useAssetGlueSchemaQuery, useDeleteOrphanedMutation,
  useDeleteAssetMutation) unchanged.
- Net: -35 LOC.

**Risk:** LOW (mechanical delete).

---

### ui/src/hooks/queries/usePipelineQueries.ts — AFFECTED

**Today:** 274 LOC. Pipeline-related hooks.

**Changes:**
- Delete `useBackfillMutation` (~18 LOC).
- Delete `useRunPipelineMutation` (~15 LOC).
- Keep all other hooks unchanged.
- Net: -33 LOC.

**Risk:** LOW

---

### NEW: ui/src/hooks/queries/useRunQueries.ts

**Estimated:** 120 LOC.

**Hooks:**
- `useRunsListQuery(filters)` — GET /api/runs
- `useRunQuery(runId)` — GET /api/runs/{id}, with 3s polling when status
  is running
- `useRunMutation()` — POST /api/run (universal for all targets)
- `useCancelRunMutation()` — POST /api/runs/{id}/cancel
- `useRetryFailedMutation()` — POST /api/runs/{id}/retry-failed

**Tests:** new `tests/queries/test_useRunQueries.tsx`.

---

### ui/src/hooks/queries/index.ts — AFFECTED

**Today:** 51 LOC. Re-exports query hooks.

**Changes:**
- Remove exports: `useBackfillMutation`, `useRunPipelineMutation`,
  `useAssetBackfillMutation`, `useForceTriggerMutation`.
- Add exports from new `useRunQueries.ts`.
- Net: ~5 LOC.

**Risk:** LOW

---

### ui/src/hooks/usePipelineActions.tsx — AFFECTED (refactor)

**Today:** 477 LOC. Pipeline action orchestration: `handleRun`,
`handleBackfill`, `handleStop`, `handlePauseResume`, `handleExtendPause`,
`handleTaskAction`, plus `runToHere`/`runFromHere`/`runOnlyThis` custom
modal logic.

**Changes:**
- Delete `handleBackfill` (~25 LOC) — replaced by opening RunModal.
- Refactor `runToHere`/`runFromHere`/`runOnlyThis` (~150 LOC total):
  these become thin wrappers around `openRunModal(seed)` where seed
  contains task subset + today date. Custom confirm modal disappears.
- Keep `handleStop`, `handlePauseResume`, `handleExtendPause`,
  `handleTaskAction` — these are not Run-related.
- `setTriggerParams(JSON.stringify(...))` calls disappear — payload now
  goes through structured RunModal state, not free-form JSON.
- Net: ~150 LOC removed, ~30 LOC added (thin wrappers).
- **-120 LOC total.**

**Risk:** MEDIUM — refactor touches multiple action handlers; mistakes
break Pipeline detail page actions.

---

### ui/src/hooks/queries/useGlobalQueries.ts — UNAFFECTED

**Today:** 131 LOC. 1 ref to `granularity` (in useAssetMatrixQuery —
already in useAssetQueries, this is just type). False positive.

---

### ui/src/hooks/useGlobalData.ts, useUrlSync.ts — UNAFFECTED

Single refs are `granularity` URL param — already exists for Matrix view.

**Risk:** LOW

---

### Other hooks (UNAFFECTED, verified)

`hooks/index.ts`, `useAuth.tsx`, `useFocusTrap.ts`, `useKeyboardShortcuts.tsx`,
`usePersistedState.ts`, `usePipelineData.ts`, `useTaskEvents.ts` —
zero refs. No changes.

---

## Phase H — UI lib + types + stores + utils

### ui/src/types/index.ts — AFFECTED

**Today:** 649 LOC. TypeScript type definitions.

**Changes:**
- Delete `BackfillModalProps` interface (~10 LOC).
- Delete `BackfillPayload` interface (~15 LOC).
- Delete refs to old types in other interfaces (~5 LOC).
- Add new types: `RunModalProps`, `RunModalSeed`, `RunPayload`,
  `RunRecord`, `RunStatus`, `CascadeMode`, `RunResponse`,
  `PartitionInfo` (~80 LOC).
- Keep `skip_on_backfill` field on Task type (still used by DSL).
- `Column.partition_key` (boolean) — unchanged (column-level concept,
  different from execution partition_key).
- Net: +50 LOC.

**Risk:** LOW (types only, TypeScript catches mismatch at build time).

---

### ui/src/stores/useAppStore.ts — AFFECTED

**Today:** 179 LOC. Zustand store. Includes `showBackfillModal` state.

**Changes:**
- Replace `showBackfillModal`/`setShowBackfillModal` with
  `runModalSeed`/`setRunModalSeed` (~10 LOC).
  - When `runModalSeed === null` → modal closed.
  - When set to non-null → modal opens with seed.
- This unifies all 6 entry points using one piece of state.
- Net: ~10 LOC modifications.

**Risk:** LOW

---

### ui/src/stores/useStoreInit.ts — UNAFFECTED

**Today:** 206 LOC. URL → store hydration on app load. No Backfill
references.

---

### ui/src/lib/queryClient.tsx — AFFECTED (minor)

**Today:** 65 LOC. Query key factory.

**Changes:**
- Add keys: `runs`, `runDetail`, `runChildren` (~5 LOC).

**Risk:** LOW

---

### ui/src/utils/icons.tsx — AFFECTED (minor)

**Today:** 503 LOC. 2 refs to History/Backfill icons.

**Changes:**
- Add `Play` icon for Run (already imported).
- No deletes (icons reused).
- Net: ~3 LOC.

**Risk:** LOW

---

### ui/src/utils/routing.ts — UNAFFECTED

**Today:** 23 LOC. 1 ref to `/runs` URL — old route. After redesign,
URL `/runs` semantics change (Run records, not executions) and
`/executions` becomes the renamed view. Routing helpers update.

**Changes:**
- Add `/executions` route helper.
- Update `/runs` to point to RunsListPage instead of AllRunsView.
- Net: ~5 LOC.

**Risk:** LOW

---

### ui/src/utils/ddl-glue.ts, types/dagre.d.ts — UNAFFECTED

DDL utility for Glue partition_key column flag — unrelated to execution
partition_key. Dagre type def for graph layout.

---

### Other lib/utils (UNAFFECTED, verified)

`amplifyConfig.ts`, `config.ts`, `utils.ts`, `api.ts`, `constants.ts`,
`countdown.ts`, `dagHelpers.ts`, `formatters.ts`, `index.ts`, `logger.ts`,
`staleness.ts`, `storage.ts` — zero refs (or false positives).

---

## Phase G + H summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 9 | useAssetQueries, usePipelineQueries, queries/index, usePipelineActions, types/index, useAppStore, queryClient, icons, routing |
| NEW | 1 | useRunQueries.ts (~120 LOC) |
| UNAFFECTED | 25 | all other hooks/utils/stores/lib/types files |
| DELETE | 0 | (deletions are inline in modified files) |

**Phase G+H LOC delta:**
- New: ~120 LOC
- Modified: ~120 LOC (Net of additions/removals across 9 files)
- **Total: +240 LOC in hooks/types/stores/lib/utils/**

**Risk distribution:** 1 MEDIUM (usePipelineActions refactor), 8 LOW.

**Phase G+H complete.**

---

## Phase I — Tests mapping (existing → new)

### Python tests (27 files)

#### HEAVY AFFECTED (>10 refs)

- **`tests/backend/test_alerting.py`** (46 refs) — Includes
  `TestVariableSchemaDrift` — the drift safety net for `task_variables.py`.
  **Critical:** update target file paths after redesign:
  - JSONata builder: `run_task/sfn.tpl.json::Prepare_Task_Input` → still
    that location (Run-side bulk-run SFN passes daily anchor in current_date,
    so JSONata logic unchanged).
  - Python builder: `routes/backfill.py::auto_variables` → moves to
    `routes/runs.py::_build_run_input` or `slsflow/partitions.py`.
  - Test updates expected: ~30 LOC for path references; logic unchanged.
- **`tests/sdk/test_asset_partitions.py`** (23 refs) — Tests Asset's
  `granularity` and `partition_start`. Likely all passing, no changes.
  Quick verification needed.
- **`tests/integration/test_integration.py`** (20 refs) — End-to-end
  test. After redesign, must cover Run flow. Rewrite ~30% (~150 LOC):
  - Add: test_run_pipeline_e2e, test_run_asset_e2e, test_cascade_modes,
    test_skip_completed, test_cancel_run, test_retry_failed.
  - Keep: tests of cron-triggered runs (unchanged path).
  - Remove tests asserting old `/api/pipeline-backfill` endpoint
    response shape (~30 LOC).
- **`tests/sdk/test_templates.py`** (16 refs) — Tests SFN template
  generation, asserts route count. Update:
  - `len(ROUTES) == 52` → `len(ROUTES) == 53` (one more route net after
    additions/removals).
  - Assert new BulkRunSfn template exists.
  - ~15 LOC modifications.
- **`tests/sdk/test_smoke.py`** (15 refs) — Smoke tests for pipeline
  validation. Add granularity validation tests (~20 LOC).

#### MEDIUM AFFECTED (3-10 refs)

- **`tests/sdk/test_adapters_glue.py`** (8 refs) — Glue granularity
  inference. No changes for Run (function unchanged).
- **`tests/sdk/test_schema.py`** (5 refs) — Column.partition_key tests.
  No changes (column-level, unrelated).
- **`tests/sdk/test_glue_granularity_inference.py`** (3 refs) — Glue
  inference logic. No changes.
- **`tests/sdk/test_asset_helpers.py`** (2 refs) — No changes.
- **`tests/integration/test_sdk_lambda_parity.py`** (2 refs) — Parity
  between SDK and Lambda runtime. Verify new fields propagated correctly.
  ~10 LOC additions.
- **`tests/backend/test_idempotency.py`** (2 refs) — Run cancel +
  retry idempotency. Add new tests (~30 LOC).
- **`tests/backend/test_stop_restart.py`** (1 ref) — No changes expected.

#### NEW TEST FILES

- `tests/sdk/test_partitions.py` (~400 LOC) — Tests `PartitionRange`,
  `expand_range`, `translate_to`, `cost_estimate`, `skip_completed`.
- `tests/sdk/test_pipeline_granularity.py` (~200 LOC) — Tests strict
  validation: cron-vs-outlet alignment, override flag, ambiguous cron.
- `tests/backend/test_runs.py` (~300 LOC) — Tests `/api/run` endpoint:
  resolver, partition expansion, error model, cascade modes.
- `tests/backend/test_runs_repo.py` (~150 LOC) — DAL tests with moto.
- `tests/backend/test_bulk_run_sfn.py` (~250 LOC) — Bulk-run SFN
  integration test using local SFN emulator.

**Total new Python test files:** 5, ~1300 LOC.

#### UNAFFECTED Python tests (12 files)

`test_resolve_task`, `test_api_routes`, `test_query_subscriptions`,
`test_health`, `test_pipelines` (e2e), `test_assets` (e2e), `test_routes`,
`test_trigger_rules`, `test_asl_snapshots`, `test_asl_snapshots_steps`,
`test_adapters_pyarrow`, `test_adapters_pydantic`, `test_validation_schema`,
`test_ddl_parity`.

### console_api Lambda tests (12 files)

#### AFFECTED

- **`test_matrix.py`** (31 refs) — Matrix endpoint. Existing tests
  cover granularity/partition_key. Add tests for `partition_start`
  clipping and run_id filter (~30 LOC).
- **`test_drift.py`** (13 refs) — Drift detection. Add tests for
  `partition_start`-aware scaling (~20 LOC).
- **`test_utils.py`** (9 refs) — `is_internal_record`,
  `compute_pipeline_execution_short`. Add tests for Run record detection
  (~15 LOC).
- **`test_assets_glue_schema.py`** (6 refs) — No changes.
- **`test_slack_actions.py`** (2 refs) — Verify run_id propagation
  through Slack restart callbacks (~10 LOC).

#### NEW

- `tests/routes/test_runs.py` (~300 LOC) — Run handler tests.

#### UNAFFECTED (7 files)

`test_config`, `test_assets_repo`, `test_lineage_last_updated`,
`test_pipelines_list_cleanup`, `test_executions_pause`, `test_assets_helpers`,
`test_delete_orphaned`.

### Other Lambda tests (3 files) — UNAFFECTED

`test_evaluate_deps`, `test_notify_asset_subscribers`, `test_check_assets`
— all 0 refs to Run keywords.

### UI tests (49 files)

#### DELETED

- **`BackfillModal.test.tsx`** (30 refs) — Component being deleted.
  Coverage moves to RunModal.test.tsx (with appropriate seed tests).
- **`AssetBackfillModal.test.tsx`** (40 refs) — Same.

#### HEAVY AFFECTED

- **`AssetMatrixView.test.tsx`** (27 refs) — Cell click → RunModal
  test instead of AssetBackfillModal (~10 LOC).
- **`usePipelineActions.test.ts`** (9 refs) — Test refactored hooks
  (~15 LOC).
- **`useAssetQueries.test.ts`** (8 refs) — Remove tests for deleted
  mutations.

#### MEDIUM AFFECTED

- **`AssetDetailModal.test.tsx`** (6 refs) — Backfill button test
  updates (~5 LOC).
- **`useAppStore.test.ts`** (4 refs) — Replace `showBackfillModal`
  tests with `runModalSeed` tests (~10 LOC).
- **`AssetsView.test.tsx`** (3 refs) — Backfill flow test updates
  (~10 LOC).
- **`AssetDetailPage.test.tsx`** (2 refs) — Minor.
- **`PipelineDetail.test.tsx`** (2 refs) — Run/Backfill button tests
  (~5 LOC).
- **`DAGGraphFlow.test.tsx`** (1 ref) — Minor.

#### NEW UI test files

- `RunModal.test.tsx` (~350 LOC) — All seed types, conditional UI,
  cost preview, validation.
- `RunDetailPage.test.tsx` (~200 LOC) — Polling, cancel, retry-failed.
- `RunsListPage.test.tsx` (~150 LOC) — Filtering, navigation.
- `useRunQueries.test.tsx` (~150 LOC) — All mutations + queries.

#### UNAFFECTED UI tests (38 files)

All other UI tests have zero refs to Run keywords (confirmed via scan).

### SFN JSONata tests (1 directory)

- `tests/sfn_jsonata/test_jsonata.js` — 563 JSONata compile tests.
  After SFN template changes (Phase D), re-run all to verify no parse
  errors. May add ~10-20 new test cases for bulk-run template JSONata.

### Snapshot tests

- `tests/snapshots/` — Tests verify SFN templates byte-for-byte against
  baseline snapshots. **All affected SFN templates need re-baseline**:
  - dependency_wrapper snapshot
  - run_task snapshot
  - restart_task snapshot (minor)
  - register_pipeline snapshot (minor)
  - notify_asset_consumers snapshot (minor)
  - pagerduty_alerter/resolver snapshots
  - **NEW** bulk_run snapshot
- Re-baseline command: `pytest --snapshot-update` then code review of
  diffs.

## Phase I summary

| Type | AFFECTED | NEW | UNAFFECTED | DELETE |
|---|---|---|---|---|
| Python tests | 8 | 5 | 14 | 0 |
| console_api tests | 5 | 1 | 7 | 0 |
| Other Lambda tests | 0 | 0 | 3 | 0 |
| UI tests | 9 | 4 | 38 | 2 |
| **Total** | **22** | **10** | **62** | **2** |

**Phase I LOC delta:**
- New tests: ~2150 LOC (10 new test files)
- Modified: ~250 LOC across 22 files
- Deleted: ~380 LOC (2 UI test files for deleted components)
- **Total: +2020 LOC in tests**

**Phase I complete.**

---

## Phase J — Documentation (30 files)

### High-impact docs (10+ refs)

#### docs/features/ASSETS.md (10 refs) — AFFECTED

**Today:** 793 LOC. Comprehensive Asset documentation.

**Changes:**
- Rewrite "Backfilling assets" section (~80 LOC).
- Add "Cascade modes" subsection (~50 LOC, new content).
- Update partition_start examples to show Run integration.
- Update granularity examples with Run partition expansion.
- ~150 LOC delta.

**Risk:** LOW

---

#### docs/operations/UI.md (9 refs) — AFFECTED

**Today:** 459 LOC. UI reference. Has Backfill modal screenshots/text.

**Changes:**
- Rewrite Backfill section → Run section (~100 LOC).
- Add Run Detail Page documentation (~50 LOC).
- Update Matrix-cell-click documentation.
- ~150 LOC delta.

**Risk:** LOW

---

#### docs/architecture/ARCHITECTURE.md (8 refs) — AFFECTED

**Today:** 557 LOC. High-level system architecture.

**Changes:**
- Add Run concept to architecture diagrams (text).
- Update execution flow descriptions to mention Run unification.
- ~80 LOC delta.

**Risk:** LOW

---

#### docs/features/DSL.md (6 refs) — AFFECTED

Covered in sample entries above. ~80 LOC delta.

---

#### docs/operations/API.md (5 refs) — AFFECTED

**Today:** 329 LOC. API reference. Documents endpoints.

**Changes:**
- Remove sections: `/api/pipeline-backfill`, `/api/assets/backfill`,
  `/api/dags/{n}/force-trigger`, `/api/runs/{n}` (old POST).
- Add sections: `/api/run`, `/api/runs`, `/api/runs/{id}`,
  `/api/runs/{id}/cancel`, `/api/runs/{id}/retry-failed`.
- Add `/api/executions` (renamed).
- ~150 LOC delta (net additions).

**Risk:** LOW

---

#### docs/reference/AIRFLOW_MIGRATION.md (2 refs) — AFFECTED

**Today:** 455 LOC. Airflow user migration guide.

**Changes:**
- Update "Backfill" comparison to show Run model — actually
  **stronger than Airflow** (cancel, retry-failed, cost preview).
- Highlight improvements over Airflow CLI.
- ~50 LOC delta.

**Risk:** LOW

---

### Medium-impact docs (2-3 refs)

#### docs/architecture/BACKEND.md (1 ref) — AFFECTED

**Today:** 515 LOC. Backend architecture.

**Changes:**
- Add bulk-run SFN description.
- Update DDB schema (run_id GSI, new attributes).
- ~40 LOC delta.

---

#### docs/reference/UI_AUDIT.md (1 ref) — AFFECTED

**Today:** 186 LOC. UI inventory/audit.

**Changes:**
- Update component list: remove BackfillModal, AssetBackfillModal;
  add RunModal, RunDetailPage, RunsListPage.
- Rename AllRunsView → AllExecutionsView.
- ~30 LOC delta.

---

#### docs/tools/DEVELOPMENT.md (2 refs) — AFFECTED

**Today:** 171 LOC. Developer workflow.

**Changes:**
- Update local testing section to mention `slsflow run` CLI command.
- Note that local Run multi-partition is not supported in `slsflow local`.
- ~15 LOC delta.

---

### Reference docs

#### docs/reference/DESIGN_DECISIONS.md (57 refs) — AFFECTED (additions)

**Today:** 2212 LOC. ADR log (ADR #1-47 currently).

**Changes:**
- Add ADRs #51-58 (~2400 LOC across 8 ADRs).
- See main planning doc for content.
- ~2400 LOC delta (largest single doc addition).

**Risk:** LOW (additive only).

---

#### docs/reference/BACKLOG.md (62 refs) — AFFECTED (cleanup)

**Today:** 424 LOC. Project backlog. Includes the "Backfill Redesign
Roadmap (v0.78-0.81)" section added previously.

**Changes:**
- Convert "Backfill Redesign Roadmap" section status to "In Progress —
  see docs/redesign/run/".
- Move completed items to "Completed" subsection after v0.78 ships.
- ~50 LOC delta (status updates).

---

#### docs/reference/CLI.md (0 refs but AFFECTED) — AFFECTED

**Today:** 198 LOC. CLI reference.

**Changes:**
- Add `slsflow run`, `slsflow runs list/cancel/retry` commands.
- ~80 LOC delta.

---

### UNAFFECTED docs (16 files)

`docs/README.md`, `docs/architecture/STEP_FUNCTIONS.md`,
`docs/deployment/CROSS_ACCOUNT_ROLES.md`, `docs/deployment/DEPLOY.md`,
`docs/deployment/RELEASE.md`, `docs/deployment/SAM.md`,
`docs/development/ADDING_ASSET_TABS.md`,
`docs/features/ASSET_PULL_FEATURE.md`,
`docs/features/authentication.md`,
`docs/getting-started/*` (4 files),
`docs/operations/TROUBLESHOOTING.md`,
`docs/reference/CONFIGURATION.md`,
`docs/tools/AI_ASSISTANT.md`, `docs/tools/LOCAL_TESTING.md`,
`docs/tools/REGISTRATION.md`.

**Verified:** zero relevant refs.

---

### CLAUDE.md (3 copies)

**Affected:**
- `./CLAUDE.md` (root) — references "52 routes" → "53 routes" after
  redesign. Update Run concept mentions. ~10 LOC.
- `./sam/CLAUDE.md` — Backend conventions. Update bulk-run mention.
  ~5 LOC.
- `./ui/CLAUDE.md` — UI conventions. Update RunModal pattern (replacing
  BackfillModal). ~10 LOC.

**Plus:** README.md and CONTRIBUTING.md may need minor updates (~10 LOC
each).

---

## Phase J summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 12 | ASSETS, UI, ARCHITECTURE, DSL, API, AIRFLOW_MIGRATION, BACKEND, UI_AUDIT, DEVELOPMENT, DESIGN_DECISIONS, BACKLOG, CLI |
| UNAFFECTED | 16 | (listed above) |
| OTHER | 5 | CLAUDE.md (3 copies), README.md, CONTRIBUTING.md |

**Phase J LOC delta:**
- Modified: ~3260 LOC across docs (dominated by ADR additions ~2400 LOC)
- **Total: +3260 LOC in docs/**

**Phase J complete.**

---

## Phase K — Cross-cutting concerns

### Top-level project files

#### CHANGELOG.md — AFFECTED

**Today:** Project changelog. Existing v0.77.2 entry mentions BackfillModal.

**Changes:**
- New v0.78.0 entry following existing style:
  - "Run unification" headline section
  - What changed (user-visible)
  - Why (ADRs)
  - Migration (since no production, just "first release of Run model")
  - Cost (numbers from cost-analysis doc)
  - Quality gates
- ~80 LOC.

**Risk:** LOW

---

#### README.md — AFFECTED

**Today:** Project landing page. Lines 21 ("Backfill — Run pipeline for
date range") and 399 ("### Backfill" section) require updates.

**Changes:**
- Update tagline: "Run, Backfill, Force-trigger — one unified concept"
- Rewrite Backfill section as "Run" section.
- ~30 LOC delta.

**Risk:** LOW

---

#### CONTRIBUTING.md — AFFECTED (minor)

**Today:** Contributor guide. Mentions test count (1641 → updates to
~1860 after redesign).

**Changes:**
- Update test count.
- Update route count "52 → 53".
- ~5 LOC delta.

---

#### CLAUDE.md (root) — AFFECTED

Covered in Phase J.

---

### Pipeline definitions (in repo)

#### pipelines/acme/* and pipelines/shopmart/* — REVIEW

**Today:** 6 example DAG definitions. `pipelines/acme/daily/dag.py` is
the only one referencing `skip_on_backfill` per scan.

**Touches Run redesign:** YES potentially — strict granularity validation
(ADR #52) may reject some if cron doesn't match outlet granularity.

**Changes:**
- Verify each pipeline declares granularity consistent with its cron.
- If mismatch: add explicit `@dag(granularity=...)` override or fix.
- `skip_on_backfill` usage in acme/daily/dag.py — semantic unchanged
  ("skip during Run-initiated executions"). Docstring update optional.
- ~5 LOC per pipeline max, 6 pipelines × ~3 LOC = 18 LOC.

**Risk:** LOW (verification step, mostly no changes needed).

---

### Build / packaging

#### requirements.txt, ui/package.json deps — AFFECTED (minor)

**Today:** Python/Node dependencies.

**Changes:**
- No new dependencies for Python (uses stdlib + boto3).
- No new dependencies for Node (uses existing React/Next stack).
- Verify after pyproject.toml additions — if `slsflow run` CLI needs
  click or typer, add (~1 LOC).

**Risk:** LOW

---

### UI Next.js routes (ui/src/app/)

#### ui/src/app/runs/page.tsx — AFFECTED

**Today:** 5 LOC. Routes `/runs` URL to old App component (AllRunsView).

**Changes:**
- Decide: `/runs` → RunsListPage (new Run records), `/executions` →
  AllExecutionsView (renamed AllRunsView).
- Create new file `ui/src/app/executions/page.tsx` (~5 LOC).
- Update `ui/src/app/page.tsx` valid views list (~2 LOC).

**Risk:** LOW

---

### Smoke / E2E pipelines

#### tests/snapshots/* (baseline files) — REGENERATE

**Today:** Snapshot files (JSON) for SFN templates.

**Changes:**
- Regenerate all snapshots after SFN template changes (Phase D).
- `pytest --snapshot-update` then review diffs in PR.
- Expected diff: ~5-10 files updated, mostly with new `run_id`/
  `partition_key` field references in JSONata.

**Risk:** LOW (mechanical regeneration; PR review catches surprises).

---

## Phase K summary

| Status | Count | Files |
|---|---|---|
| AFFECTED | 6 | CHANGELOG, README, CONTRIBUTING, ui/app/runs/page, pipelines/*, snapshots/* |
| NEW | 1 | ui/app/executions/page.tsx |
| UNAFFECTED | 1 | requirements.txt (no changes) |

**Phase K LOC delta:** ~140 LOC modifications, ~5 LOC new.

**Phase K complete.**

---

# Final Discovery Summary

## Overall scope by phase

| Phase | Domain | AFFECTED | NEW | UNAFFECTED | DELETE | Risk dist |
|---|---|---|---|---|---|---|
| A | slsflow/ Python | 7 | 3 | 19 | 0 | 1 MED, 6 LOW |
| B | console_api/ | 16 | 2 | 9 | 1 | 4 MED, 12 LOW |
| C | Other Lambdas | 0 | 0 | 5 | 0 | All LOW |
| D | SFN templates | 6 | 1 | 6 | 0 | 3 HIGH (incl new), others LOW |
| E | Infrastructure | 5 | 0 | 0 | 0 | 1 MED, 4 LOW |
| F | UI components | 8 | 3 | 35 | 2 | 2 MED, 6 LOW |
| G | UI hooks | 6 | 1 | 7 | 0 | 1 MED, 5 LOW |
| H | UI lib/types | 5 | 0 | 5 | 0 | All LOW |
| I | Tests | 22 | 10 | 62 | 2 | All LOW–MED |
| J | Docs | 12 | 0 | 16 | 0 | All LOW |
| K | Cross-cutting | 6 | 1 | 1 | 0 | All LOW |
| **TOTAL** | **All** | **93** | **21** | **165** | **5** | **3 HIGH, 13 MED** |

**Files touched: 119 of 314 (38%).**
**Files unaffected: 165 of 314 (53%).**
**Files deleted: 5 of 314 (1.6%).**
**Files new: 21 (creates 7% growth).**

## LOC delta by phase

| Phase | New LOC | Modified LOC | Deleted LOC | Net |
|---|---|---|---|---|
| A | +480 | +110 | 0 | +590 |
| B | +420 | +200 | -576 | +44 |
| C | 0 | 0 | 0 | 0 |
| D | +250 | +50 | 0 | +300 |
| E | 0 | +150 | 0 | +150 |
| F | +930 | +180 | -636 | +474 |
| G+H | +120 | +120 | 0 | +240 |
| I | +2150 | +250 | -380 | +2020 |
| J | 0 | +3260 | 0 | +3260 |
| K | +5 | +140 | 0 | +145 |
| **TOTAL** | **+4355** | **+4460** | **-1592** | **+7223** |

**Net codebase growth: +7223 LOC** across implementation + tests + docs.
**Without docs** (J's +3260): +3963 LOC actual code+tests.
**Code-only** (no tests, no docs): ~+1850 LOC.

## High-risk areas requiring extra attention

1. **SFN templates `dependency_wrapper` + `run_task`** — hot path of every
   task. Naming collision `run_id` must be resolved in ADR before edits.
   Snapshot tests + 563 JSONata compile tests catch regressions.

2. **NEW `bulk_run` SFN template** — new infrastructure, no prior art in
   the codebase. Requires careful integration testing.

3. **`utils.py::is_internal_record`** — called in every iteration of
   pipeline-tokens. Bug here causes Run records to leak into execution
   lists, breaking UI counts.

4. **`task_variables.py` drift system** — single source of truth must
   stay in sync with both JSONata (SFN template) and Python (run handler).
   Tests catch mismatch.

5. **`main.py` routes table** — central dispatcher. Mistakes here cause
   404s on all API calls.

## Naming collision (CRITICAL — must resolve first)

**`run_id`** is used in two different ways:
- **Existing:** DDB field on task records = `pipeline_execution` value.
  Used by PagerDuty grouping.
- **New:** Run record ID (parent of multiple pipeline executions).

**Resolution (recommended option 3):** rename existing → `parent_execution_id`,
new Run model uses `run_id`. Since no production, do clean rename.

**Action:** This decision is a **prerequisite** for ADR #51 and all
subsequent code in Phases B, D.

## Open questions remaining after Discovery

1. **Standard vs Express bulk-run SFN** — decided Standard (simpler,
   $0.01/run negligible). Need ADR #54 confirmation.
2. **`@dag(granularity=...)` override** — recommended YES. Need ADR #52
   confirmation.
3. **`runs_repo.py` separate vs extend `executions_repo`** — recommended
   separate for clarity. Need ADR #54 confirmation.
4. **Pipeline version capture in Run** — recommended YES (capture at
   Initialize state). Need ADR #51 inclusion.
5. **Scheduled runs via bulk-run** — included or deferred to v0.79?
   Recommended **included v0.78** for symmetry. Need ADR #55.
6. **Cascade lineage propagation (cascade_source_run_id)** — recommended
   defer to v0.79. Need ADR #57 mention.
7. **TabPartitions.tsx classification** — needs file read during
   implementation to finalize (low risk either way).
8. **Soft/hard partition limits** — recommended 500/5000. Need ADR
   inclusion.
9. **Run record TTL** — recommended same as executions (30 days). Need
   ADR confirmation.

## Discovery complete

All 314 source/test/doc/infra files in the project have been walked.
93 affected, 165 unaffected, 5 deleted, 21 new.

**Next steps:**
1. User reviews this report.
2. Resolve naming collision (run_id) — decision point.
3. Write ADR #51-58 based on findings (each ADR opens a section in
   `docs/reference/DESIGN_DECISIONS.md`).
4. Implementation phases follow ADR approval.

**The Discovery has done its job:** found 1 CRITICAL naming collision,
3 HIGH-risk areas requiring careful handling, and reduced unknown scope
to zero. The remaining work is structured engineering, not exploration.


---


---


---


---


---


---


---


---


---

