---
name: tier-and-entitlements
description: Use when working with SLSFlow's open-core tiers or entitlements rather than a single component — adding a new paid tier, making a feature Team- or Enterprise-only, adding a capability/entitlement key, gating something behind a plan, or understanding the model. The canonical reference for the two boundaries (free↔paid = physical strip; team↔enterprise = runtime entitlement). Trigger for "add a tier", "new pricing/paid tier", "make X Enterprise-only / paid-only", "add a capability/entitlement", "gate behind a plan", "how do the tiers work", or any change that spans the backend + UI of the open-core split. For a single route use add-backend-route; for a single component use add-ui-feature — this skill owns the cross-cutting tier work they reference.
---

# Tiers and entitlements (open-core)

SLSFlow ships three tiers — **free** (open-source), **Team** (paid), **Enterprise**
(paid). They are separated by **two different boundaries**; getting the right one
is the whole game (ADR #98/#99/#100).

## The two boundaries

1. **free ↔ paid — a physical strip** (ADR #98/#99). Proprietary code lives under
   `ee/` roots (`sam/lambdas/console_api/ee/`, `slsflow/_ee/`, `ui/src/ee/`); the
   OSS build *removes* them. This is a **repo-publication** boundary — proprietary
   code must never enter the public repo, so it must be physically absent, not
   flag-gated. The build proves it (`ui/scripts/check-oss-build.sh`, the backend's
   16-vs-58 route tests).

2. **Team ↔ Enterprise — a runtime entitlement** (ADR #100). Both paid tiers ship
   in **one** build (SLSFlow hosts the paid tiers itself; single-tenant, one
   deployment = one customer). A deployment-level `SLSFLOW_TIER`
   (`team` | `enterprise`) decides what is *enabled*. This is **not** a second
   strip — Enterprise code is present in the paid bundle and gated at runtime.

> If a self-hosted (on-prem) paid tier is ever needed, the tier directories are
> physical, so the same parameterised strip layers on one level deeper (a Team
> artifact strips `enterprise/`) with no rework. Until then, do not build per-tier
> artifacts.

## Where it lives

- **Registry (single source of truth):** `sam/lambdas/console_api/ee/entitlements.py`
  — `FEATURES` (capability key → owning tier), the tier→capability derivation
  (`enterprise ⊇ team` by construction), `deployment_tier()` (reads
  `SLSFLOW_TIER`), and the `@requires(<cap>)` route decorator.
- **Report route:** `GET /api/capabilities` (`ee/capabilities.py`) → `{tier,
  capabilities}` for the UI. Present on any paid build; absent in OSS.
- **UI hooks (free):** `useCan()` / `useTier()` / `useCapabilitiesQuery()` from
  `@/hooks/queries` (backed by `/api/capabilities`).
- **Tier packages:** `console_api/ee/team/` + `console_api/ee/enterprise/`;
  `ui/src/ee/team/` + `ui/src/ee/enterprise/`.

## Invariants

- Free code never imports `ee/` directly — backend via the `try: import ee`
  seam, UI via `@/ee-active.generated` + `@/ee-contract`. `ee/` may import free.
- `ee/team/` never imports `ee/enterprise/` (Enterprise may import Team).
- Each tier fills **disjoint** capability keys and UI slots.
- The security boundary is the **API** (`@requires`); `can()` in the UI is UX
  only (it hides controls a plan lacks, but the route still rejects).

## Recipe — make a feature Team or Enterprise

1. **Pick the tier.** Operations / observability / intervention → Team.
   Governance / cost / SSO / RBAC / cross-account → Enterprise.
2. **Add a capability key** to `FEATURES` in `ee/entitlements.py` under that tier.
   (Team keys are reported for `can()`; Enterprise keys are what actually gate.)
3. **Backend route** → put it in `ee/<tier>/`, and for **Enterprise** decorate it
   `@requires('<key>')`. Team routes need no decorator (granted on any paid
   deployment; absent from OSS). Mechanics: **add-backend-route** skill.
4. **UI component** → put it in `ui/src/ee/<tier>/`, register it in that tier's
   `surface`, and for **Enterprise** gate the slot on `can('<key>')` as well as on
   presence (an Enterprise component is *in* a Team deployment's bundle but not
   entitled). Team slots need only the presence check. Mechanics: **add-ui-feature**
   skill.

A Team feature is reachable on any paid deployment, so it needs no `@requires` and
no `can()`. Only **Enterprise** features carry both gates.

## Recipe — add a whole new tier

1. **Registry:** add the tier to the inheritance map in `ee/entitlements.py`
   (which lower tiers it includes) and assign its capability keys in `FEATURES`.
   Keep `higher ⊇ lower` by deriving, never by hand.
2. **Backend package:** `mkdir sam/lambdas/console_api/ee/<tier>/` with an
   `__init__.py` exporting `MODULES = [...]`, and compose it in
   `ee/__init__.py` (one line — the backend composition is **explicit** by design,
   "explicit is better than implicit" for runtime imports). Tests go in
   `ee/<tier>/tests/` (add that path to the pytest invocation in `Makefile` /
   `ci.yml`).
3. **UI package:** `mkdir ui/src/ee/<tier>/` with an `index.ts` exporting a
   `surface`. The UI generator (`gen-ee-active.mjs`) scans `src/ee/*/index.ts`, so
   it is **auto-discovered** — no generator edit. (Backend composition is explicit;
   UI composition is generated — that asymmetry is intentional.)
4. **SAM:** extend the `SlsflowTier` parameter's `AllowedValues` in
   `sam/template.yaml`.

## Verify

```
# backend
cd sam/lambdas/console_api && PYTHONPATH=. python -m pytest tests/ ee/team/tests/ -v
# UI
cd ui && npm run typecheck && npm run test:run && npm run build && bash scripts/check-oss-build.sh
```

The OSS guard proves the free↔paid strip (no free→ee leak). For the
team↔enterprise boundary there is no shipping strip to guard — the API's
`@requires` is the enforcement, covered by entitlement unit tests
(`ee/team/tests/test_entitlements.py`).

## Deliberately deferred

The DSL→ASL codegen dispatch (`slsflow/generators.py`) is still a hardcoded
`if/elif` over task types. When the **first paid AWS service** is added it must be
refactored into a registry (so paid emitters register from `ee/` without editing
the free compiler) — its own stage + ADR. Until then, all task types are free and
the `if/elif` stands.
