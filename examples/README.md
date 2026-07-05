# polyris examples

Four small, self-contained pipelines that build up the core concepts. Every one
runs **locally with no AWS account** — explore the DSL, see the generated Step
Functions definition, and iterate before you deploy anything.

| Example | Concept |
|---|---|
| [`01_hello_world`](01_hello_world/dag.py) | The smallest pipeline — one scheduled task |
| [`02_linear_etl`](02_linear_etl/dag.py) | `extract → transform → load`; passing data between tasks |
| [`03_fan_in_trigger_rule`](03_fan_in_trigger_rule/dag.py) | Parallel tasks + a `trigger_rule` (`all_done`) |
| [`04_assets_lineage`](04_assets_lineage/dag.py) | Typed assets, lineage, and a pull-based `wait_for` dependency |

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
