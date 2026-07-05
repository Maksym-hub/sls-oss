# Editions — what is Free, Team, and Enterprise

Canonical map of which capability belongs to which edition. This is the
human-readable source of truth; when it and the code disagree, the code wins and
this file is the bug. Two enforcement mechanisms back it up (see *How the
boundary is enforced* below), so this page should never be the *only* record of a
tier decision — but it is the one place to read the whole picture at a glance.

Boundary principle (ADR #98, #110): **Free** is the full single-pipeline loop you
own end to end — author, deploy, run, observe, and intervene on a live run.
**Team** adds fleet-scale operations, external integrations, deep observability,
configuration mutation, and paid visualisations. **Enterprise** adds governance,
cost, and cross-account controls on top of Team.

## Free (open-core)

Everything here ships in the public build. The proprietary `ee/` trees are
physically absent from that build, so nothing below can depend on them.

| Area | What you get | Notes |
|------|--------------|-------|
| Authoring | Python DSL → ASL → CloudFormation; `polyris-init`, `polyris-deploy` | The whole pipeline SDK |
| Asset **engine** | Declare first-class assets, partitions, asset tables; produce & wait on assets | The asset *console* is Team (below) |
| Run | Trigger a pipeline run | |
| Read / observe | Pipelines list, DAG view, executions, tasks, task-config (GET), task events, decision-timeout (GET) | |
| Live-run intervention | Task **skip / fail / success / stop / restart** (and `retry`); execution **stop / pause / resume / extend** | ADR #110 — free so a free operator can unstick a run |
| Notifications | In-app / browser polling alerts on failure | ADR #103 — external integrations (Slack/PagerDuty) are Team |
| Web console | Pipelines + DAG view | Gantt & calendar view-modes are Team |

## Team (paid)

Ships in the paid build only (the `ee/team/` overlay). On a Team deployment every
capability here is granted.

| Capability key | Area | What it adds | Source |
|----------------|------|--------------|--------|
| `backfill` | Backfill | Date-range backfill, upstream smart-fill, downstream cascade, partition granularity | `ee/team/backfill.py` — *on the roadmap to open-core* |
| `assets.management` | Asset console | Matrix, lineage graph, drift | `ee/team/assets.py`, `matrix.py`, `drift.py` — *on the roadmap to open-core* (engine is free) |
| `slack.actions` | Alert integrations | Slack + PagerDuty config, interactive callbacks | `ee/team/alerts.py`, `slack.py` |
| `task.config` | Config mutation | Edit `task-config` (timeout / retries), set decision-timeout | `ee/team/tasks.py` (task-config PUT), `ee/team/settings.py` (decision-timeout PUT) |
| `pipeline.controls` | Pipeline lifecycle | Pipeline **pause / restart** (distinct from per-task/execution intervention, which is free) | `ee/team/pipelines_actions.py` |
| `pipeline.observability` | Observability | Per-pipeline logs & metrics | `ee/team/pipelines_info.py` |
| `api.tokens` | Access | Personal Access Tokens (PATs) | `ee/team/tokens.py` |
| *(no key)* | View-modes | Gantt & calendar in the console | `ui/src/ee/team/` |
| *(no key)* | CLI | `polyris-backfill` | Ships with the Team edition |

**Coming to open-core:** `backfill` and the asset console (`assets.management`) are
on the graduation roadmap — the `/backfills` and `/assets` pages show a *coming in
an upcoming release* notice in the public build rather than a permanent
paid-tier lock (ADR #105 established the pattern).

## Enterprise (paid)

Ships in the same paid build as Team; the deployment's `POLYRIS_TIER` decides
whether Enterprise capabilities are enabled (a *runtime entitlement*, not a
separate build).

| Capability | Status |
|------------|--------|
| Governance — RBAC / SSO / MFA / audit | Roadmap (ADR #100) — no Enterprise capability has landed yet |
| Cost reporting | Roadmap |
| Cross-account | Roadmap |

The registry (`console_api/ee/entitlements.py`) currently has an **empty
Enterprise set**; the first Enterprise feature adds its key there and gates its
route with `@requires("<key>")`.

## How the boundary is enforced

Two independent mechanisms, one per axis (ADR #98/#99/#100):

- **Free ↔ paid is a physical strip.** The public build ships without the `ee/`
  trees, so paid code simply is not present. For API routes the source of truth is
  *module namespace*: anything registered by an `ee.*` module is paid, everything
  registered by a `routes.*` module is free. `ee/team/tests/test_route_table_ee.py`
  derives the free/Team split from that and asserts the tiers are disjoint and
  cover the whole route table — so a feature moving across the seam (as in ADR
  #110) is tracked automatically, with no count or list to hand-maintain.
- **Team ↔ enterprise is a runtime entitlement.** Both paid tiers ship together;
  `console_api/ee/entitlements.py` (`FEATURES`) is the source of truth for which
  capability belongs to which paid tier, `POLYRIS_TIER` selects the deployment's
  tier, and `can()` (UI) / `@requires` (backend) gate Enterprise features. Team
  capabilities need no gate — they are granted on any paid deployment.

## Changing an edition boundary

Moving a feature across the free↔paid line is a `git mv` between the free tree and
`ee/` plus the module's register line — not a rewrite (the overlay / РОЗЧЕПЛЕННЯ
model, ADR #99). When you do, update **this file**, the relevant ADR, and — for a
team↔enterprise change — the `FEATURES` registry. The route-table guard will fail
until the physical move and this map agree.

## Related ADRs

`adr-98-open-core-split-structure.md`, `adr-99-ui-open-core-exclusion.md`,
`adr-100-tier-entitlement.md`, `adr-104-*` (CLI split + nav-tab slot),
`adr-105-*` (asset console → Team, coming-soon), `adr-110-intervention-tier-flip.md`
(task/execution intervention → free).
