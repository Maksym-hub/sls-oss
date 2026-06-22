# Adding a New Tab to AssetDetailPage

This is a step-by-step procedure for adding a new tab to the asset-detail
view. The architectural rationale for the tab pattern lives in
[ADR #48](../reference/DESIGN_DECISIONS.md#48-assetdetailpage-composition--tabs-as-independent-sub-components);
this doc is the procedural follow-up.

> **Open-core:** the asset cluster is **Team-tier** — it lives under
> `ui/src/ee/team/components/asset-tabs/` and is stripped from the public build
> (ADR #99). The general mechanics (tier decision, `paidSurface` slots, the
> OSS build guard) are in the **`add-ui-feature`** skill and the "Open-core UI
> surface" section of `CLAUDE.md`; this page is the asset-tab specifics on top
> of that.

## Decision tree before you start

Before writing code, answer these:

1. **Is this really a new tab, or a section inside an existing tab?**
   A "Checks" tab is a new tab. "A new card in the Overview tab" is
   not — extend `TabOverview.tsx` instead.

2. **What state does this tab need?**
   - State that exists *while you're on the tab and resets when you
     leave* → tab-local `useState`, lives inside the tab file.
   - State that *persists across tab switches* (e.g. a query that
     shouldn't refetch on remount, a selection you want to remember)
     → page-scoped, lives in `AssetDetailPage.tsx`, passed down.

3. **Does it need a new API endpoint or data source?**
   If yes, build the endpoint and its query hook first, then come
   back to this guide. The tab itself should not fetch — it should
   accept the query result as a prop or use a shared hook.

## Procedure

### 1. Create the tab component

In `ui/src/ee/team/components/asset-tabs/`, add `TabYourName.tsx`:

```tsx
/**
 * TabYourName — one-line summary of what this tab shows.
 *
 * Renders:
 *   - First section: brief description
 *   - Second section: brief description
 *
 * Added in vX.Y.Z (ADR #48).
 */
import React from 'react';
import type { TabContext } from './types';

// Add any extra props this specific tab needs.
// Do NOT put them in TabContext if other tabs don't need them.
export interface TabYourNameProps extends TabContext {
    // e.g. `mySpecificData: SomeType;`
}

export function TabYourName(props: TabYourNameProps) {
    const { asset, assetName, assetEvents } = props;
    // ...
    return (
        <div className="adp-content">
            {/* Your JSX here. Use BEM classes (adp-*) consistent with
                other tabs. CSS lives in ../../styles/_assets.css. */}
        </div>
    );
}
```

**Conventions to follow:**

- Wrap the tab body in `<div className="adp-content">` — this gives
  consistent padding/scroll matching the other tabs.
- Empty states use the `adp-empty` class with a Lucide icon — see
  `TabPartitions.tsx` for the canonical pattern.
- For sections inside the tab, use `<section className="adp-section">`
  with `<h3 className="adp-section-title">`.

### 2. Wire it into the barrel export

In `ui/src/ee/team/components/asset-tabs/index.ts`:

```ts
export { TabYourName } from './TabYourName';
export type { TabYourNameProps } from './TabYourName';
```

### 3. Add it to the tab type and TABS array

In `ui/src/ee/team/components/AssetDetailPage.tsx`:

```ts
type TabId = 'overview' | 'schema' | 'partitions' | 'events' | 'checks' | 'lineage' | 'yourname';

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
    // ... existing entries
    { id: 'yourname', label: 'Your Name', icon: SomeIcon },
];
```

Then import the icon at the top of the file alongside the other icons.

### 4. Dispatch it in the body

In the same file, in the tab dispatcher block:

```tsx
{activeTab === 'yourname' && (
    <TabYourName {...ctx} /* additional props if any */ />
)}
```

### 5. (If applicable) Lift query/state to the orchestrator

If your tab needs a query result that must persist across tab switches,
or shared state used by multiple tabs:

- Add the `useXxxQuery` call near the existing `useAssetEventsQuery`
  call at the top of the component body.
- Pass the result through your tab's props.

If your tab only needs `useState` for local UI interactions (e.g. which
row is selected, whether a section is expanded), keep that `useState`
inside the tab file — no orchestrator change needed.

### 6. Add tests

Create `ui/src/ee/team/components/asset-tabs/TabYourName.test.tsx` mirroring
the structure of existing test files (vi.mock for icons, simple render
tests for each render branch).

**Required tests at minimum:**

- Renders with empty state when there's no data to show
- Renders happy-path content with mock data
- Each interactive element (button, link, expansion toggle) has at
  least one click-through test

The orchestrator's existing tests in `AssetDetailPage.test.tsx`
exercise tab integration; tab-internal logic belongs in the tab's
own test file.

### 7. Update the CSS if needed

CSS classes specific to your tab go in `ui/src/styles/_assets.css`
(global stylesheet for Asset views — adp-* and av-* classes).
**Do not create a `.module.css` file** — CSS Modules are not used
in this project (see CLAUDE.md principle 10).

### 8. Bump the tab badge logic if applicable

If your tab should display a count in its label (like
"Schema (13)" or "Events (20)"), extend `tabBadge` in the orchestrator:

```ts
const tabBadge = (id: TabId): string => {
    if (id === 'schema') return derived.schema.length > 0 ? ` (${derived.schema.length})` : '';
    if (id === 'events') return assetEvents.length > 0 ? ` (${assetEvents.length})` : '';
    if (id === 'yourname') return /* your count expression */;
    return '';
};
```

## Anti-patterns to avoid

These mistakes show up regularly and break the pattern:

- **Adding state to `TabContext` that only one tab uses.** If only
  TabSchema needs `glueQuery`, it goes on `TabSchemaProps`, not
  `TabContext`. Every other tab having a useless prop is noise.

- **Reading from a React Context inside a tab to avoid prop drilling.**
  Don't. The page is shallow (one orchestrator → one tab), there is
  no drilling to avoid. Explicit props win.

- **Putting a `useXxxQuery` inside the tab body.** This causes the
  query to re-fire on every tab switch, defeating React Query's cache.
  Hoist queries to the orchestrator.

- **Inlining a "small helper" inside a tab that turns out to be 80
  lines.** Extract it as a sibling component in `asset-tabs/` — see
  `GlueSyncPanel.tsx` and `SchemaCopyButtons.tsx` for examples.

- **Skipping tests because "the tab is simple."** Even a placeholder
  tab (like TabChecks) should have at least a render-without-crashing
  test so future changes can't silently break it.

## Worked example: TabChecks (placeholder)

TabChecks is the smallest tab in the codebase. It's a useful template
for understanding the minimum viable tab.

See `ui/src/ee/team/components/asset-tabs/TabChecks.tsx` — 30 lines, no
context fields used (it takes no props), pure empty state.

## Worked example: TabSchema (complex)

TabSchema is the most complex tab. It demonstrates:

- Multiple sub-components (`SchemaCopyButtons`, `GlueSyncPanel`)
- A page-scoped query passed through props (`glueQuery`)
- Conditional rendering with multiple states (empty, conflict banner,
  drift detection, in-sync, etc.)

See `ui/src/ee/team/components/asset-tabs/TabSchema.tsx` for the pattern.

## Questions before you ship

Before opening the PR:

- [ ] Does my tab work when `assetEvents` is empty?
- [ ] Does my tab work when `asset.schema` is empty?
- [ ] Does my tab work when `glue_table` is unset?
- [ ] Does the tab badge show correctly?
- [ ] Are all interactive elements keyboard-accessible (button vs div)?
- [ ] Did I add a CHANGELOG entry under the next version?
- [ ] Does the new file pass `npx tsc --noEmit`?
- [ ] Does `npx vitest run` pass all tests including mine?
- [ ] Did I run the full app and visually verify the new tab?
