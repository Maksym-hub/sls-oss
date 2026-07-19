# polyris examples

Self-contained pipelines that build up the DSL. Every one runs **locally with no
AWS account** — explore the DSL, see the generated Step Functions definition, and
iterate before you deploy anything.

The first three are minimal intros; `04`–`08` each exercise a slice of the full
feature surface (task types, branching, direct steps, operational settings, and a
realistic end-to-end run).

| Example | Concept |
|---|---|
| [`01_hello_world`](01_hello_world/dag.py) | The smallest pipeline — one scheduled task |
| [`02_linear_etl`](02_linear_etl/dag.py) | `extract → transform → load`; passing data between tasks |
| [`03_fan_in_trigger_rule`](03_fan_in_trigger_rule/dag.py) | Parallel tasks + a `trigger_rule` (`all_done`) |
| [`04_multi_service`](04_multi_service/dag.py) | Six AWS task types: `sfn`, `lambda_`, `glue`, `athena`, `ecs`, `batch` + `default_args` + cross-account `role` (`emr` is supported too but omitted here — it needs a live cluster) |
| [`05_branching`](05_branching/dag.py) | Fan-out / fan-in, trigger rules, `chain()` / `cross_downstream()` |
| [`06_direct_steps`](06_direct_steps/dag.py) | Direct service steps (`Wait`, `Pass`, `SNS`, `SQS`, `S3`), `wait_before`, `rate(...)`, `variables` |
| [`07_operational`](07_operational/dag.py) | Retries + backoff, timeouts, `skip_on_backfill`, `catchup`, concurrency limits |
| [`08_realistic`](08_realistic/dag.py) | A plausible daily analytics pipeline combining several services end to end |
| [`09_trigger_rules`](09_trigger_rules/dag.py) | All ten fan-in `trigger_rule` conditions side by side |
| [`10_manual`](10_manual/dag.py) | An on-demand pipeline with **no schedule** (manual trigger only) |
| [`11_assets_basic`](11_assets_basic/dag.py) | Declaring asset `inlets`/`outlets` for lineage *(experimental)* |
| [`12_assets_lineage`](12_assets_lineage/dag.py) | Cross-pipeline asset lineage + asset-triggered runs *(experimental)* |

## Run one locally

```bash
pip install -e .                 # from the repo root, once
cd examples/01_hello_world

polyris-validate                 # is the DAG valid?
polyris-validate -v              # verbose: tasks, dependencies, ASL preview
polyris-output --graph           # the DAG as an ASCII graph
polyris-output --mermaid         # a Mermaid diagram you can paste anywhere
polyris-output --json            # the full Step Functions definition (ASL)
```

Each `@task.sfn` invokes an existing Step Functions state machine, so the ARNs
in these files are placeholders — they're fine for local validation; replace
them with your own before deploying.

## Deploy one for real

```bash
cd examples/02_linear_etl
polyris-deploy                   # builds + deploys via CloudFormation
```

See the top-level [README](../README.md) and
[docs/getting-started](../docs/getting-started/) for setup, the tutorial, and the
full DSL reference.
