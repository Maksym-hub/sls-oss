---
name: add-ui-feature
description: Use when adding anything to the SLSFlow Next.js console (ui/) — a new top-level tab/view, a sub-tab inside an existing tab, a panel, a modal, or a component. Walks the free / Team / Enterprise tier (open-core) decision, where the file goes, how to wire it (App route, paidSurface slot, render-prop provider, or can() gate), the CSS rules, tier-following tests, and the OSS build guard. Trigger for any request like "add a tab", "add a view", "new sub-tab", "add a panel/modal/component" to the UI.
---

# Adding a UI feature (open-core aware)

The console is split at build time. The proprietary **paid surface** lives under
`ui/src/ee/`, organised per tier — `ui/src/ee/team/` and `ui/src/ee/enterprise/`;
everything else is public. Two boundaries (ADR #100): **free↔paid** is a physical
strip (the public build ships without `src/ee/`); **team↔enterprise** is a runtime
entitlement — both paid tiers ship in one bundle and `can()` gates Enterprise
features. Read the "Open-core UI surface (ADR #99)" section of `CLAUDE.md` once
before starting.

## Step 1 — Decide the tier

- **Free** (`ui/src/components`, `ui/src/hooks`): authoring and basic read —
  viewing pipelines/runs/tasks, the DAG, task details, anything a single-user
  OSS operator needs.
- **Team** (`ui/src/ee/team/…`): operations, advanced observability, or
  intervention — anything that acts on a running pipeline, asset
  matrix/lineage/drift, backfills, Gantt/Calendar, API tokens.
- **Enterprise** (`ui/src/ee/enterprise/…`): governance and the highest tier —
  cost reporting, SSO/RBAC/MFA, audit, cross-account, cross-pipeline upstream.

If unsure between free and paid, default to **free** — moving a free feature into
`ee/` later is trivial; the reverse leaks paid code into the public repo. If
unsure between the two paid tiers, default to **Team** (the lower paid tier).

**Adding a whole new tier** (rare, spans backend + UI): the full recipe lives in
the **tier-and-entitlements** skill. UI side only: `mkdir src/ee/<tier>` with an
`index.ts` exporting a `surface` — the generator scans `src/ee/*/index.ts`, so it
is picked up automatically (no edit to the generator or to free code).

## Step 2 — Place the file

| What | Free location | Paid location (`<tier>` = `team` or `enterprise`) |
|---|---|---|
| Whole view / top-level tab | `src/components/<Name>View.tsx` | `src/ee/<tier>/views/<Name>View.tsx` |
| Panel / modal / component | `src/components/…` | `src/ee/<tier>/components/…` |
| Sub-tab inside a tab | inside the parent tab component | a slot the parent renders |
| Query hook | `src/hooks/queries/` | `src/ee/<tier>/hooks/queries/` |

A paid query a **free** component needs stays free (e.g. `useBackfillsListQuery`
— the Header badge depends on it).

## Step 3 — Wire it

**Free view / tab:** add it to the router/tab list in `App.tsx` (and the nav)
like the existing views. Nothing else.

**Self-contained component** (panel, modal, view, sub-tab): use a typed slot.
1. Add the slot to `PaidSurface` in `src/ee-contract.ts` (with a typed prop
   interface from `@/types`).
2. Register the real component in that tier's `surface` — `src/ee/<tier>/index.ts`.
3. In the free host, capture and render it:
   ```tsx
   const Panel = paidSurface.MyPanel;            // const-in-closure narrows
   …
   {Panel ? <Panel … /> : <EeFeatureFallback/>}  // empty in OSS
   ```
   For a sub-tab, gate both the tab **button** and its **content** on the slot
   (`{Panel && <TabButton …/>}` and `… : Panel ? <Panel/> : null`).
4. **Enterprise only** — also gate on `can()`. An Enterprise component is
   *present* in the paid bundle on a Team deployment but not *entitled*, so the
   slot check alone would render it. Add a capability key to
   `console_api/ee/entitlements.py` (tier `enterprise`), enforce its data routes
   with `@requires`, and gate the slot:
   ```tsx
   const Panel = paidSurface.MyPanel;
   const can = useCan();                          // from @/hooks/queries
   {Panel && can('my.capability') ? <Panel … /> : <EeFeatureFallback/>}
   ```
   `can()` is UX only — the API enforces. Team slots need no `can()` (granted on
   any paid deployment).

**Cross-cutting Team handlers woven through a free host** (actions used by a
toolbar + a banner + a modal, like pipeline actions): use a **render-prop
provider** in the tier's `src/ee/<tier>/views/`. The provider owns the hook + any
tier-only modal and exposes handlers via `children(handlers)`; the free host wraps
its content `Provider ? <Provider …>{h => content(h)}</Provider> : content(null)`
and gates each control on the handlers being present (for Enterprise, additionally
on `can()`). See `src/ee/team/views/PipelineActionsProvider.tsx`.

**Invariants:** free code never imports `src/ee/` directly — only through
`@/ee-active.generated` (components) and `@/ee-contract` (types). `src/ee/` may
import free modules, never the reverse; and `ee/team/` never imports
`ee/enterprise/` (enterprise may import team).

## Step 4 — CSS

Edit the global stylesheets in `ui/src/styles/modules/_*.css`
(`_navigation`, `_tasks`, `_assets`, `_dag`, `_layout`, …). **Never** create or
edit a `.module.css` — they are dead code in this repo (the build proves zero
exist). Follow the 7 responsive rules in ADR #40.

## Step 5 — Tests follow the tier

A paid component/hook's test lives next to it under `src/ee/<tier>/` (stripped in
OSS); a free test stays under `src/`. Use Vitest + Testing Library. When a free
host's test needs a slot, mock `@/ee-active.generated`'s `paidSurface` (pass a stub
component, or for a provider a passthrough `({children}) => children(mockHandlers)`).

## Step 6 — Verify (all must pass)

```
cd ui
npm run typecheck
npm test -- --run
npm run build
bash scripts/check-oss-build.sh   # strips src/ee → proves the OSS build still builds
```

The last command is the open-core guard: if free code leaked an `@/ee` import or
a type from a Team module, it fails here.
