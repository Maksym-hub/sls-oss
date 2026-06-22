# slsflow Backlog

## ✅ Completed Features

### Core DSL
- [x] Airflow-familiar DSL syntax (@task, >>, DAG)
- [x] Task types: SFN, Lambda, Glue, ECS, Athena, EMR, Batch
- [x] Trigger rules (all_success, one_failed, all_done, etc.)
- [x] Dependencies (bitshift operators, function calls)
- [x] Variables (pipeline-level, auto-generated)
- [x] **Alerts configuration (required parameter)**
- [x] slsflow-deploy (CloudFormation-based deployment)

### Task Management
- [x] Task state tracking (DynamoDB)
- [x] Dependency-based execution
- [x] Wait callbacks (waitForTaskToken)
- [x] Timeout handling
- [x] Retry logic
- [x] wait_before delays
- [x] Skip task (manual)
- [x] Fail task (manual)
- [x] Stop task (force)
- [x] Restart task
- [x] Task events history

### Pipeline Operations
- [x] Run pipeline (manual)
- [x] Backfill (date range)
- [x] Backfill with task selection
- [x] Backfill with asset selection
- [x] Auto variables for backfill
- [x] Pause/Resume pipeline
- [x] Stop pipeline

### Alerts & Notifications
- [x] Slack notifications (interactive)
- [x] **PagerDuty integration**
- [x] **Alerts per-DAG configuration**
- [x] Failure events (EventBridge)

### Asset-Based Orchestration
- [x] Asset definition (name, uri, group)
- [x] **Asset schema declaration (column name/type/description)**
- [x] **Asset owner, glue_table, glue_catalog fields**
- [x] **Asset Detail Page (6-tab view with sidebar)**
- [x] Asset outlets (producers)
- [x] Asset inlets (consumers)
- [x] Asset-triggered DAGs
- [x] AND logic (all assets required)
- [x] OR logic (any asset triggers)
- [x] Asset events history
- [x] Asset queue management
- [x] Manual asset trigger

### Web Console
- [x] Pipeline list
- [x] Pipeline status
- [x] **DAG visualization (React Flow)**
- [x] **Gantt chart**
- [x] **Calendar view**
- [x] **Asset lineage graph**
- [x] Task detail modal
- [x] Task events timeline
- [x] Task actions (skip, fail, stop, restart)
- [x] **Backfill modal**
- [x] **Date picker**
- [x] Execution selector
- [x] **Auto-refresh (polling)**
- [x] Help modal (icons, API)
- [x] Filtering (status, pipeline, date)
- [x] **Notifications panel**

### Technical
- [x] 7 DynamoDB tables
- [x] 6 Lambda functions
- [x] 9 Step Function helpers
- [x] EventBridge rules
- [x] CloudFront + S3 (UI hosting)
- [x] API Gateway (HTTP)
- [x] **Code splitting (UI bundle)**
- [x] **CloudWatch Alarms (7 alarms)**
- [x] **CloudWatch Dashboard**
- [x] Smoke tests (27 tests)
- [x] Integration tests (9 tests)
- [x] **Configurable orchestration_timeout** (per-task dependency wait time)
- [x] **Backfill with max_parallel** (staggered start with throttle retry)
- [x] **Route table** (49 routes, replaces if/elif chain)
- [x] **DDB Catch clauses** on all run_task states
- [x] **Bounded DDB scans** (all scan_all() calls have limits)
- [x] **Race condition protection** (restart_task, ConditionExpression)
- [x] **CI pipeline** (trigger rules, pipeline imports, Lambda tests, constants sync)
- [x] **DAG snapshot per execution** (survives redeploys, TTL 120 days)
- [x] Pipeline registration lifecycle (register on deploy, deregister on destroy)
- [x] **Idempotent manual actions** (claim-before-side-effects, named executions)
- [x] **Asset.consecutive()** (cross-pipeline date dependencies)

---

## 🚧 In Progress / Planned

