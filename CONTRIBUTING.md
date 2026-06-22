# Contributing to slsflow

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | All Lambdas run on 3.12 |
| Node.js | 22+ | LTS recommended; minimum 18.18 for Next.js 16 |
| AWS SAM CLI | latest | For infrastructure deployment |
| AWS CLI | 2.x | For local testing |
| Make | any | For convenience commands |

No AWS credentials needed for running tests locally (uses pytest-mock `mocker` fixture).

### Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| boto3 | latest | AWS SDK |
| pytest | 7.0+ | Testing |
| pytest-mock | 3.0+ | `mocker` fixture for patching |
| jsonata | 2.0+ (npm) | SFN template expression tests |
| next | 16.x | UI framework (App Router) |
| react | 19.x | UI library |
| vitest | 2.x | UI testing |

---

## Quick Start for Developers

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_ORG/slsflow.git
cd slsflow

# Python dependencies (for SDK development)
pip install -e ".[dev]"

# UI dependencies
cd ui && npm install && cd ..
```

### 2. Run All Tests

```bash
# Everything at once
make test

# Or by area:
make test-sdk           # pytest tests/sdk/
make test-lambdas       # evaluate_deps, check_assets, notify_asset_subscribers, console_api
make test-sfn-jsonata   # JSONata expression tests (requires Node.js)
make test-ui            # vitest (requires npm install in ui/)
```

### 3. Before Committing

```bash
make check   # Runs: lint, sync-constants, test

# Or manually:
make sync-constants
make lint
```

---

## Running the UI Locally

```bash
cd ui

# Copy environment template
cp .env.example .env.local

# Edit .env.local:
# API_GATEWAY_URL=https://xxx.execute-api.us-east-1.amazonaws.com/api
# NEXT_PUBLIC_AUTH_ENABLED=false

# Start dev server
npm run dev
# → http://localhost:3000
```

**Note:** UI needs a backend API. Options:
1. Point to deployed dev environment (set `API_GATEWAY_URL` in `.env.local`)
2. Run with mock data (not yet implemented)

---

## Project Structure

```
slsflow/
├── slsflow/              # Python SDK - the DSL users write pipelines with
│   ├── ai/               # AI assistant (slsflow-ai CLI)
│   ├── dag.py            # DAG class
│   ├── task.py           # @task decorators
│   ├── generators.py     # Step Functions JSON generation
│   └── ...
│
├── sam/     # AWS Infrastructure
│   ├── lambdas/          # Lambda function code
│   │   ├── console_api/  # REST API (52 endpoints)
│   │   ├── evaluate_deps/# Dependency evaluation
│   │   ├── check_assets/ # Asset freshness checks
│   │   ├── notify_asset_subscribers/ # Asset event notification
│   │   ├── query_subscriptions/     # Downstream subscriber lookup
│   │   └── _shared/      # Shared constants (SOURCE OF TRUTH)
│   ├── sfn_templates/    # Step Functions ASL templates
│   └── template.yaml    # SAM template
│
├── ui/                   # React Console UI
│   └── src/
│       ├── components/   # React components
│       ├── hooks/        # Custom hooks (with tests!)
│       └── utils/        # Helpers
│
├── tests/                # SDK integration tests
├── docs/                 # Documentation
└── pipelines/            # Example pipelines
```

---

## Key Concepts

### Lambda Constants Sync

Lambdas can't share code, so `TaskStatus` is duplicated. Keep in sync manually:

```bash
# Check if in sync
make sync-constants

