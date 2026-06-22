# UI Audit — What's Left to Do

**Date:** 2026-02-21
**Current state:** v69.1 | 349 UI tests | 30+ components

---

## 1. TypeScript Strict Mode (current ~4/10, target 7/10)

### 1.1 `strictNullChecks: false` — MAIN GAP

`tsconfig.json` has `strict: true` but `strictNullChecks: false`. This defeats much of the strict mode benefit — nullable values aren't caught at compile time.

**Impact:** Every `useState(null)`, optional prop access, and API response is unchecked.

**Fix plan:**
1. Enable `strictNullChecks: true`
2. Fix all resulting errors (estimated 80-150 locations)
3. Most fixes are trivial: add `?` optional chaining or `!` non-null assertions where safe

### 1.2 `Record<string, any>` — 35 instances in production code

| File | Count | Notes |
|------|-------|-------|
| `hooks/useAuth.tsx` | 8 | Auth types need proper interfaces |
| `components/BackfillModal.tsx` | 6 | DAG task types need importing |
| `components/AssetLineageFlow.tsx` | 5 | React Flow node types |
| `components/AllRunsView.tsx` | 4 | Run/pipeline types |
| `components/AllTasksView.tsx` | 3 | Task/pipeline types |
| `components/AssetsView.tsx` | 4 | Asset types |
| `components/PipelineDetail.tsx` | 2 | Execution types |
| `components/Notifications.tsx` | 3 | Notification types |
| `components/CalendarView.tsx` | 2 | Execution types |
| `components/DAGGraphFlow.tsx` | 1 | Minimap node types |
| `hooks/usePipelineData.ts` | 1 | Metrics types |

**Fix:** Most of these already have proper types in `types/index.ts` — need to import and use them instead of `Record<string, any>`.

### 1.3 `as any` — 6 instances

All in `AssetLineageFlow.tsx` — React Flow type mismatches with dagre layout. These are harder to fix properly (library type issues).

### 1.4 `AppStateContext` untyped

```ts
const AppStateContext = createContext(null); // No type parameter
```

Needs a proper `AppState` interface.

---

## 2. Accessibility (current ~4/10, target 6/10)

### Already implemented ✅
- ✅ Skip-to-content link (`<a href="#main-content" class="skip-link">`)
- ✅ `focus-visible` styles for all interactive elements
- ✅ `prefers-reduced-motion` media query with animation disable
- ✅ Focus trap in all modals (`useFocusTrap` hook)
- ✅ `aria-live` region on notifications toasts
- ✅ Bell icon has `aria-label` and `aria-expanded`
- ✅ Sidebar: `role="listbox"`, `aria-selected`, `aria-expanded` on groups
- ✅ Header: comprehensive `aria-label` on all buttons
- ✅ `sr-only` class defined in CSS
- ✅ 49 aria attributes, 29 role attributes across components

### 2.1 Missing: More screen reader text

Only 2 `sr-only` usages. Status indicators and icons need text alternatives.

- DAG graph: no keyboard navigation between nodes
- Gantt chart: no keyboard interaction
- Calendar view: no arrow key navigation
- Asset lineage: no keyboard support

### 2.4 Missing: Focus management

- No focus trap in notification dropdown (only in BaseModal)
- No focus return after closing popovers
- No `aria-activedescendant` for virtual lists

### 2.5 Missing: Reduced motion support

No `prefers-reduced-motion` media query. Running task animation may cause issues.

### 2.6 Present (already done)

- ✅ 49 aria attributes across components
- ✅ 29 role attributes
- ✅ Focus trap in BaseModal (`useFocusTrap` hook)
- ✅ `aria-live` region on notifications toasts
- ✅ Bell icon has `aria-label` and `aria-expanded`
- ✅ 9 `tabIndex` usages

---

## 3. Architecture / Code Quality Issues

### 3.1 Components importing `api` directly (violates CLAUDE.md)

Per `CLAUDE.md`: "Components never import `api` directly — use hooks"

| Component | Import | Should use |
|-----------|--------|------------|
| `CalendarView.tsx` | `import { api } from '../utils'` | React Query hook |
| `Notifications.tsx` | `import { api } from '../utils'` | React Query hook |

`AuthGate.tsx` imports `setAuthTokenGetter` which is a setup function, not data fetching — acceptable.

### 3.2 Duplicate keyboard shortcuts registration

Both `App.tsx` (lines 164-174) and `AppContext.tsx` (lines 143-153) register the same shortcuts. One should be removed.

### 3.3 Components without tests — 16 of 30

| Component | Priority | Reason |
|-----------|----------|--------|
| `AllRunsView.tsx` | High | Core view |
| `AllTasksView.tsx` | High | Core view |
| `AssetsView.tsx` | High | Core view, complex logic |
| `DAGGraphFlow.tsx` | Medium | React Flow mocking needed |
| `CalendarView.tsx` | Medium | Direct API calls |
| `GanttChart.tsx` | Medium | SVG rendering |
| `AssetLineageFlow.tsx` | Medium | React Flow |
| `HelpModal.tsx` | Low | Static content |
| `Toast.tsx` | Low | Simple component |
| `BaseModal.tsx` | Low | Wrapper component |
| `Modal.tsx` | Low | Wrapper component |
| `Skeletons.tsx` | Low | UI-only |
| `CountdownTimer.tsx` | Low | Tested via TaskDetailModal |
| `LoginPage.tsx` | Low | Auth flow |
| `UserMenu.tsx` | Low | Auth flow |
| `Providers.tsx` | Low | Wrapper |

---

## 4. Missing Features (from Backlog)

### 4.1 Not started

| Feature | Effort | Backend needed? |
|---------|--------|-----------------|
| **Register_only filter** | Small (1-2h) | No — filter client-side |
| **Execution diff comparison** | Large (2-3d) | Yes — new API endpoint |
| **Cost tracking per pipeline** | Large (2-3d) | Yes — CloudWatch cost data |
| **SLA indicators** | Medium (1d) | Yes — new config + API |
| **Task logs viewer** | Medium (1-2d) | Partial — API exists (`/api/pipeline-logs`) |

### 4.2 Already implemented ✅

| Feature | Status |
|---------|--------|
| Browser notifications | ✅ Working — Notification API + localStorage |
| Keyboard shortcuts | ✅ Partial — Help, Search, Escape, Theme, Refresh |
| Command palette | ✅ Working — Ctrl+K |

---

## 5. Recommended Priority Order

### Phase 1: Quick wins (1 day)
1. ✅ Replace `Record<string, any>` with proper types (35→0 instances)
2. ✅ Replace `Record<string, unknown>` in useAuth (8 auth-related types)
3. ✅ CalendarView migrated to React Query + a11y improvements (keyboard nav, aria-grid)
4. ⬜ Move Notifications to React Query hook
5. ⬜ Add register_only filter to execution dropdowns

### Phase 2: TypeScript hardening (2-3 days)
1. Enable `strictNullChecks: true`
2. Fix all resulting errors
3. Type `AppStateContext` properly
4. Remove remaining `as any` where possible

### Phase 3: Accessibility (2-3 days)
1. Skip-to-content link
2. `prefers-reduced-motion` support
3. Screen reader improvements (`sr-only` labels)
4. Keyboard navigation for Calendar view
5. Focus management improvements

### Phase 4: Missing features (by priority)
1. Task logs viewer (API exists)
2. Register_only execution filter
3. Execution diff comparison
4. SLA indicators
5. Cost tracking
