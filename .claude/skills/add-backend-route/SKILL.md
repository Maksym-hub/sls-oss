---
name: add-backend-route
description: Use when adding or changing a console_api HTTP endpoint in the Python backend (sam/lambdas/console_api/) — a new GET/POST route, a handler, or wiring an existing handler. Covers the free / Team / Enterprise tier (open-core) decision, the self-registering route-module pattern (ADR #97), the `@requires` entitlement gate for Enterprise routes (ADR #100), how it joins the route table, the data-access layer, and pytest-mock tests. Trigger for "add an endpoint/route/API", "new backend handler", or changing what the API exposes.
---

# Adding a backend route (open-core aware)

The console_api is one Lambda. Routes self-register into a table (ADR #97). Two
open-core boundaries (ADR #98/#100): **free↔paid** is physical — the paid route
set is appended only when the `ee` package is present, so the public build
exposes exactly the free routes; **team↔enterprise** is a runtime entitlement —
both paid tiers ship together and an Enterprise route gates itself with
`@requires(<cap>)` against the deployment's `SLSFLOW_TIER`. Read the "API Routes"
section of `CLAUDE.md` once before starting. For the cross-cutting tier model
(the two boundaries, the entitlement registry, adding a whole new tier) see the
**tier-and-entitlements** skill — this skill covers only the per-route mechanics.

## Step 1 — Decide the tier

- **Free** (`routes/`): reads an OSS operator needs — list/detail of pipelines,
  runs, tasks, assets, health/metrics.
- **Team** (`ee/team/`): mutations and ops — pipeline actions (run/stop/pause),
  backfills, drift, asset matrix, notification fan-out, API tokens.
- **Enterprise** (`ee/enterprise/`): governance and the highest tier — cost
  reporting, RBAC/SSO/MFA, audit, cross-account, cross-pipeline upstream.

Mutating or operational → Team. Governance / multi-tenant → Enterprise. When in
doubt between free and paid, default to free; between the paid tiers, default to
Team (the lower paid tier).

## Step 2 — Write the route module

A route module exposes one function: `register(router)`. Handlers take the Lambda
event (and an optional path param). Copy the shape from `routes/health.py` (free)
or `ee/team/backfill.py` (Team):

```python
def my_handler(event):
    # parse query/body from event, call the DAL, return a response dict
    ...

def register(router) -> None:
    router.add('GET',  '/api/things', list_things)
    router.add('POST', '/api/things/do', do_thing)   # mutations: Team only
```

**Enterprise routes gate themselves** with `@requires(<cap>)` from
`ee/entitlements.py` — it returns 403 when the deployment's `SLSFLOW_TIER` does
not grant the capability. First add the key to `FEATURES` in `ee/entitlements.py`
under the `enterprise` tier, then decorate the handler:

```python
from ee.entitlements import requires

@requires('cost.reporting')          # 403 on a Team deployment
def get_cost(event):
    ...
```

Team routes need **no** decorator — they are granted on any paid deployment and
are absent from the OSS build entirely (the free↔paid strip already excludes them).

- Use the existing **data-access layer** (`dal/…`) for DynamoDB — do not call
  boto3 tables directly from handlers.
- Errors must be visible to operators (ADR #38): typed exception handling with
  logging, never a silent `except: pass`.
- Public paths must be allow-listed in `auth.py` (`is_public_path` /
  `ADMIN_ROUTES`) if they should skip the auth gate.

## Step 3 — Join the route table

- **Free:** import the module in `main.py` and add it to the `ROUTE_MODULES`
  list.
- **Team:** add the module to `ee/team/`'s exported `MODULES`. `main.py` already
  does `try: ROUTE_MODULES += ee.MODULES / except ImportError: pass` — that
  `try/except` **is** the open-core seam (OSS has no `ee`, so the Team routes
  simply never register). Do not touch the dispatch logic.
- **Enterprise:** add the module to `ee/enterprise/`'s exported `MODULES`.
  `ee/__init__.py` composes `team.MODULES + [capabilities] + enterprise.MODULES`,
  so an Enterprise module joins the surface automatically when `ee/enterprise/` is
  present. The route registers on every paid build; the `@requires` gate (Step 2)
  is what restricts it to Enterprise deployments at runtime.

## Step 4 — Enums / shared constants

If the route returns or accepts a status/enum, source it from the canonical
`slsflow/constants.py` (or the generated `_shared/`) — never hand-duplicate enum
values. Run `make sync-constants` if you touched a family.

## Step 5 — Tests (pytest-mock, ADR #26)

Use the `mocker` fixture — never `unittest.mock`. Mock at the boundary (the DAL /
boto3), let handler logic run. Place tests in:

- Free route → `sam/lambdas/console_api/tests/`
- Team route → `sam/lambdas/console_api/ee/team/tests/`
- Enterprise route → `sam/lambdas/console_api/ee/enterprise/tests/` (add this path
  to the pytest invocation once that tier has its first test)

Run from the function dir with the SDK importable:

```
pip install -e .                     # slsflow editable (once)
cd sam/lambdas/console_api
PYTHONPATH=. python -m pytest tests/ ee/team/tests/ -v
```

(`import slsflow` resolves via the editable install — no symlink needed for tests.)

## Step 6 — If the route backs a UI action

A Team mutation usually has a matching UI control. Pair this with the
`add-ui-feature` skill: the UI calls the route through a Team hook/provider, and
both must stay on the Team side of the seam.