# Fix by copying source of truth
cp sam/lambdas/_shared/constants.py sam/lambdas/evaluate_deps/constants.py
```

**Source of truth:** `sam/lambdas/_shared/constants.py`

### Testing Strategy

| Area | Test File | Run With | What it tests |
|------|-----------|----------|---------------|
| SDK core (DAG, tasks, DSL) | `tests/sdk/test_smoke.py` | `pytest tests/sdk/` | DAG structure, dependencies, ASL generation, constants |
| ASL snapshots | `tests/sdk/test_asl_snapshots.py` | `pytest tests/sdk/` | Golden file comparison of generated Step Functions JSON |
| Template features | `tests/sdk/test_templates.py` | `pytest tests/sdk/` | orchestration_timeout, route table, run_task resilience |
| API routes | `tests/backend/test_api_routes.py` | `pytest tests/backend/` | All 49 console_api routes registered and callable |
| Trigger rules | `tests/sdk/test_trigger_rules.py` | `pytest tests/sdk/` | 11 trigger rules: Python ↔ JSONata logic sync |
| SFN flow graphs | `tests/sdk/test_sfn_flow.py` | `pytest tests/sdk/` | State references, reachability, Catch, cycles for all 13 templates |
| JSONata expressions | `tests/sfn_jsonata/` | `cd tests/sfn_jsonata && npm test` | Default fallbacks, type conversions, conditionals, 550 expressions compile |
| evaluate_deps Lambda | `sam/lambdas/evaluate_deps/` | `PYTHONPATH=. pytest` | BatchGetItem, trigger_rule evaluation, paused check |
| check_assets Lambda | `sam/lambdas/check_assets/` | `PYTHONPATH=. pytest` | Asset freshness, wait_for logic |
| notify_asset_subscribers | `sam/lambdas/notify_asset_subscribers/` | `PYTHONPATH=. pytest` | Asset event publishing, subscriber notification |
| console_api Lambda | `sam/lambdas/console_api/tests/` | `PYTHONPATH=. pytest` | API routes, query/scan pagination, validation |
| UI hooks | `ui/src/hooks/*.test.{js,jsx}` | `npm test` | React hooks, state management |

**Note:** `pip install -e ".[dev]"` installs: pytest, pytest-cov, ruff, mypy. Lambda tests only need pytest and boto3.

### Local Lambda Development

```bash
cd sam/lambdas/evaluate_deps

# Run tests with mocked DynamoDB
PYTHONPATH=. pytest test_evaluate_deps.py -v

# Test specific function
PYTHONPATH=. pytest test_evaluate_deps.py::TestCheckTriggerRule -v
```

---

## Common Tasks

> **Open-core & skills.** slsflow is open-core with **three tiers**: free
> (open-source), **Team** and **Enterprise** (both paid, hosted). Proprietary code
> lives per tier under `ui/src/ee/{team,enterprise}/` and
> `console_api/ee/{team,enterprise}/`; everything else is public and the public
> build ships without `ee/`. Two boundaries: **free↔paid** is a physical strip;
> **Team↔Enterprise** is a runtime entitlement (`SLSFLOW_TIER` + `can()`). Before
> adding a feature, decide the tier (authoring/basic-read = free; ops/intervention
> = Team; governance/cost/SSO = Enterprise). The checklists below are summaries —
> for the full step-by-step **including the tier decision and the OSS build guard**,
> use the Claude Code skills in [`.claude/skills/`](.claude/skills):
> **`tier-and-entitlements`** (the tier model + adding a tier or Enterprise
> feature), **`add-ui-feature`**, **`add-backend-route`**, **`add-aws-service`**.
> See the "Open-core UI surface" and "API Routes" sections of `CLAUDE.md` for the
> mechanism (ADR #97/#98/#99/#100).

### Adding a New Task Status

1. Add to `_shared/constants.py`
2. Copy to `evaluate_deps/constants.py`
3. Update `console_api/constants.py` manually if needed
4. Update UI constants in `ui/src/utils/constants.js`
5. Run `make sync-constants` to verify

### Adding a New API Endpoint

See the **`add-backend-route`** skill for the full flow. In short:

1. Decide the tier: read → `console_api/routes/`; mutation/ops → `console_api/ee/team/`
2. Add a `register(router)` module with `router.add(METHOD, path, handler)`
3. Wire it: free → `ROUTE_MODULES` in `console_api/main.py`; Team → `ee/team` `MODULES`
4. Tests with `pytest-mock` in `console_api/tests/` (free) or `ee/team/tests/` (Team)
5. Document in `docs/operations/API.md`

### Modifying Step Functions

1. Edit template in `sfn_templates/<helper>/sfn.tpl.json`
2. Run graph validation: `pytest tests/sdk/test_sfn_flow.py -v`
3. Run JSONata tests: `cd tests/sfn_jsonata && npm test`
4. Run smoke tests: `pytest tests/sdk/test_smoke.py -v`
5. Update ASL snapshots if needed: `SNAPSHOT_UPDATE=1 pytest tests/sdk/test_asl_snapshots.py`
6. Deploy to dev: `sam deploy`
7. Test in AWS Console

---

## Sign your commits (DCO)

slsflow uses the [Developer Certificate of Origin](DCO) — by signing off you
certify you wrote the patch or otherwise have the right to contribute it under the
project's Apache-2.0 license. **Every commit must be signed off**, and CI enforces
it (`.github/workflows/dco.yml`):

```bash
git commit -s                       # appends "Signed-off-by: Name <you@example.com>"
git rebase --signoff origin/main    # retro-fit sign-off across an existing branch
```

The sign-off name/email must match your commit author identity.

> **DCO vs CLA.** The DCO is a lightweight provenance check; contributions come in
> under the same Apache-2.0 license (inbound = outbound). It deliberately does
> **not** ask you to assign rights. Because slsflow's paid tiers are built from
> *separate* code — not from contributions to the open core — a heavier Contributor
> License Agreement is **not** required today. If relicensing optionality on
> contributed core code is ever needed, a CLA (e.g. via cla-assistant) would be
> added then. This is a deliberate, recorded choice, not an oversight.

---

## PR Checklist

- [ ] Commits signed off (`git commit -s`) — see [DCO](#sign-your-commits-dco)
- [ ] Tests pass locally (`make test`)
- [ ] Constants synced (`make sync-constants`)
- [ ] No lint errors (`make lint`)
- [ ] CHANGELOG.md updated
- [ ] Documentation updated (if API changed)

---

## Getting Help

- **Architecture questions:** See `docs/architecture/`
- **API reference:** See `docs/operations/API.md`
- **Slack:** #slsflow-dev