### High Priority
- [ ] E2E tests
- [ ] Production testing (backfill)
- [ ] Alert testing (PagerDuty integration)
- [x] ~~Remove auto_registration.tf~~ (replaced by `register_pipeline` SFN, ADR #24) — done v69.1

### Medium Priority
- [ ] Orphaned asset subscriptions cleanup (lazy validation in trigger path)
- [ ] Browser notifications (on failure)
- [ ] Keyboard shortcuts
- [ ] Execution diff (compare runs)
- [ ] Cost tracking per pipeline
- [ ] SLA indicators
- [ ] Task logs viewer
- [ ] UI filter for register_only executions

### Low Priority
- [ ] Multi-region support
- [ ] Role-based access control
- [ ] Audit logging
- [x] ~~Pipeline versioning~~ → DAG snapshot per execution (v69)
- [ ] A/B testing support
- [x] ~~Legacy providers~~ — removed

### Code Quality Follow-ups (from v0.77.2 audit)
- [ ] **`useUrlSync.ts` refs updated in render body** — `react-hooks/refs`
      lint warning; real React 19 concurrent-rendering anti-pattern.
      Needs to move ref assignment into `useEffect`. Add test for back/
      forward URL sync regression coverage before changing.
- [x] ~~**Extract `_shared/logger.py`**~~ — done v0.79.4 (ADR #76).
      All 4 helper Lambdas now use `from logger import log` with
      structured JSON output; canonical source in `_shared/logger.py`,
      synced via `make sync-loggers`.
- [ ] **`ruff format` on 82 currently-unformatted files** — style-only,
      no semantic changes, but creates large git-blame churn. Land as
      its own dedicated commit (no other changes in the same patch).
- [ ] **mypy as blocking CI gate** — currently `continue-on-error: true`.
      Build a baseline of accepted errors first (`mypy --show-error-codes
      | tee mypy_baseline.txt`), then make blocking with diff-only check.
- [ ] **`generators.py` split** — 1719 lines, 38 functions. Natural
      submodules: `generators/asl_validator.py`, `generators/states/*.py`
      (per-step generators), `generators/wrapper.py`, `generators/mermaid.py`,
      `generators/eventbridge.py`, `generators/assets.py`. Refactor, not fix
      — do when next feature lands that touches it.
- [ ] **Large UI component splits** — `AssetMatrixView.tsx` (825 lines),
      `AssetLineageFlow.tsx` (798), `AssetsView.tsx` (775). Extract
      `useMatrixFilters`, `useMatrixData` etc. as hooks; pull subviews
      into siblings. Same "refactor when touched" rule.
- [ ] **Silent excepts in `slsflow/_ee/ai/*` (6 sites) and `slsflow/config.py:81`**
      — SDK-side, lower priority than the 4 Lambda sites fixed in v0.77.2.
      Pattern: `except Exception: return <default>` without logging.
- [ ] **Fully fold `_shared`/`evaluate_deps` status classes into generated**
      (v0.80.0, ADR #83 — console_api part DONE). `console_api/constants.py`
      now re-exports all status classes from the generated module (no manual
      duplicates); the divergent members that blocked it
      (`TriggerRule.DEFAULT`/`EARLY_TRIGGER`/`WAIT_ALL`,
      `PipelineStatus.PAUSED`/`ABORTED`) were dead and removed. What remains:
      `_shared/constants.py` (copied to evaluate_deps) still defines
      TaskStatus/TriggerRule/AssetOperator manually, on purpose — it has an
      ImportError fallback so the file works standalone in unit tests, and
      re-exporting the generated classes would couple it hard to
      `constants_generated` at import. For now that copy is *guarded* against
      drift by `check_shared_constants` (`make sync-constants`), so it cannot
      silently diverge. Folding it fully into generated requires resolving
      that standalone-resilience tension (e.g. ship constants_generated in
      every Lambda artifact unconditionally, or accept the guarded copy as
      the permanent design). Deliberate design decision, not urgent.
      **Decision recorded in ADR #84:** guarded copy now, PyPI (Option D) as
      target end-state, Layer (Option C) as fallback — done as one packaging
      migration, not piecemeal for constants.

- [ ] **`npm audit` cleanup — dev-toolchain + amplify transitive** (from v0.90.0).
      Bumping Next `16.1 → 16.2` (16.2.9) cleared the high-severity Next
      advisories, but `npm audit` still reports findings, all outside Next:
      - **Dev/test toolchain (not shipped to prod):** `vitest` 2.x (critical via
        `@vitest/mocker`), `vite`, `vite-node`, `esbuild`, `@babel/core`,
        `brace-expansion`, `js-yaml`, build-time `postcss`. Fix = `vitest`
        2.x → 3.x — a **major** bump with breaking config/API changes. Land as
        its own change with the full `npx vitest run` suite green, never blind.
      - **aws-amplify transitive (runtime):** `fast-xml-builder`, `form-data`,
        `js-cookie`, `ws`. Fix = bump `aws-amplify` (6.x line), which can ripple
        the Cognito auth path — validate sign-in / sign-out end-to-end after.
      Both are separate, test-validated bumps. Production exposure is low today
      (static export, no Next server; amplify limited to Cognito auth), so this
      is hardening / clean-clone-audit optics, not an active prod risk.

- [ ] **Quality pass — deferred items (from v0.91.0 audit).** The v0.91.0 pass
      fixed the highest-value issues (switch_provider contract, config
      silent-swallow, provider typing, backfill test boundary). The wider,
      systemic debt was deliberately left out of that bounded pass:
      - **SDK type-checking as a blocking gate.** mypy is ~404 errors after
        v0.91.0 and still `continue-on-error`. Land file-by-file, then flip the
        gate — not one mega-change. Biggest remaining lever for SDK quality.
      - **Remaining internal-mock test sites (~56).** `test_backfill_upstream.py`
        now mocks at the `executions_repo` boundary and lets the real helpers run
        (Principles 13/14); apply the same pattern to the other sites that stub
        private `_helpers`. Console-API tests use MagicMock (no moto) — keep that
        convention; mock the repo/boto3 boundary, not the internal helper.
      - **`generators.py` split / `validate_asl` dispatch** — already tracked
        ("refactor when touched"). `render_dag_ascii` F(42), `validate_asl` E(40)
        are the worst; a per-state-type dispatch table makes each rule unit-
        testable. Needs a feature trigger + full output-equivalence snapshot.
      - **SDK `print` → `logging` (552 sites).** The SDK prints instead of using
        `logging`, so consumers can't control output. Separate architectural
        decision + ADR before any migration.

### Backfill Redesign — DONE in v0.78.0

The "three separate code paths, six entry points" mess described below was
unified in **v0.78.0 (May 2026)**. See ADRs #51–#58 in
[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) and the v0.78.0 entry in
[CHANGELOG.md](../../CHANGELOG.md) for the implementation summary.

What we shipped:

- **One endpoint**: `POST /api/backfill` with target/partitions/options/cascade
  shape (replaces `pipeline-backfill`, `pipeline-force-trigger`,
  `assets/backfill`).
- **One orchestrator**: `slsflow-bulk-backfill` Standard SFN with
  `Map(max_concurrency=max_parallel)` (replaces in-Lambda iteration).
- **One persisted record**: Backfill row in `pipeline-tokens` with sentinel
  pipeline_name + `record_type='backfill'` discriminator, sparse GSI
  `backfill-id-index` for child execution lookup.
- **Backfill record fields**: `backfill_id`, `target_pipeline`,
  `partition_keys`, `total_partitions`, `completed_partitions`,
  `failed_partitions`, `skipped_partitions`, `cascade`, `status`,
  `pipeline_dag_hash`, `parent_backfill_id` (retry chain), `started_by`,
  `started_at`, `finished_at`, `estimated_sfn_cost_usd`.
- **Six statuses** (ADR #56): `pending`, `running`, `completed`, `failed`,
  `partial`, `canceled`.
- **Cooperative cancel** (ADR #54): `POST /api/backfills/cancel?id=...`
  marks DDB; Map checks status at each iteration; in-flight children
  continue.
- **Retry-failed** (ADR #54): `POST /api/backfills/retry-failed?id=...`
  forks new Backfill with only failed partition keys, linked via
  `parent_backfill_id`.
- **Granularity-aware partition expansion** (ADRs #52, #58):
  `slsflow.partitions.PartitionRange` with `expand()` / `from_keys()` /
  `translate_to()` / `skip_completed()` / `cost_estimate()` and 5000-
  partition hard limit. Runtime cron cadence inference defaults ambiguous
  schedules to `daily` with warning.
- **Cascade semantics** (ADR #57): asset-target only;
  `auto` / `all` / `none` for downstream consumer triggering.
- **CLI** (Phase 6): `slsflow backfill pipeline/asset NAME ...`,
  `slsflow backfills list/show/cancel/retry-failed`.
- **UI** (Phase 5): universal seed-driven `BackfillModal`,
  `/backfills/` list page, `/backfills/{id}/` detail page with partition
  heatmap and cancel/retry.

#### Future enhancements (not blocking v0.78)

- [ ] **Multi-cell selection in Matrix** — currently each click opens a
      separate backfill modal. Allow lasso/range-select across cells,
      single backfill modal pre-filled with the union range.
- [ ] **`target.type='batch'`** — currently returns 501. Implement when
      a user actually needs multi-asset/multi-pipeline atomic backfills.
- [x] **Real `skip_completed` pre-flight** — DONE. `_scan_completed_partitions`
      performs the real per-task DDB check at preview/start time (not a stub);
      preview shows an accurate skipped count.
- [x] **`partition_start` reading from asset metadata** — DONE.
      `_resolve_target` / `_find_producers_for_asset` read the declared
      `Asset(partition_start=...)` from the outlet metadata for clipping.

#### Correctness audit follow-ups (from v0.80.0 backfill review, ADR #83)

- [x] **Child execution name length** — DONE (v0.80.0). `start_backfill`
      now rejects with `child_name_too_long` (422) when
      `{pipeline}-{partition}-bf-{hex8}` would exceed SFN's 80-char limit,
      instead of every partition silently failing inside the Map.
- [x] **Hourly partition keys in child name** — NOT A BUG. The hourly
      format `YYYY-MM-DDTHH` (e.g. `2024-01-15T14`) contains only chars
      legal in SFN execution names; verified. The only edge was length,
      covered by the item above.
- [ ] **`.sync:2` child Retry may not produce a fresh attempt** — the
      `StartChildSFN` state has a `Retry` on `States.TaskFailed`
      (MaxAttempts 3). On retry it calls `StartExecution.sync:2` again with
      the **same Name + Input** (Name is derived from constant input). AWS
      `StartExecution` is idempotent on name+input within the dedup window,
      so the retry likely re-attaches to the same already-failed execution
      rather than launching a new one — making the child-level Retry
      ineffective (it just re-observes the failure after backoff).
      **Impact:** low — partitions still end correctly failed, and
      backfill-level `retry-failed` is the real re-run path; the only cost
      is wasted retry backoff. **Open question:** confirm the exact
      `.sync:2` + idempotent-StartExecution behavior on a live stack.
      **Candidate fixes (require a deploy smoke test — do NOT ship blind,
      this edits orchestrator JSONata which has no CI-side syntax
      validation):**
        1. Make each attempt unique: append `$states.context.State.RetryCount`
           to the child execution Name so retries launch fresh executions.
        2. Remove the `Retry` block entirely and rely solely on
           backfill-level `retry-failed`.
      Decision deferred until the behavior is confirmed on a real stack;
      neither edit is safe to make without end-to-end SFN validation.

#### Planned: v0.79.7 — Per-partition CANCEL/SKIP (Approach A)

Closes ADR #74's deferred work: per-partition retry (✅ done v0.79.2)
needs companion CANCEL/SKIP for the heatmap to feel complete.

**Approach A:** SKIP always works; CANCEL only for not-yet-started
partitions (no mid-execution `stop_execution`). Chosen over B (full
CANCEL with stop_execution) because of race-condition risk and over C
(SKIP only) because tail-partition CANCEL covers a real use case
("changed my mind on range, still iterating").

**User value:**
- Backfill stuck on corrupt partition → skip 1-2 dates, others continue (no abort + re-run).
- Mid-range parameter change → cancel tail partitions still in queue.
- Granular control → less "all-or-nothing" frustration.

**Out of scope (deliberate):**
- Stopping already-running SFN partition executions. Race-condition
  prone; user can still abort whole backfill if they really need to
  stop a running partition.

**Scope (~4-5 hours):**

1. **DDB schema** — add `partition_states` Map<date_str, {skipped?,
   cancelled?, action_at, reason}> to backfill record. Lazy-create
   on first action (no migration; missing field = no actions).

2. **SFN template `bulk_backfill/sfn.tpl.json`** — inside Map iteration,
   before Run_Task, add Choice state checking
   `$states.input.backfill.partition_states[$partition_key].cancelled`
   or `.skipped`. If true → write `status: cancelled` or `skipped` to
   pipeline-tokens, skip Run_Task, continue iteration. State-transition
   cost: +1 Choice per partition (~$0.000025 per partition; negligible).
   Re-run `make check-sfn-templates` after change.

3. **Backend endpoints:**
   - `POST /api/backfills/{id}/skip-partitions` body
     `{partition_keys: ["2026-01-15", ...], reason?: str}`. Updates
     `partition_states[key].skipped = true` in single DDB
     UpdateExpression with multiple SET clauses. Validation: keys
     must be in backfill range; idempotent (re-skip = no-op).
   - `POST /api/backfills/{id}/cancel-partitions` — same shape, sets
     `cancelled = true`. Does NOT call `stop_execution`; relies on
     SFN Choice state to see the flag on next iteration.

4. **UI** — heatmap cells gain two new buttons on hover (next to ↻ retry
   from v0.79.2): ✗ cancel (only on `waiting`/`pending`/`running`) and
   ⊘ skip (any non-terminal). Same mutation pattern as retry: confirm
   dialog → `useSkipPartitionsMutation` / `useCancelPartitionsMutation`
   → optimistic state toast → invalidate detail query.

5. **Tests:**
   - Backend: route validation (range bounds, idempotency, partition
     not in backfill, key not found), DDB update assertion (single
     UpdateExpression), partition-state respected on next bulk-backfill
     iteration (integration-level mock).
   - UI: mutation hook shape, button visibility per cell state, confirm
     dialog behavior, toast text.
   - SFN drift: template change passes `check-sfn-templates`.

6. **ADR #79** — Approach A rationale, race-condition acceptance
   (already-running partitions not stoppable), why not B/C, partition_states
   schema choice (lazy map vs. eager array), cost analysis (+1 state
   transition per partition).

**Edge cases to handle:**
- Cancel + skip on same partition → skip wins (last-write).
- Skip on already-running partition → cancel current execution? No —
  partition_states only checked at iteration start; running task
  completes normally. UI must indicate this ("running partitions complete
  before skip takes effect").
- Backfill in `paused` state when skip arrives → updates DDB; takes
  effect when backfill resumes.

**Estimate breakdown:**
- SFN template + drift check pass: ~1.5h (highest-risk piece, test on
  staging backfill before deploy).
- 2 backend endpoints + tests: ~1h.
- UI buttons + 2 mutation hooks + tests: ~1.5h.
- ADR + integration verification: ~1h.

**Why this is being deferred:**
- Tool budget exhausted in the current alignment cycle (v0.78.13–v0.79.6).
- SFN template changes carry deploy-time risk; should be tested
  carefully on staging before production rollout.
- Mike + Claude haven't sat down to walk through edge cases together
  with whiteboard-level scrutiny. Worth the 30-minute design pass.

**Deferred to a separate session.** All other ADR #74 work
(per-partition retry) is shipped in v0.79.2.

#### Intentional differentiators (kept)

These are not bugs, they are features competitors don't have:

- **Task-level backfill** (`tasks=[...]` subset) — neither Airflow nor
  Dagster expose this as cleanly. Kept.
- **`incremental` mode reads stored statuses** — pragmatic, useful. Kept.

#### Decided no (out of scope, do not implement)

- Multi-dimensional partitions (region × date) — adds enormous complexity
  for ~3 users who'd ever need it. Stay 1-D.
- Dynamic partitions (sensor-generated keys at runtime) — Dagster has,
  we don't need yet. Revisit if data-team requests.
- Single-run backfills (one execution materializes all partitions) —
  requires task author to write code aware of N partitions at once;
  burden too high for too little gain.

---

## 🔧 Tech Debt — Lambda packaging of slsflow SDK
**Decision context: see ADR #84** (SDK / shared-constants delivery — guarded
copy now, PyPI as target end-state, Layer as fallback; done as one move).


**Current state (v0.78.0):** `sam/lambdas/console_api/slsflow` is a
**committed symlink** to the repo-root `slsflow/` package. SAM's Python
builder follows the symlink and packages the SDK as a subdirectory of
the Lambda artifact. Zero setup; standard `sam build && sam deploy`
just works.

**Why this is debt:** symlink is a workaround, not an architectural
decision. The Lambda's real dependency on `slsflow` is hidden in the
file system, not declared in `requirements.txt`. Cross-platform
fragility (Windows requires admin + git config). Not how industry
projects (Dagster, Airflow, dbt) declare shared internal libraries.

### Migration trigger

Replace the symlink when **any one** of these happens:
- slsflow gets published to public PyPI (planned for OSS launch)
- slsflow gets published to private AWS CodeArtifact (intermediate option)
- A second Lambda needs to import from `slsflow.*` (current code only
  has console_api; once a second consumer appears, fix the pattern)
- A Windows contributor joins and hits the symlink permission issue

### Migration checklist — when slsflow goes to public PyPI

This is the **target end state**. Once slsflow is on PyPI:

1. **Verify the package builds**
   ```bash
   python -m build      # creates dist/slsflow-X.Y.Z-py3-none-any.whl
   twine check dist/*   # PyPI metadata sanity
   ```

2. **Publish to PyPI (manual first time, then GitHub Actions)**
   ```bash
   twine upload dist/*  # one-time; require PyPI 2FA
   ```
   Verify: `pip install slsflow==X.Y.Z` works in a fresh venv.

3. **Add `slsflow` to Lambda `requirements.txt`**
   Create `sam/lambdas/console_api/requirements.txt`:
   ```
   slsflow==X.Y.Z
   ```
   Pin the exact version — Lambda artifacts are immutable, surprise
   upgrades break things.

4. **Remove the symlink**
   ```bash
   rm sam/lambdas/console_api/slsflow
   git add sam/lambdas/console_api/slsflow  # records deletion
   ```

5. **Remove the regression test that enforces the symlink**
   In `tests/sdk/test_reviewer_regressions_v078.py`, delete:
   - `test_lambda_has_slsflow_symlink`
   - `test_lambda_local_makefile_not_reintroduced` (keep as guard)
   - `test_template_has_no_buildmethod_makefile_for_console_api` (keep)

6. **Add a new regression test for the PyPI dependency**
   ```python
   def test_console_api_has_slsflow_in_requirements():
       req = REPO_ROOT / "sam/lambdas/console_api/requirements.txt"
       assert req.exists()
       assert re.search(r"^slsflow==\d", req.read_text(), re.M)
   ```

7. **Verify `sam build` works without symlink**
   ```bash
   cd sam && sam build
   # SAM PythonBuilder runs `pip install -r requirements.txt -t artifact_dir`
   # Lambda artifact now contains slsflow/ as pip-installed dependency
   ```

8. **Update CHANGELOG.md and CLAUDE.md**
   - CHANGELOG: "Replaced Lambda packaging symlink with PyPI dependency."
   - CLAUDE.md: remove the "Lambda packaging" section about symlinks.

9. **Set up GitHub Actions to publish on tag**
   ```yaml
   # .github/workflows/publish.yml
   on:
     push:
       tags: ['v*']
   jobs:
     publish:
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
         - run: pip install build twine
         - run: python -m build
         - run: twine upload dist/*
           env:
             TWINE_USERNAME: __token__
             TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
   ```
   Use **PyPI trusted publishers** (OIDC) instead of long-lived tokens
   when set up.

10. **Update CI to install from PyPI instead of editable**
    In `.github/workflows/ci.yml`, the `lambdas` job currently has:
    ```yaml
    pip install -e .  # editable install from local source
    ```
    Change to (after PyPI publish):
    ```yaml
    pip install slsflow==X.Y.Z  # same version as Lambda requirements
    ```
    This makes CI exercise the same package the Lambda will get.

### Alternative migration: AWS CodeArtifact (private PyPI)

Same checklist as above, but step 2 publishes to CodeArtifact instead:
```bash
aws codeartifact login --tool twine --domain slsflow --repository releases
twine upload --repository codeartifact dist/*
```
And step 6's `requirements.txt` resolution requires `aws codeartifact
login --tool pip` (12-hour token). Useful **only if** OSS launch is
deferred but you want to be off the symlink.

### Alternative migration: Lambda Layer

Build slsflow as a separate Lambda Layer, attach to console_api in
template.yaml. AWS-native, but separate deploy cycle for the layer and
extra CloudFormation resource. Not recommended unless multiple Lambdas
need slsflow and PyPI publish is far off.

### What absolutely MUST NOT come back

- **Lambda-local `sam/lambdas/console_api/Makefile`** with
  `BuildMethod: makefile` and `cp ../../../slsflow`. Failed live smoke
  2026-05-22 because SAM CustomMakeBuilder runs `make` from a scratch
  directory; the relative path doesn't reach the repo root.
- **Top-level `make sam-build`** target that vendor-copies slsflow
  before `sam build`. Introduces a wrapper command users forget about
  and run plain `sam build` anyway.

Regression tests in `tests/sdk/test_reviewer_regressions_v078.py`
prevent both patterns from being reintroduced silently.

---

## 📊 Stats

| Component | Lines of Code |
|-----------|---------------|
| Python DSL (slsflow) | ~13,500 |
| SFN Templates (JSON) | ~4,300 |
| Lambda Handlers | ~9,400 |
| UI React | ~14,600 |
| UI CSS | ~10,600 |
| Tests | ~3,800 |
| Docs | ~9,000 |
| **Total** | **~69,600** |

---

## 🏗️ Architecture Components

### Step Function State Machines (12)
1. `sf_dependency_wrapper` - Main wrapper (deps → run → notify)
2. `sf_registration_helper` - Register task + subscriptions
3. `sf_run_task_helper` - Execute tasks (Lambda/Glue/ECS/Athena/EMR/Batch)
4. `sf_failure_handler` - Handle failures, call alerters
5. `sf_slack_interactive` - Slack interactive notifications (Express)
6. `sf_pagerduty_alerter` - PagerDuty alert creation (Express)
7. `sf_pagerduty_resolver` - PagerDuty alert resolution (Express)
8. `sf_restart_task_helper` - Restart terminal tasks (Express)
9. `sf_restart_wrapper` - Restart wrapper executions (Express)
10. `sf_notify_dependents_helper` - Notify downstream tasks (Express)
11. `sf_notify_asset_consumers_helper` - Notify asset subscribers (Express)
12. `sf_pause_waiter` - Handle pause/resume callbacks

### Lambdas (5)
1. `console_api` - REST API for UI (58 routes)
2. `evaluate_deps` - Evaluate trigger rules
3. `query_subscriptions` - Query dependency subscriptions
4. `check_assets` - Check asset freshness for pull-based triggers
5. `notify_asset_subscribers` - Notify waiting tasks of asset readiness

Shared: `_shared/` - Constants, utilities used by multiple lambdas

**Removed in v55:**
- `asset_trigger` - Replaced by `notify_asset_consumers` SFN helper
- `notify_dependents` - Replaced by `notify_dependents_helper` SFN

**Removed in v69.3:**
- `asset_watcher` - Never activated; external assets use `POST /api/asset/{name}/trigger`

### DynamoDB Tables (7)
1. `pipeline_tokens` - Task state + pause tokens
2. `dependency_subscriptions` - Dependency tracking (who waits for whom)
3. `pipeline_registry` - Pipeline metadata (ARNs, DAG structure)
4. `asset_events` - Asset materialization history
5. `queued_asset_events` - AND trigger queue (partial fulfillment)
6. `task_events` - Task event timeline
7. `asset_subscriptions` - Asset → pipeline subscriptions

### UI Components (31 components, 35 test files, 536+ tests)

**Views:**
1. `PipelineDetail` — Pipeline detail (DAG/Gantt/Calendar tabs, lazy-loaded modals)
2. `DAGGraphFlow` — ReactFlow + dagre graph visualization
3. `GanttChart` — Execution timeline bars
4. `CalendarView` — Monthly execution grid
5. `AssetLineageFlow` — Asset dependency graph with prefix filtering
6. `AssetsView` — Asset management (list + lineage + events)
7. `AllTasksView` — Cross-pipeline task table with filters
8. `AllRunsView` — Cross-pipeline execution table with filters + `backfill_id` column
9. `BackfillsListPage` — Recent backfills with status filters (v0.78+)
10. `BackfillDetailPage` — Single backfill with partition heatmap + cancel/retry (v0.78+)

**Modals:**
11. `TaskDetailModal/` — Split into 6 sub-components (Details/Dependencies/Events tabs);
    `Backfill This Task` button opens universal BackfillModal with task seed
12. `BackfillModal` — Universal seed-driven modal (v0.78+); opens for pipeline/asset/
    matrix-cell/task-detail/asset-detail origins via `openBackfillModal({seed})`
13. `ActionModal` — Pipeline action confirmation with JSON params
14. `AssetTriggerModal` — Manual asset trigger
15. `AssetDetailModal` — Asset info + events + staleness (lightweight preview)
16. `AssetDetailPage` — Full asset detail view (6 tabs: Overview, Schema, Partitions, Events, Checks, Lineage)
17. `BaseModal` — Base modal (focus trap, ESC, overlay, ARIA)
18. `Modal` / `ConfirmModal` — Simple dialogs on BaseModal
19. `HelpModal` — Keyboard shortcuts + API reference
20. `CommandPalette` — ⌘K fuzzy search across pipelines + actions

**Shell:**
21. `App` — Root component (sidebar + main views), mounts universal `<BackfillModal>` globally
22. `Header` — Date picker, view mode, theme, live mode; 5 nav tabs incl. Backfills
21. `PipelinesSidebar` — Pipeline list with groups, search, sparklines
22. `Notifications` — Real-time notification panel
23. `LoginPage` / `AuthGate` / `UserMenu` — Cognito auth UI

**Shared:**
24. `Toast` — Toast notification system
25. `CountdownTimer` — wait_before countdown with progress bar
26. `SortableHeader` — Sortable table column header (keyboard + ARIA)
27. `Skeletons` — Loading skeletons for all views (10 variants)
28. `ErrorBoundary` — Error boundary with retry
29. `Providers` — App-wide providers wrapper
30. `ui/` — shadcn/ui primitives (button, input, select, dialog, badge, checkbox, tabs, etc.)

---

## 📝 Recent Changes

See [CHANGELOG.md](../../CHANGELOG.md) for full version history.

---

## Product backlog (roadmap ideas)

### Pro-tier features (commercial — not in OSS Community)

Per the tiered model (Community free / Pro paid / managed Cloud), the
following live behind a Pro-tier flag. They reuse the OSS Community
backfill infrastructure but layer paid capabilities on top.

#### Tiering philosophy

**Community gets power. Pro gets control, governance, scale.**

| Question user asks | Tier |
|---|---|
| "How does this work?" | Community |
| "What will this cost?" | Community (cost preview is transparency, not gated) |
| "Why did it fail?" | Community |
| "Who ran this?" | **Pro** (audit log) |
| "How do I limit this?" | **Pro** (cost limits, budgets) |
| "Notify the team" | **Pro** (Slack/Teams/Discord routing) |
| "Don't run in prod without approval" | **Pro** (approval workflows) |
| "Track cost by team for chargeback" | **Pro** (cost allocation) |
| "Multi-tenant with RBAC" | **Pro** |

**Anti-patterns — never gate behind Pro:**
- Engine features (backfill, retry, partition heatmap, cost *preview*)
- Transparency (what user sees about their own pipelines)
- Documentation, CLI, onboarding (must be friction-free)
- Quality (same SLAs across tiers — no "Pro gets faster Lambda")

The litmus test: if gating a feature would make Community users feel
*spied on* or *kept in the dark about their own data* — it stays
Community. Pro is for **operational scale + organizational concerns**.

---

#### Category 1 — Control (prevent expensive mistakes)

##### Pre-flight cost limit warning
- If `estimated_sfn_cost_usd > $threshold`, modal shows red warning before Start
- Configurable per-tenant via SSM (`/slsflow/{stage}/cost-limit-warning-usd`)
- UI: red banner + checkbox "I understand this will cost ~$X"
- Backend: include `cost_exceeds_threshold: true` in preview response
- ~10 LOC UI + 5 LOC backend + 1 SSM parameter
- **Pro gating**: only *enforced* when Pro flag true; OSS users see warning text but no checkbox enforcement

##### Cost reporting (full workflow — formerly Community estimate, now Pro)
*Deferred from v0.78.2 per ADR #62. Estimate alone proved misleading;
ship the full workflow or none.*

Three components, all Pro-only:

1. **Estimate at submit** — what we used to ship as `estimated_sfn_cost_usd`
   in Community. Methodology recoverable from git history at v0.78.1 tag
   (`slsflow/partitions.py::PartitionRange.cost_estimate()`).
2. **Actual reconciliation** — post-execution, read SFN cost from
   CloudWatch / Cost Explorer; populate `pipeline-cost-history` DDB
   table; show estimate vs actual delta in UI. Reconciles ~24h after
   run completes (Cost Explorer lag).
3. **Budgets** — `max_monthly_cost_usd` parameter per pipeline. Daily
   aggregation Lambda compares MTD spend; Slack alert at 80%, hard
   block (refuses new backfill API calls) at 100%.

UI: dedicated "Cost" tab in `BackfillDetailPage` and `PipelinePage`:
  - Estimate vs actual delta chart (line, monthly)
  - Burn rate this month vs budget (progress bar)
  - Per-task cost breakdown (table)

Why deferred: shipping (1) alone created UX confusion (users assumed
actual). Shipping (1) + (2) without (3) gives a passive report users
can't act on. Coherent Pro feature ships all three together.

Spec status: design ✓, implementation ⏸ until Pro tier launch.

##### Per-pipeline cost budget *(absorbed into "Cost reporting" above)*
- `$50/month cap per pipeline`, alert at 80%
- DDB table `cost-budgets` keyed by pipeline_name
- Daily aggregation job reads execution costs, compares to budget
- Slack alert at 80% / hard-block at 100% (configurable)
- ~100 LOC backend + UI configurator

##### Approval workflows
- "Backfill > $X requires manager approval"
- Slack/Teams interactive button → callback Lambda → flips approval flag in DDB
- SFN `WaitForApproval` Task with token, callback resumes
- Roles defined in cognito groups: approver / requester
- ~200 LOC + new SFN state + interactive Slack app config

##### Quota tuning per-tenant
- SSM-tunable `MAX_PARALLEL` cap (the override we reverted in v0.78 OSS)
- Same impl as removed from `routes/backfill.py::_get_max_parallel_cap`
- ~80 LOC + IAM permission + env var
- **This is the home for that feature** — premature in OSS, real in multi-tenant Pro

---

#### Category 2 — Notifications & Escalation

##### Slack notification on backfill complete/failed
- Hook into bulk-backfill SFN `UpdateFinalStatus` state
- Reuse `notify_asset_subscribers` Lambda + existing notification template
- Per-pipeline opt-in via DSL (`notify_on_backfill=True`) or Console UI
- Slack message format: pipeline name, partition count, success/fail/partial, link to backfill detail page
- ~40 LOC infra (1 SFN state + 1 Lambda payload extension)

##### Teams / Discord parity
- Same notification engine, different webhook templates
- Webhook URL configured per channel in Console
- ~20 LOC each (mostly message formatting)

##### Escalation chains
- "If on-call doesn't ack in 10 min → page next person"
- DDB table `escalation-policies` keyed by team
- EventBridge scheduled rule polls unacked alerts
- PagerDuty integration as paid add-on
- ~150 LOC + new Lambda

##### Custom routing
- Production failures → `#data-incidents`, dev → `#data-dev`
- Route by namespace, pipeline tag, severity
- UI config: rules table per team
- ~80 LOC backend + UI

##### Alert deduplication
- Don't spam 50 messages for one incident (50 failed partitions in one backfill = 1 Slack message, not 50)
- Grouping key: (pipeline, date, error_type, 5-min window)
- DDB `alert-fingerprints` with TTL
- ~60 LOC

---

#### Category 3 — Multi-tenancy & RBAC

##### Per-team namespaces
- `team-finance` sees only their pipelines, executions, assets
- Existing Namespace param in SAM template is the foundation
- New DDB GSI `team-pipeline-index` for filtered queries
- ~200 LOC across all list/detail endpoints

##### Role-based access control
- Roles: viewer / operator / admin
- viewer: read only; operator: start/cancel/retry; admin: deploy/config
- Stored in cognito user-pool group + custom claim
- Middleware checks role per endpoint
- ~150 LOC + cognito setup docs

##### SSO integration
- Okta, Azure AD, Google Workspace
- Cognito federation already supports SAML 2.0
- Config UI for SAML metadata upload
- ~50 LOC UI + ops docs (mostly customer-side setup)

##### Audit log
- Who started/cancelled/retried what backfill, when, with what params
- DDB table `audit-events` partitioned by date
- 90-day retention default, configurable
- Console: filterable timeline view
- ~120 LOC backend + UI

---

#### Category 4 — Operations at scale

##### Cost dashboard
- Historical cost view: this month, last 3 months, last year
- Per-pipeline / per-team breakdown
- Anomaly detection: "pipeline X cost 3× more this week than last"
- Reuse cost estimation logic from preview, aggregate over executions
- ~200 LOC backend + UI charts (recharts)

##### Cost allocation
- Tag executions with team / cost-center / project
- Export monthly CSV for chargeback to finance
- AWS Cost Explorer integration via resource tags
- ~80 LOC

##### SLA tracking
- Define expected completion time per pipeline ("by 09:00 UTC daily")
- Dashboard: % runs hitting SLA over time
- Trend alerts: SLA % dropped below threshold this week
- Reuse existing `expected_finish` field
- ~100 LOC

##### Premium support
- Email/Slack SLA (24h response Pro, 4h Cloud)
- Migration assistance from Airflow / Dagster
- Custom training sessions
- Operational reviews quarterly
- Not code — service offering

---

#### Pricing intuition (placeholder, far-future)

| Tier | Monthly | Includes |
|---|---|---|
| Community | $0 | Self-host, full engine, cost preview, all transparency features |
| Pro | $99-199/team | Notifications, RBAC, audit, budgets, approval workflows |
| Cloud | Custom | Managed deploy + infra + Premium support |

Dagster Cloud reference: $25/user/mo Starter, custom Pro/Enterprise. Astronomer Cloud: ~$5000/mo entry. SLSFlow infra is ~$31/mo, so Pro should price for the *value* of governance features, not as infra markup.

This pricing model is a far-horizon conversation. Current focus: Community traction. Pro features ship as engine maturity and user demand emerge.


### @task.python — inline Python executor
Auto-package a Python function as Lambda and deploy via `slsflow-deploy`. No manual Lambda needed.
```python
@task.python(requirements=["pandas", "pyarrow"])
def my_transform(date: str):
    import pandas as pd
    df = pd.read_parquet(f"s3://bucket/{date}.parquet")
    df.to_parquet(f"s3://bucket/out/{date}.parquet")
```
`slsflow-deploy` under the hood: zip fn + requirements → deploy Lambda → substitute ARN into SFN.

### DAG diff on deploy
Show what changed vs previous deploy before applying:
```
slsflow-deploy --diff
  acme-daily v47 → v48
  + validate_schema (after stage_listings)
  ~ build_product_details — timeout 3600 → 7200
  - old_cleanup (removed)
```
Store DAG JSON snapshot in S3/DynamoDB per deploy. UI: green/yellow/red nodes on DAG graph.

### Backfill cost controls
- Skip fully-done dates entirely (0 transitions) — currently in backlog #6
- Cost estimator in UI before starting backfill: "this will cost ~$0.45"
- Configurable transition budget: stop backfill if cost exceeds $X

### Cost tracking per pipeline
Dashboard showing SFN transitions, Lambda invocations, DynamoDB reads per pipeline per month. Identify expensive pipelines.

### SLA escalation chain
Not just alert if pipeline misses SLA — full escalation:
1. T+0: Slack alert
2. T+30min: PagerDuty
3. T+1hr: escalate to manager

### Dependency-aware backfill
When backfilling pipeline B that depends on pipeline A — automatically detect and suggest backfilling A first. Optionally auto-trigger upstream backfill in correct order.

### Execution budget per DAG
`max_monthly_cost_usd` parameter per DAG. If SFN transitions for the month exceed the budget — pause pipeline and alert.

---

## ⚠️ Known Operational Quirk — DynamoDB GSI rename via CloudFormation

**Trigger**: When renaming a GSI (e.g., `run-index` → `parent-execution-index`)
or changing its key schema, `sam deploy` fails with:

```
Cannot perform more than one GSI creation or deletion in a single update
```

This is an AWS DynamoDB hard limit, not a slsflow bug. CloudFormation
attempts the delete+create as a single UpdateTable API call, which AWS
refuses (max 1 GSI op per UpdateTable call).

### Fix when this happens

Two options:

**A. Manual pre-delete (fastest, single sam deploy)**

If the old GSI has no active readers (verify with grep), delete it
manually:

```bash
aws dynamodb update-table \
  --table-name <full-table-name> \
  --global-secondary-index-updates '[{"Delete":{"IndexName":"<old-name>"}}]' \
  --profile <profile>
# Wait ~1-2 min for IndexStatus to settle
sam deploy --profile <profile>
```

**B. Two-phase template (no manual AWS action)**

1. Temporarily add the old GSI back to template.yaml alongside the new one
2. `sam deploy` → succeeds (only creates new GSI; old unchanged)
3. Remove old GSI from template.yaml
4. `sam deploy` → succeeds (only deletes old GSI)

### Prevention

Avoid renaming GSIs when possible. If a rename is necessary, plan
deploys explicitly: add new GSI first (separate PR), wait for code
to migrate reads, then remove old GSI (separate PR).


## 🧹 Philosophy compliance gaps (v0.78.9 audit)

Surfaced by an audit measuring the Coding Philosophy section in
CLAUDE.md against current code. None are critical; do them
opportunistically when you're already in the file.

### Migrate bare `print()` to `slsflow.logger` in 5 Lambdas

`sam/lambdas/evaluate_deps/index.py`, `notify_asset_subscribers/index.py`,
`check_assets/...`, `query_subscriptions/...`, `ui_bootstrap/...` use
`print()` for warnings and errors. CloudWatch captures `stdout` so the
logs are visible, but they're plain strings — harder for alarms to
parse than the JSON lines `slsflow.logger` emits.

Pattern to apply:
```python
# Before
print(f"[notify_asset_subscribers] Warning: hit 10000 subscriber limit for {asset_name}")
# After
log.warn("notify_asset_subscribers", "Hit subscriber limit",
         asset_name=asset_name, limit=10000)
```

Cost: ~30-60 min per Lambda. Each file is small. Tests don't need
changes (logger output goes to stdout same as print).

### Docstring pass on `cmd_*` CLI handlers

`slsflow/cli.py` has ~80 `cmd_*` argparse handlers. The Coding
Philosophy CLI exception says docstrings can be omitted when the
function just unpacks args and delegates. In practice many of them
have a few lines of real logic worth documenting briefly. Audit pass
to add one-line docstrings where the function does anything beyond
pure delegation.

### Inline-style cleanup in `AssetLineageFlow.tsx`

3 ReactFlow `<Panel>` components use `style={{ margin: '10px' }}` or
similar literal values. Move to CSS class. Marginal value, low cost.

### Icon-only button ARIA audit

Most buttons have text content (acts as the label). Icon-only buttons
(e.g. close X, refresh icon) need `aria-label`. The audit didn't
catalog which buttons fall into the icon-only category — do a
targeted sweep, add `aria-label` where missing.
