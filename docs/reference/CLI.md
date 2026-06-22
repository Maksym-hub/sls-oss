# CLI Reference

All slsflow commands. Run from your pipeline directory unless noted.

---

## slsflow

Top-level dispatch command (v0.78+). Without arguments prints help.
Subcommands route to backfill operations against a deployed Console API.

```bash
slsflow                                    # show help
slsflow backfill pipeline NAME [opts]      # backfill a pipeline
slsflow backfill asset NAME [opts]         # backfill an asset
slsflow backfills list [--status ...]      # list recent backfills
slsflow backfills show ID                  # show backfill detail
slsflow backfills cancel ID                # cooperatively cancel
slsflow backfills retry-failed ID          # fork new backfill with failed partitions
```

### Configuration

The `backfill*` subcommands talk to the Console API over HTTPS. Configure
via env vars:

```bash
export SLSFLOW_API_URL=https://abc123.execute-api.us-east-1.amazonaws.com/Prod
export SLSFLOW_API_TOKEN=<optional-bearer-token>   # if API is protected
```

### `slsflow backfill pipeline`

Start a backfill targeting a pipeline. The pipeline's cron schedule is
read at runtime and used to infer partition granularity (per ADR #52);
ambiguous schedules default to `daily` with a warning.

```bash
slsflow backfill pipeline daily-etl \
    --start 2024-01-15 --end 2024-01-20 \
    --max-parallel 5 \
    --tasks extract,transform \
    --variables '{"region": "us-east"}' \
    --preview            # show plan without starting
```

Options:
- `--start DATE` (required) — start partition key or date
- `--end DATE` (required) — end partition key or date
- `--tasks LIST` — comma-separated task names (subset of pipeline)
- `--max-parallel N` — Map concurrency 1–10 (default 5)
- `--force` — bypass safety checks
- `--no-skip-completed` — re-run already-completed partitions
- `--incremental` — stop on first failure
- `--variables SPEC` — JSON object or `k1=v1,k2=v2`
- `--preview` — return the plan + cost estimate without starting

### `slsflow backfill asset`

Start a backfill targeting an asset. The producer pipeline is resolved
from `pipeline_registry` outlets; multiple producers fail with a list of
candidates so you can re-issue with `target.type=pipeline`.

```bash
slsflow backfill asset catalog/db/orders \
    --start 2024-01-15 --end 2024-01-15 \
    --cascade auto
```

Same options as `backfill pipeline`, plus:
- `--cascade auto|all|none` — cascade strategy for downstream consumers
  (default `auto` = respect trigger rules)

### `slsflow backfills list`

```bash
slsflow backfills list                          # all recent
slsflow backfills list --status active          # pending + running
slsflow backfills list --status failed --limit 25
```

Status values: `active`, `pending`, `running`, `completed`, `failed`,
`partial`, `canceled`.

### `slsflow backfills show ID`

```bash
slsflow backfills show bf-a1b2c3d4
```

Returns full backfill record with partition keys, child executions, and
parsed options.

### `slsflow backfills cancel ID`

```bash
slsflow backfills cancel bf-a1b2c3d4
```

Marks status as `canceled` in DDB. The bulk-backfill SFN's Map iterator
checks at each iteration and short-circuits remaining partitions. In-
flight child executions continue to completion (per ADR #54).

Returns exit code 1 with `already_terminal` if the backfill is already
done.

### `slsflow backfills retry-failed ID`

```bash
slsflow backfills retry-failed bf-a1b2c3d4
```

Creates a new Backfill containing only the failed partitions of the
parent, linked via `parent_backfill_id`. Only valid when parent status
is `failed` or `partial`.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | API returned 4xx/5xx (response printed to stderr) |
| 2 | Missing or invalid configuration (`SLSFLOW_API_URL` unset) |
| 3 | Network/transport failure |
| 4 | Bad CLI arguments |
| 130 | Interrupted (Ctrl-C) |

---

## slsflow (legacy help dispatcher)

For backward compat, `slsflow` without subcommand prints help text. Use
the named entry points below for deployment workflows.

---

## slsflow-init

Create a new pipeline or initialize project config.

```bash
# Initialize project config.py (run once in project root)
slsflow-init --project

# Create a new pipeline (creates my-pipeline/dag.py)
slsflow-init my-pipeline

# Try locally without AWS (explore DSL)
slsflow-init my-pipeline --local

# Custom schedule
slsflow-init my-pipeline --schedule "@hourly"
slsflow-init my-pipeline --schedule "0 9 * * MON-FRI"

# Interactive wizard
slsflow-init my-pipeline -i

# Custom directory
slsflow-init my-pipeline --dir ./pipelines
```

| Option | Description |
|--------|-------------|
| `name` | Pipeline name (optional with `--project` or `-i`) |
| `--project` | Generate `config.py` template in current directory |
| `--local` | Create pipeline without AWS (for exploring DSL) |
| `--schedule` | Cron schedule (default: `@daily`) |
| `--dir` | Base directory (default: `.`) |
| `-i`, `--interactive` | Interactive wizard |

---

## slsflow-validate

Validate pipeline(s) for errors. Run from pipeline directory.

```bash
# Validate dag.py in current directory
slsflow-validate

# Verbose — shows schedule, task count, state count
slsflow-validate -v

# Validate all pipelines found in project
slsflow-validate --all

# All pipelines, verbose
slsflow-validate --all -v

# Specific file
slsflow-validate --file my_pipeline.py

# Run python_callable for @task.python tasks
slsflow-validate --test

# JSON output
slsflow-validate --json
```

| Option | Description |
|--------|-------------|
| `--all`, `-a` | Find and validate all pipelines in project |
| `-v`, `--verbose` | Show schedule, task count, state count |
| `--file`, `-f` | Pipeline file (default: `dag.py`) |
| `--test` | Run python_callable for `@task.python` tasks |
| `--json` | Output results as JSON |

---

## slsflow-output

Generate pipeline artifacts. Run from pipeline directory.

```bash
# Generate Step Functions ASL JSON
slsflow-output --json

# Generate Mermaid diagram
slsflow-output --mermaid

# Show DAG as ASCII graph
slsflow-output --graph

# Generate asset registry JSON
slsflow-output --assets

# Custom file
slsflow-output --json --file my_pipeline.py

# Multi-DAG file — select specific DAG
slsflow-output --json --select my-dag-id
```

| Option | Description |
|--------|-------------|
| `--json` | Generate Step Functions ASL JSON |
| `--mermaid` | Generate Mermaid diagram |
| `--graph` | Show DAG as ASCII graph |
| `--assets` | Generate asset registry JSON |
| `--file`, `-f` | Pipeline file (default: `dag.py`) |
| `--select` | Select DAG by ID (for multi-DAG files) |

---

## slsflow-deploy

Deploy pipeline to AWS via CloudFormation. Run from pipeline directory.

```bash
# Deploy using defaults from config.py
slsflow-deploy

# Deploy to specific stage
slsflow-deploy --stage prod

# Override AWS profile
slsflow-deploy --profile my-aws-profile

# Both
slsflow-deploy --stage prod --profile my-aws-profile

# Preview without deploying
slsflow-deploy --dry-run

# Remove pipeline stack
slsflow-deploy --destroy

# Deploy specific file
slsflow-deploy --file my_dag.py

# Multi-DAG file — deploy specific DAG
slsflow-deploy --select my-dag-id
```

| Option | Description |
|--------|-------------|
| `--stage` | Deployment stage (default: from `config.py DEFAULT_STAGE`) |
| `--profile` | AWS profile (default: from `config.py` or AWS default) |
| `--file` | Pipeline file (default: `dag.py`) |
| `--dry-run` | Preview CloudFormation changes without deploying |
| `--destroy` | Remove pipeline stack and clean up DynamoDB |
| `--select` | Select DAG by ID (for multi-DAG files) |
| `--region` | AWS region (default: from `config.py`) |
| `--log-level` | CloudWatch log level: `ALL`, `ERROR`, `FATAL`, `OFF` (default: `ERROR`) |
| `--log-retention` | Log retention in days (default: `30`) |

---

## slsflow-register

Manually register a pipeline in DynamoDB (without running tasks).

```bash
# Register by ARN
slsflow-register arn:aws:states:us-east-1:123456789:stateMachine:my-pipeline

# Register by name
slsflow-register --name my-pipeline

# With specific profile and region
slsflow-register --name my-pipeline --profile prod --region us-east-1

# Assume IAM role (cross-account)
slsflow-register --name my-pipeline --role-arn arn:aws:iam::123:role/deploy

# JSON output
slsflow-register --name my-pipeline --json
```

| Option | Description |
|--------|-------------|
| `arn` | Step Function ARN (positional, optional) |
| `--name`, `-n` | Pipeline name (alternative to ARN) |
| `--region`, `-r` | AWS region (default: from `config.py` or `us-east-1`) |
| `--profile`, `-p` | AWS profile from `~/.aws/credentials` |
| `--namespace` | Namespace prefix for pipeline search |
| `--role-arn` | IAM role ARN to assume (cross-account) |
| `--json` | Output result as JSON |
