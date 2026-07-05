# Roadmap

Where Polyris is heading. This is a high-level, user-facing view of planned
capabilities — not a commitment to dates or ordering. For shipped features see
[CHANGELOG.md](../../CHANGELOG.md).

Have a request or want to help build one of these? Open an issue or see
[CONTRIBUTING.md](../../CONTRIBUTING.md).

## Planned

### Pipeline authoring
- **`@task.python`** — package a Python function as a Lambda and deploy it
  directly via `polyris-deploy`, no separate packaging step.
- **DAG diff on deploy** — show what changed in a pipeline's structure before
  applying.
- **Dependency-aware backfill** — backfills that respect upstream/downstream
  asset relationships.

### Observability
- **Cost tracking per pipeline** — attribute AWS spend to individual pipelines.
- **Execution diff** — compare two runs side by side.
- **SLA indicators** — surface lateness and SLA status in the console.
- **Browser notifications** — alert on failure without watching the dashboard.
- **Task logs viewer** — read task logs directly in the UI.

### Operations at scale
- **Multi-region support** — run pipelines across more than one AWS region.
- **Role-based access control** — finer-grained permissions for teams.
- **Audit logging** — a record of who changed what, when.

### Quality of life
- **Keyboard shortcuts** — faster navigation in the console.
- **Asset lineage graph** — visualize asset dependencies as an interactive graph.

## Under consideration

Ideas being explored but not yet committed. Feedback welcome:

- Per-DAG execution budget (a monthly spend cap per pipeline).
- SLA escalation chains (tiered alerting).
- Cost estimator in the backfill UI (preview spend before running).

## How priorities are set

Polyris is built around a small, sharp core: a Python DSL that compiles to AWS
Step Functions, deployed serverlessly at low cost. Features that keep that core
simple and composable are favored over ones that add operational weight. If a
capability can live as a thin layer on top of the DSL rather than complicating
the engine, that is the preferred shape.
