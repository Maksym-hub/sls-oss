# Changelog

## Unreleased

Open-core refactor — **redeploy scope:** SDK reinstall (`pip install -e .`) for the
`ai` move; console_api `sam deploy` for the route registry, Team-module split, and
the `SLSFLOW_TIER` entitlement parameter; a UI rebuild for the tier restructure. No
schema change; behaviour-preserving (the full build is the same surface).

### Added

- **Tier entitlement for the team↔enterprise boundary (ADR #100).** Both paid
  tiers ship in one build; a deployment-level `SLSFLOW_TIER` (`team`|`enterprise`)
  decides what is enabled at runtime — *not* a physical strip (that remains the
  free↔paid boundary, ADR #98/#99). New `ee/entitlements.py` is the single source
  of truth (capability → tier; enterprise ⊇ team by construction) and exposes the
  `@requires(<cap>)` route decorator; `GET /api/capabilities` reports the
  deployment's tier and capabilities for the UI's `can()`. The paid surface is now
  organised into `ee/team/` and `ee/enterprise/` tier packages composed in
  `ee/__init__.py` (enterprise empty until its first feature). Full paid surface is
  now **58 routes** (was 57). `SLSFLOW_TIER` is a new SAM parameter; the OSS build
  (no `ee/`) ignores all of it. Every current paid feature is Team; the decorator
  applies to 0 routes today — this lands the mechanism so the first Enterprise
  feature is additive, not a re-architecture.
- **UI tier restructure for entitlement (ADR #100, builds on ADR #99).**
  `ui/src/ee/` is reorganised into the same tier packages — `ui/src/ee/team/` and
  `ui/src/ee/enterprise/`. The generator (`gen-ee-active.mjs`) now scans
  `src/ee/*/index.ts` and merges the `surface` every present tier exports into the
  active surface, so a new tier is added by `mkdir` alone (no generator edit). New
  free hooks `useCan` / `useTier` / `useCapabilitiesQuery` (`@/hooks/queries`,
  backed by `GET /api/capabilities`) gate Enterprise components — which ship inside
  the paid bundle but are hidden on a Team deployment — applied to 0 components
  today. free↔paid stays the physical strip; the OSS build is unchanged
  (behaviour-preserving full build).

### Changed

- **SDK: the AI assistant moved to the `slsflow/_ee/` proprietary root (ADR #98).**
  `slsflow/ai/` → `slsflow/_ee/ai/`; the `slsflow-ai` entry point now targets
  `slsflow._ee.ai.cli:main`. The OSS build strips `slsflow/_ee/` (and the entry),
  so the public SDK ships without the Team AI assistant — the only proprietary SDK
  code, and self-contained (core never imported it). `_ee` is a distinct package
  name from the backend's `ee`, so the two proprietary roots never collide on
  `sys.path` and need no symlink.
- **console_api: the five clean Team route modules moved to `ee/` (ADR #98).**
  `backfill`, `notifications`, `slack`, `matrix`, `drift` (and their tests) →
  `console_api/ee/team/`. `main.py` registers the OSS modules unconditionally and
  appends `ee.MODULES` only when the `ee` package is present, so an OSS build
  (which strips `ee/`) serves the free routes and the full build serves all 58.
  Their handlers were also dropped from the OSS `routes/` barrel.
- **console_api: the backend open-core split is complete — OSS surface is now 16
  free routes (ADR #98).** The five *mixed* modules (free + Team handlers in one
  file) were split at the function level — `pipelines_info` (metrics/logs → Team),
  `pipelines_actions` (pause/restart → Team), `tasks` (intervention + runtime
  task-config edit → Team), `executions` (stop/pause/resume/extend → Team),
  `assets` (everything except `list_assets` → Team). Shared helpers stay in the OSS
  `routes/` module and `ee/` imports them (`_build_assets_from_pipelines`,
  `resolve_task_item`). The clean `tokens` module also moved to `ee/team/`; the
  `api_tokens_repo` request-auth check stays in core. Team tests that lived under
  the OSS repo-root (`tests/backend/test_stop_restart`, `test_idempotency`, and the
  source-location smoke checks) moved under `ee/team/tests/`, so the OSS test tree
  imports no proprietary code. The route-table contract was also tier-split: the
  free-subset assert stays in `tests/sdk/test_templates.py` (passes at both 16 and
  58), the full 58-route assert moved to `ee/team/tests/test_route_table_ee.py`, so
  `pytest` is green in both the full build and the OSS-stripped build. Full build
  still serves all 58 routes; dispatch and behaviour are unchanged.
- **console_api routes now self-register via an explicit registry (ADR #97).**
  Introduced `console_api/routing.py` (`Router` + `register(router)` contract).
  `main.py` is now the runner: it holds an explicit `ROUTE_MODULES` list and calls
  each module's `register(router)`; the central `ROUTES` literal is removed and each
  route module owns its routes. The route table is unchanged (58 routes) and
  dispatch is unchanged — this is the seam the open-core split rides on (which
  modules are registered, not file-cutting).

## v91.0 (0.91.0) - 2026-06-16

SDK contract + test-quality pass. No infrastructure change — **redeploy scope:**
SDK/CLI changes need the package reinstalled (`pip install -e .`); nothing needs
`sam deploy` or a UI rebuild. All changes implement already-recorded decisions
(ADR #38, Principles 13/14), so no new ADRs.

### Changed

- **`SmartProvider.switch_provider` now returns a `SwitchOutcome`** instead of an
  in-band sentinel — it used to return either a status `str` or, on a missing API
  key, a 3-tuple `("_NEEDS_KEY", …)`, with the `-> str` annotation hiding the
  tuple case (and the Gemini branch not even following the convention). The CLI
  caller is updated; the missing-key path now works uniformly across all
  providers.

### Fixed

- **`config.py` no longer silently swallows a broken `config.py`.** A project
  config that exists but fails to import previously produced an empty config with
  zero feedback (confusing downstream errors); it now surfaces a visible warning
  naming the file (ADR #38) while staying resilient. The `spec`/`loader` `None`
  case from `importlib` is also guarded, and the spec-loading is de-duplicated
  into one helper.

### Internal

- **SmartProvider state is type-annotated** (`_current: Optional[AIProvider]`,
  `_groq: Optional[GroqProvider]`, …). The `AIProvider` ABC already existed but
  wasn't used in the annotations; this resolves the bulk of the provider
  type-check errors (SDK mypy 426 → ~404) with no runtime change.
- **Backfill upstream tests now exercise the real completeness helpers.**
  `test_backfill_upstream.py` previously stubbed `_scan_completed_partitions` and
  `_partition_task_status` directly, so the completeness computation (ADR #51) was
  never run — a data-layer regression would have passed (Principles 13/14). The
  tests now seed the one external dependency (`executions_repo.query_by_date`)
  with real PipelineTokens rows and let the helpers run; a mutation that breaks a
  field read now fails the suite, as verified. New unit tests cover the config
  and `switch_provider` paths, which had none.

## v90.0 (0.90.0) - 2026-06-15

Pre-OSS-launch hardening. Fixes the broken local quickstart, registers the AI
assistant command, applies the UI security headers that static export was
silently dropping, and moves Next.js off the vulnerable line. **Redeploy scope:**
the CloudFront and `next.config.mjs` changes need `sam deploy` (CloudFront) plus
a UI rebuild + redeploy (`npm ci && npm run build`, then `deploy-ui.sh`); the
SDK/CLI changes need the package reinstalled (`pip install -e .`). The test-only
fixes need nothing.

> ⚠️ After unzipping this archive, confirm the Lambda SDK symlink survived as a
> symlink before `sam build` (some unzip tools turn it into a 16-byte text file):
> `ls -la sam/lambdas/console_api/slsflow` must show `-> ../../../slsflow`.

### Added

- **`slsflow-ai` console script.** The AI assistant (`slsflow/ai/cli.py`) was
  fully implemented and documented but never registered in `[project.scripts]`,
  so the `slsflow-ai` command advertised across the README and
  `docs/tools/AI_ASSISTANT.md` did not exist after a clean install. Now
  registered (`slsflow-ai = "slsflow.ai.cli:main"`).
- **CloudFront security headers (ADR #96).** An
  `AWS::CloudFront::ResponseHeadersPolicy` on the console distribution adds
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  and HSTS. These were declared in `next.config.mjs` but, under
  `output: 'export'`, there is no Next server to apply them — so production
  served none of them. `X-XSS-Protection` was intentionally not carried over
  (deprecated). Cache-Control stays on the S3 objects, where `deploy-ui.sh`
  already sets it correctly.

### Fixed

- **`slsflow-init … --local` scaffolded `pipeline.py`** while `slsflow-validate`
  and `slsflow-output` default to `dag.py`, so the README "Try It Now" quickstart
  failed on the first command with `Pipeline file not found: dag.py`. `--local`
  now writes `dag.py`, matching the interactive/CFN path and the rest of the CLI.
- **`formatDateTime` date-boundary tests were timezone-dependent.** A fixed UTC
  "now" near local midnight made the "Yesterday" case resolve to "Today" on
  machines east of UTC (e.g. UTC+2/+3) — green on UTC CI, red for EU
  developers. The vitest setup now pins `TZ=UTC`.
- **Iceberg asset-helper tests hard-failed without `pyarrow`** (an optional
  extra) instead of skipping on a base install. `_pa_schema` now uses
  `pytest.importorskip("pyarrow")`.

### Security

- **Next.js `16.1` → `16.2`** (resolves to 16.2.9), clearing the high-severity
  Next advisories (middleware/proxy bypass, image-optimization DoS, WebSocket
  SSRF, RSC cache poisoning); `eslint-config-next` bumped in lockstep.
  Production runtime exposure was already low (static export, no Next server),
  but the advisories surface on a fresh `npm audit` at clone time. Remaining
  audit findings are dev-toolchain (`vitest` 2.x → 3.x) and aws-amplify
  transitive deps — deferred to separate, test-validated bumps (see
  `docs/reference/BACKLOG.md`).

## v89.12 (0.89.12) - 2026-06-05

Help modal (in-app docs) accuracy fixes — UI only, requires a UI redeploy.

### Fixed

- **Backfill tab:** hard limit was documented as 5000 partitions; the real
  ceiling is `PARTITION_HARD_LIMIT = 1000` (constants.py, derived from the SFN
  25k history-event limit). Corrected to 1000.
- **Shortcuts tab:** the "List views" group implied `J`/`K`/`Enter` and `/` work
  on every list view. In reality `⌘R` is universal, `/` (focus filter) is wired
  only on Backfills + All Tasks, and `J`/`K`/`Enter` (row highlight/open) only on
  the Backfills list. Each shortcut is now annotated with where it applies.
- **Icons tab:** added the **Pending** task status (it has its own rendered icon
  in `icons.tsx` but was missing from the legend).

## v89.11 (0.89.11) - 2026-06-05

Docs/comment cleanup — no code or behavior change, no redeploy required.

### Fixed

- `auth.py`: the scope-set SSoT note pointed at `ui/src/components/ApiTokensModal.tsx`,
  which no longer exists — corrected to `ApiTokensSection.tsx` (the actual scope
  `<select>`).
- `auth.py`: removed a duplicated "Always-public path prefixes" comment line.
- `docs/features/api-tokens.md`: the "What a PAT is" list claimed "no per-token
  scopes yet", contradicting the "Scopes" section right below it (added in
  ADR #66). Replaced with an accurate one-line scope description.

## v89.10 (0.89.10) - 2026-06-05

The API Tokens list now shows only active tokens — revoked tokens no longer
clutter the list. Backend change; requires a backend redeploy.

### Changed

- **`GET /api/tokens` (`list_tokens`)** filters out revoked tokens. Revocation
  stays a soft-delete (`revoked` + `revoked_at`) so auth still rejects a reused
  token precisely ("token revoked") and the record is retained for a future
  audit log (planned Pro feature) — but the list is for *usable* credentials, so
  revoked ones are hidden. Existing soft-revoked tokens disappear from the UI on
  next load (they had no Revoke button, so could not be cleared otherwise).
- The UI's revoked-token handling (`ApiTokensSection`) is intentionally kept as
  a defensive/forward-compatible path for a possible `?include_revoked` toggle.
- Decision recorded in ADR #65 (token table = active credentials; revocation
  history belongs in the audit log).

## v89.9 (0.89.9) - 2026-06-05

Renamed the API-docs example token env var from `$SLSF_TOKEN` to `$API_TOKEN`
(naming preference). Affects only the curl examples and the intro note in the
in-app API reference (`HelpModal`); no behavior change.

## v89.8 (0.89.8) - 2026-06-05

Docs/UX: the in-app API reference (Help → API) said every request needs a token
but the curl examples omitted it. Now every example shows the auth header.

### Fixed

- **`HelpModal` API reference:** curl examples did not include the
  `Authorization` header, so copying one and running it returned `401` once
  `AUTH_ENABLED=true`. Added a central `withAuthHeader()` injector that prepends
  `-H "Authorization: Bearer $SLSF_TOKEN"` to every example (after `curl` / after
  `-X METHOD`) — one place, no drift across ~25 examples (Principle #1). The
  examples reference `$SLSF_TOKEN`, and the intro now tells the user to export it
  once (`export SLSF_TOKEN=slsf_…`, created under Settings → API Tokens).
- Injector is idempotent (won't double-add if a header is already present) and
  leaves non-curl strings untouched; unit tests added.

## v89.7 (0.89.7) - 2026-06-05

UX: make the API Tokens "Generate" button explain why it is disabled.

### Fixed

- **API Tokens (`ApiTokensSection`):** the "Generate" button is disabled until a
  token name is entered, but nothing told the user why. Added a hover tooltip
  ("Enter a token name first") via the native `title` attribute (the pattern
  already used on the scope `<select>`), shown only while the name is empty.
  Test added asserting the disabled state + hint appear until a name is typed.

## v89.6 (0.89.6) - 2026-06-05

Docs only — no code change, no redeploy required. Records the runtime-config
precedence convention introduced by the v0.89.5 fix so it is not silently reverted.

### Changed

- Added **ADR #94** (`docs/reference/adr-94-runtime-config-precedence.md` + index
  entry in `DESIGN_DECISIONS.md`): `window.CONFIG` (runtime, from `/config.js`) is
  authoritative for all UI config; baked `NEXT_PUBLIC_*` is a build-time fallback
  only. `getConfig()` must stay window-first, and booleans must use `??` (never
  `||` / `? :`) so a baked `'false'` cannot shadow a runtime `true`.
- `CLAUDE.md`: added the ADR #94 row to the Key-ADRs table and a runtime-config
  bullet under UI Patterns.

## v89.5 (0.89.5) - 2026-06-05

Bugfix (the real root cause): the console dropped the `Authorization` header
because `config.AUTH.enabled` was forced to `false` at build time, ignoring the
runtime `window.CONFIG`. This is the actual cause behind the `401 missing bearer
token` symptom that v0.89.3/v0.89.4 only partially addressed.

### Fixed

- **`getConfig()` read auth config env-first, and `next.config.mjs` bakes
  `NEXT_PUBLIC_AUTH_ENABLED` to the string `'false'`.** The logic was
  `process.env.NEXT_PUBLIC_AUTH_ENABLED ? envBool(env) : window.CONFIG…` — but the
  baked value `'false'` is a non-empty (truthy) string, so the env branch was
  always taken and evaluated to `false`, and the runtime `window.CONFIG.AUTH.enabled`
  (`true`, written by `/config.js` from CloudFormation) was ignored entirely.
  `useAuth.isAuthEnabled()` reads `window.CONFIG` first (so the login page showed
  and sign-in worked), but `api.ts` `getAuthHeaders` read `config.AUTH.enabled`
  (`false`) → it never attached the bearer token. With API auth on this surfaced
  as a blanket `401 missing bearer token` and a login↔401↔signOut bounce, even in
  a clean (incognito) session with all Cognito calls returning 200.
- **Fix:** `getConfig()` is now **window-first** — `window.CONFIG` (runtime) is
  authoritative for every field, with `NEXT_PUBLIC_*` as a build-time fallback,
  matching `getApiUrl()` and `isAuthEnabled()`. `AUTH.enabled` uses
  `windowConfig?.AUTH?.enabled ?? envBool(env)` so an explicit runtime `false` is
  still respected while the baked `'false'` no longer overrides a runtime `true`.
- Added regression tests pinning that `window.CONFIG.AUTH.enabled` wins over a
  baked `NEXT_PUBLIC_AUTH_ENABLED='false'`. (The earlier config test passed under
  Vitest because `next.config.mjs`'s env baking does not apply there, so it could
  not catch this — the new case stubs the env explicitly.)
- Retains v0.89.3 (lazy config getters) and v0.89.4 (local-only `signOut`, no
  server-side token revocation). UI-only change; no backend/SAM changes.

## v89.4 (0.89.4) - 2026-06-02

Bugfix: stop `signOut` from revoking the refresh token server-side, which was
poisoning the stored session and making fresh logins fail with
`NotAuthorizedException: Access Token has been revoked` (400).

### Fixed

- **`signOut` used `amplifySignOut({ global: true })` (server-side GlobalSignOut).**
  A 401 from any `/api/*` call auto-triggers `signOut` (AuthGate's auth-error
  callback), so a single dropped request revoked the user's refresh token on the
  server. On the next page load Amplify tried to restore the session with that
  revoked token and got `400 "Access Token has been revoked"`, so login looked
  broken even with correct credentials — and re-running the flow kept re-poisoning
  the session. Combined with the v0.89.3 header bug this produced an unrecoverable
  login↔401↔signOut loop.
- **Fix:** `signOut` is now a **local** sign-out (`amplifySignOut()` — clears this
  browser's tokens, no server-side revocation), so a sign-out (manual or the
  automatic one on a 401) no longer revokes the session for future logins. A
  deliberate "sign out everywhere" can be reintroduced later as an explicit action.
- **Note:** an already-revoked session from before this fix still needs to be
  cleared once in the browser (private window, or DevTools → Application → Clear
  site data) — the server-side revocation can't be undone client-side.

## v89.3 (0.89.3) - 2026-06-02

Bugfix: the console never sent the `Authorization` header, so every `/api/*`
call was rejected (`401 missing bearer token`) once auth enforcement was on.

### Fixed

- **`config.ts` evaluated the runtime config eagerly and froze it.** The default
  `config` export called `getConfig()` once at module load and `Object.freeze`d
  the result. When the JS bundle evaluated this module *before* `/config.js` had
  set `window.CONFIG`, `config.AUTH.enabled` froze to `false`. `useAuth` read the
  flag live from `window.CONFIG` (so the login page showed and sign-in worked),
  but `api.ts`'s `getAuthHeaders` read the **frozen** `config.AUTH.enabled` →
  `false` → it skipped attaching the bearer token entirely. With `AUTH_ENABLED`
  off the gap was invisible (no token needed); flipping it on surfaced it as a
  blanket `401 missing bearer token` and a login↔401↔signOut bounce.
- **Fix:** the default `config` export is now lazy — `API_URL`, `POLL_INTERVAL`,
  and `AUTH` are getters that read `window.CONFIG` on every access, so all
  consumers (`getAuthHeaders`, `useAuth`, `amplifyConfig`) see the runtime values
  regardless of module-evaluation order. Removed the now-unused eager `API_URL`/
  `POLL_INTERVAL`/`AUTH` named exports. UI-only change; no backend/SAM changes.

## v89.2 (0.89.2) - 2026-06-02

Build: Cognito JWT verification is now pure-Python — `sam build` no longer needs
`--use-container`.

### Changed

- **`auth.py` verifies Cognito tokens without the native `cryptography` wheel.**
  RS256 is now checked with the pure-Python `rsa` library (RSASSA-PKCS1-v1_5 +
  SHA-256) over the pool JWKS, with the JWKS fetched/cached via stdlib `urllib`.
  Verification is behaviourally identical (same signature + issuer + expiry +
  app-client binding); the algorithm is still pinned to RS256 before key lookup
  (alg-confusion defense). `requirements.txt`: `PyJWT[crypto]` → `rsa`.
- **Why:** `cryptography` is a native wheel, so it had to be built for Lambda's
  Amazon Linux (`sam build --use-container`); a host-built wheel failed to load
  on Lambda and rejected every valid token (401 once `AUTH_ENABLED=true`). Both
  `rsa` and its dep `pyasn1` ship as `py3-none-any` wheels, so a plain
  `sam build && sam deploy` works on any host with no extra flags. See ADR #65.

## v89.1 (0.89.1) - 2026-06-02

Bugfix: token API calls hit a doubled `/api` path → console showed NOT_FOUND.

### Fixed

- **Token management could never load/create/revoke** (console showed a red
  `NOT_FOUND`). The UI api client base already includes `/api` (`getApiUrl()` →
  `…/dev/api`), so route paths must be relative (`/tokens`), but the token calls
  used `/api/tokens` → resolved to `…/dev/api/api/tokens` → Lambda 404. Changed
  `ApiTokensSection` to call `/tokens`, `/tokens?id=…` (matching every other UI
  call). Backend routes were correct all along; this was purely a client path bug.
- **Help → API tab** base URL/examples were missing the `/dev` stage (would 404
  if copied). Now uses the real deployed base (with stage) when available, and a
  `/dev`-correct placeholder otherwise.

## v89.0 (0.89.0) - 2026-06-02

Console: user dropdown + Settings, and the token UI is now actually styled.

### Added

- **Settings** modal (avatar menu → Settings), a container with a section
  sidebar. API Tokens is the first section; new sections register via a single
  `SECTIONS` array in `SettingsModal.tsx` with no other wiring.

### Changed

- Renamed the avatar-menu item "API Tokens" → "Settings"; token management moved
  into `ApiTokensSection` (logic unchanged) rendered inside Settings.
- Redesigned the user dropdown: avatar + name + email + role header, larger and
  fully padded. Root cause of the old cramped look: `um-*` referenced undefined
  `--space-*` tokens, collapsing all padding/gap — replaced with explicit values.
- Styled the token UI properly. It was unstyled because the modal used an
  unstyled wrapper class and the `at-*` classes had no CSS; added Settings layout
  + token-section CSS to `_modals.css`, plus real `.action-btn--primary/--danger`
  button modifiers (previously undefined).

### Removed

- `ApiTokensModal` (superseded by `SettingsModal` + `ApiTokensSection`).

## v88.1 (0.88.1) - 2026-06-02

Chore: removed a small duplication and documented a deliberate one (post-review).

### Changed

- Consolidated the triplicated `_now_iso()` helper into a single `utils.now_iso()`
  used by `api_tokens_repo` and `routes/tokens` (Core Principle #1). `auth.py`
  keeps its own one-line copy **on purpose** — auth is the low-dependency
  security gate and must not import `utils` (which pulls in `dal`/`config`, and
  would create an import cycle); documented inline.
- Documented the scope vocabulary as a deliberate non-codegen SSoT (ADR #66):
  comments in `auth.py`, the UI picker, and `api-tokens.md` cross-reference each
  other, since codegen covers only the pipeline schema, not console_api constants.

## v88.0 (0.88.0) - 2026-06-02

Feature: per-token scopes — granular authorization for Personal Access Tokens
(ADR #66). Until now any token was a full master key; a token can now be scoped
to least privilege. Builds on ADR #65; takes effect only when `AUTH_ENABLED=true`.

### Added

- **Scope model** (`auth.py`): ordered level `read ⊂ write ⊂ admin`.
  `read` = all GET; `write` = operational mutations (run, pause, backfill,
  retry, task ops); `admin` = destructive (asset delete / delete-orphaned) +
  token management. `required_level(method, path)` derives the needed level
  from the HTTP method plus a 5-entry `ADMIN_ROUTES` override — all 57 routes
  classified (31/21/5) with no hand-maintained table.
- **Enforcement**: `auth.authorize(principal, method, path)` runs in the gate
  after `authenticate()`, returning **403** when a token's scope is below the
  route's required level. `POST /api/tokens` accepts an optional `scope`
  (default `read`); the UI gains a Read-only / Write / Admin picker, and the
  token list shows each token's scope.
- **Slack callbacks** (`/api/action/*`) added to the public allowlist — these
  are token-less link-buttons; a documented conscious cut (ADR #66) and a
  prerequisite for enabling enforcement (otherwise Slack buttons would 401).
- **Tests** (~25): `tests/test_scopes.py` (level derivation across the whole
  route table, authorize allow/deny, legacy→admin, Cognito→admin),
  enforcement-through-`handler` cases in `tests/test_handler_auth_gate.py`
  (read-token→403 on write, write-token allowed, Slack public), token-scope
  cases in `tests/routes/test_tokens.py`, and `ApiTokensModal` scope-picker tests.

### Changed

- Cognito users and legacy PATs (minted before scopes, no `scope` field) are
  treated as `admin`, so enabling scopes never breaks an existing token (#4).

## v87.1 (0.87.1) - 2026-06-02

Hardening of the v0.87.0 auth gate (ADR #65) — done before any enforcement is
turned on. The Cognito JWT path now verifies **offline** instead of calling
`cognito-idp:GetUser`, and the gate itself is covered by an integration test.

### Changed

- **Offline JWT verification** (`auth.verify_cognito_token`): RS256 signature
  check against the pool JWKS via PyJWT, plus issuer, expiry, and **app-client
  binding** (`client_id` for access tokens / `aud` for ID tokens) — previously
  any valid token from the pool was accepted, and every request made a Cognito
  API call. Now there is no per-request Cognito call and no `cognito-idp` IAM
  permission. Adds `console_api/requirements.txt` (`PyJWT[crypto]`), packaged by
  `sam build` (use `--use-container` for the native `cryptography` wheel).
- `AUTH_ENABLED` is now read at **request time** (not import), so the flag is
  testable and a flip takes effect without a re-import.
- `list_tokens` now also returns legacy `_local`-owned tokens (created before
  enforcement) to an authenticated owner, so pre-existing tokens don't vanish
  from the list when auth is enabled.

### Added

- **Enforcement integration tests** (`tests/test_handler_auth_gate.py`): asserts
  through `main.handler` that enabled + no token → 401 (route never reached),
  `/api/health` stays public, a valid PAT reaches the route with the principal
  attached, and disabled requires no token. Closes the "test the verifier but
  not the enforcement" gap (#13). Offline-JWT unit tests (client-id binding,
  bad signature, not-configured) added in `tests/test_auth.py`.

### Removed

- The unbounded `_jwt_cache` (the offline path needs no decoded-token cache;
  PyJWKClient caches signing keys) and the unused lazy `cognito` client in
  `config.py`.

## v87.0 (0.87.0) - 2026-06-02

Feature: API authentication enforcement + Personal Access Tokens (PAT). The
Console API previously had **no** auth enforcement — no API Gateway authorizer
and no token check in the Lambda, despite Cognito existing for the UI login.
This adds a single auth gate at the API entry point that accepts either a
Cognito access token (browser/Amplify) or a slsflow PAT (`slsf_…`, for
scripts/CI/examples), plus token management. Enforcement is **on by default**
(`AUTH_ENABLED=true`) — every non-public request needs a token; disabling it is
a deliberate, reversible step. See
ADR #65 (`docs/reference/adr-65-api-tokens-and-auth-enforcement.md`).

### Added

- **Auth gate** (`console_api/auth.py`): one `authenticate()` check at the top
  of `main.handler`, branching on the `slsf_` prefix. PAT path = SHA-256 hash
  lookup with constant-time compare, revoke + expiry checks; Cognito path =
  `cognito-idp:GetUser` on the access token (cached, no offline JWKS dependency
  — see ADR #65 for the rationale and PyJWT upgrade path). Health/metrics paths
  stay public.
- **PAT storage** (`ApiTokensTable`, `console_api/dal/api_tokens_repo.py`): a
  dedicated `api-tokens` DynamoDB table (PAY_PER_REQUEST), `PK=token_id`, GSI
  `hash-index` (auth lookup) and `owner-index` (list-by-user), TTL on expiry.
  Only the token hash is stored; the plaintext is returned once at creation.
- **Token routes** (`console_api/routes/tokens.py`): `POST /api/tokens`
  (create — returns plaintext once), `GET /api/tokens` (list, hash redacted),
  `DELETE /api/tokens?id=…` (revoke). Route count 54 → 57.
- **Tests** (33): `tests/test_auth.py` (PAT hashing/verify, Cognito branch with
  mocked client, gate routing, public-path allowlist), `tests/dal/
  test_api_tokens_repo.py`, `tests/routes/test_tokens.py` (create returns
  plaintext once and never persists it, list redacts the hash, revoke 404).
- `AUTH_ENABLED` env var and `cognito-idp:GetUser` IAM permission on the
  console-api role.

### Changed

- `docs/features/authentication.md` rewritten — it previously claimed
  "API Gateway validates tokens before forwarding to Lambda", which was false
  (no authorizer existed). Now documents the real gate, dual auth, and the flag.
- API usage examples updated to include `Authorization: Bearer …` (see
  `docs/features/api-tokens.md`, the canonical auth how-to).

### Notes / remaining

- Enforcement ships **on** (`AUTH_ENABLED=true`); the Console UI attaches a token
  on every request and e2e uses a PAT. Set `AUTH_ENABLED=false` to disable.
- Console UI for token management (`UserMenu` → API Tokens modal) and the e2e
  PAT migration shipped in the same feature line (v0.87–0.89).

## v86.0 (0.86.0) - 2026-06-01

Feature: unified Run/Activity feed — `GET /api/runs` now merges Backfills into
the runs list as first-class `kind='backfill'` rows alongside `kind='execution'`
rows, so the Runs page is a single "what happened" view instead of executions
only. Read-side only: no DDB schema, SFN, or write-path change. See ADR #95.

### Added

- `kind` discriminator on every `/api/runs` row (`'execution' | 'backfill'`).
  Execution rows are unchanged plus the tag (additive, backward-compatible);
  Backfill rows carry `backfill_id`, `status` (6-state Backfill vocabulary,
  ADR #56), partition progress (`total/completed/failed/skipped_partitions`),
  `downstream`, `granularity`, `started_by`, and `duration_ms`.
- `_build_backfill_run_rows` in `routes/executions.py` — merges
  `backfills_repo.list_recent()` into the feed, filtered per ADR #95 (status
  literal-match per kind; `pipeline` on `target_pipeline`; `date` within the
  backfill's `partition_keys` range), degrading gracefully if the scan errors.
- Backfill rows in `AllRunsView`: status rendered via the existing
  `bl-status-pill` (reused from the backfills page — no new CSS), partition
  progress in place of an execution id, and a link to the backfill detail page.
  Status filter gains the Backfill vocabulary (pending/completed/partial/
  canceled).
- Tests: `test_executions_runs_feed.py` (10 — kind tags, no double-count /
  internal-record leakage, the three filters, sort, graceful degrade) and 5
  `AllRunsView.test.tsx` cases for backfill-row rendering and navigation.

### Changed

- The Runs page is now the unified Activity feed. The dedicated `/api/backfills`
  endpoint and the Backfills page remain as a backfill-only filtered view —
  nothing was removed.

### Notes

- ADR #95 records the durable boundary rule (a parent object exists iff there is
  group-level state no single execution can hold) and supersedes the
  Run-redesign discovery: the write-side split (Backfill is a first-class
  object; single runs are not) is intentional; only the read side is unified.
- `get_all_runs` rides the existing `backfills_repo.list_recent()` sentinel
  scan; the `started_at` GSI optimization already backlogged for `/api/backfills`
  covers the unified feed too.

## v85.0 (0.85.0) - 2026-05-31

Chore: quality + consistency fixes from the v0.84.1 cross-reviewer audit
(independent review by tech lead + self-audit). Two cross-language drift
surfaces closed, plus dead-code/doc-rot cleanup. No product behavior change.
See ADR #94.

### Added

- Canonical `BackfillUpstream` enum (`off`/`smart`/`force`) in
  `slsflow/constants.py`, codegen-generated into every `constants_generated.py`
  and `ui/src/generated/enums.ts`. The backend validator (`_UPSTREAM_MODES`)
  and the TS `BackfillUpstream` type now derive from it — no more hand-
  maintained copies. It was a 9th, un-gated enum family (the upstream mirror of
  the already-gated `BackfillCascade`); `check-generate-enums` now covers it.
- Canonical `BACKFILL_ERROR_CODES` registry (`slsflow/constants.py`, generated
  into `enums.ts`) and a two-sided gate: backend `test_backfill_error_registry`
  pins the registry to the route's emitted `{'error': ...}` literals; UI
  `backfillErrors.test.ts` asserts the friendly-error map covers every code.
- `make sync-constants` now also diff-guards the 5 `logger.py` copies against
  `_shared/logger.py` (ADR #84 guarded-copy pattern).

### Fixed

- UI backfill error map (`ui/src/utils/backfillErrors.ts`) was missing the v83
  `invalid_downstream*` and v81 `invalid_upstream*` / `upstream_cycle` codes
  (both flagship features fell back to raw backend messages) and still listed
  dead codes. Now covers all 36 route codes; 5 dead removed. The old "parity"
  test asserted a stale hardcoded `criticalCodes` list and stayed green —
  replaced with the generated-registry coverage gate.
- `useRetryFailedBackfillMutation` now invalidates the parent backfill's detail
  query (`['backfill', id]`). `['backfills']` (plural) does not prefix-match the
  singular detail key, so retry-failed previously refreshed the detail page only
  via the 5s poll. Mirrors `useCancelBackfillMutation`.

### Removed / cleaned

- Unreachable `if not out:` branch in `partitions.partitions_covering` (the
  covering loop always yields >=1 key).
- Unused `_DAY_NAMES` set in `granularity.py`; unused `processed` counter in
  `upstream_resolver.resolve_plan` (cycles are rejected earlier).
- `PartitionRange.translate_to` now raises on a finer-than-source target
  instead of silently dropping partitions (it is coarsen-only by design).
- Stale "$0.07 cost estimate" comment in `usePreviewBackfillMutation` (cost was
  removed in v0.78.2, ADR #62).

### Documentation

- Repositioned away from "Airflow-compatible". README now leads with
  *"Orchestration without the orchestrator"* (serverless substrate: nothing to
  run, nothing hidden, asset-aware, pay-per-run). Airflow is described honestly
  as *familiar syntax / ergonomics*, not runtime compatibility; the migration
  guide is reframed as a concept-mapping "Coming from Airflow" guide that states
  what does and doesn't carry over.
- Brought the architecture docs current: added a Design Principles section
  (SFN-first / canonical output store / asset-aware / generated SSoT), a
  lineage-aware Backfill section (upstream smart-fill, downstream cascade,
  partition granularity, tiered execution), documented the canonical output
  store on `pipeline_tokens`, and the generated constants/enums pipeline.
- Fixed the backfill API reference (`docs/operations/API.md`): `cascade` →
  `downstream`, documented the `upstream` field and `upstream_lineage` preview,
  removed the stale cost-estimate fields, and corrected the error-code list to
  match `BACKFILL_ERROR_CODES`.
- Documented partition granularity (ADR #50) in the asset matrix guide.

## v84.1 (0.84.1) - 2026-05-29

Chore: consolidate the UI status vocabulary onto the generated enums
(ADR #93). Closes the last ungated enum-duplication surface found in the
v0.84.0 whole-repo consistency audit. No product behavior change.

### Changed

- `slsflow/codegen/sync_enums.py` now also emits a named-key const object
  `export const TASK_STATUS = { SUCCESS: 'success', ... } as const` in
  `ui/src/generated/enums.ts` (from the canonical `TaskStatus` Enum).
- `ui/src/utils/constants.ts` no longer hand-maintains `TASK_STATUS` — it
  imports and re-exports it from `@/generated/enums` (mirroring the backend's
  `constants_generated` re-export), and derives `TERMINAL_STATUSES` from the
  generated `TASK_TERMINAL_STATUSES`. Consumers unchanged (zero call-site
  churn). `check-generate-enums` now gates the UI status object too — no new
  test needed.

## v84.0 (0.84.0) - 2026-05-29

Lineage-aware asset backfill (ADR #92). Backfilling an asset can now build
its missing same-pipeline upstream, not just re-run the producer task on
assumed-present inputs — fixing the "green asset over red upstream" case in
the Asset Matrix. Corrects the ADR #88 claim that same-pipeline upstream is
always handled by the DAG (true for pipeline backfills, not asset ones). No
SFN change.

### Added

- **`upstream` backfill option** (`off`/`smart`/`force`, asset target only,
  mirrors `downstream`):
  - `off` (default) — rebuild only the producer; inputs assumed present
    (the bug-fix re-run; unchanged behavior).
  - `smart` — also build same-pipeline ancestors whose canonical output is
    missing for a requested partition; the frontier stops at present outputs
    (reads them from storage). `skip_on_backfill` ancestors are never run.
  - `force` — rebuild the entire same-pipeline lineage.
- **Lineage frontier** (`upstream_integration.lineage_frontier` +
  `make_output_missing_adapter`): walks the producer's task dependencies,
  expanding only as far as missing outputs, over the existing per-task
  completeness signal (`executions_repo.query_by_date`).
- **Preview scope disclosure** — preview returns `upstream_lineage`
  (`tasks_to_run × partitions`) and warns when a `skip_on_backfill` ancestor's
  stored output is missing/expired (the ~31-day canonical-output TTL boundary),
  so a one-cell click that expands to a large lineage is never a surprise.
- **UI** — `Upstream` section in the backfill modal (mirrors `Downstream`),
  preview box shows the lineage scope.

### Changed

- Asset backfill with `upstream != off` widens `task_subset` to the lineage
  frontier before the (unchanged) skip-task computation. `skip_completed`
  still gates on the target producer only. `off` is fully backward-compatible.

### Notes

- Cross-pipeline upstream lineage (per-item subsets in the tiered SFN) remains
  deferred to a future release — triggered by a second pipeline (ADR #92).
- No SFN change this release — safe deploy.

### Chore

- Repo-wide ruff cleanup: fixed 36 pre-existing lint findings outside the
  `slsflow/` package (F841 unused locals in snapshot/integration tests and two
  codegen scripts, E712 `== True` comparisons, F811 duplicate imports, E401,
  F541). No behavior change; snapshot tests confirm step registrations intact.
- **Gated ruff repo-wide so this can't recur:** `make lint` now runs
  `ruff check .` (was syntax-only), and CI's lint step widened from
  `ruff check slsflow/` to `ruff check .` — the original gap that let lint debt
  accumulate in tests/codegen/ui.

## v83.0 (0.83.0) - 2026-05-29

Rename the backfill `cascade` option to `downstream` (ADR #91) so the
backfill API reads symmetrically — `upstream` walks producers, `downstream`
fans out to consumers. Pure rename: no behavior change, no SFN change.

### Changed

- **`downstream` is the canonical request/response field** for consumer
  fan-out (values unchanged: `auto`/`all`/`none`). `cascade` is accepted as
  a deprecated alias on input (returns a `deprecated_field` warning) and is
  mirrored on output for one transition window. Validation error codes are
  now `invalid_downstream` / `invalid_downstream_for_pipeline_target`.
- **UI migrated to `downstream`** — the backfill modal, asset/matrix backfill
  launchers, and backfill list/detail now send and read `downstream`; modal
  and help copy say "downstream". Internal plumbing (the DDB record field,
  the SFN input key, the SFN template) keeps the name `cascade` — it is
  invisible to users and renaming it would force a needless second
  consecutive SFN-changing deploy (see ADR #91).

### Notes

- No SFN change this release — safe deploy, no in-flight backfill disruption.
- Existing API clients that send `cascade` keep working (alias); migrate to
  `downstream` at leisure.

## v82.0 (0.82.0) - 2026-05-29

Upstream smart-fill Phase 3 — the bulk-backfill SFN now executes the
cross-pipeline tiered plan (ADR #90). With `upstream=smart|force`, missing
cross-pipeline upstream is built before the target, in dependency order. The
Phase 2 `upstream_execution_pending` 422 is removed.

### Added

- **Tiered SFN execution (nested Map).** The bulk-backfill state machine
  runs an outer Map over dependency tiers with `MaxConcurrency=1` (strict
  order, deepest upstream first) wrapping an inner Map over each tier's items
  with `MaxConcurrency=max_parallel` (unchanged per-tier parallelism). A
  one-tier plan (`upstream=off`) is behaviorally identical to before.
- **Reused-skip.** A smart-fill item whose upstream partition already exists
  is routed to a Pass — not executed, not counted as work.
- **Tier failure gate.** At each tier's start the SFN re-reads the backfill
  record; if canceled or any earlier tier failed, the tier is skipped. A
  downstream/target is therefore never run on top of a failed upstream (no
  silent wrong data). Coarse by design — per-partition gating is a documented
  follow-up (ADR #90 Phase 3b).
- `upstream_integration.plan_to_sfn_tiers` / `single_tier` /
  `count_executable` — convert a resolved plan (or the no-upstream case) into
  the SFN `tiers` input and count executable (non-reused) partitions.

### Changed

- `start_backfill` now sends `tiers` to the SFN (one unified path; the
  single-pipeline case is a one-tier plan — no separate legacy code path).
  `total_partitions` counts executable items. `retry_failed` is unaffected —
  it delegates to `start_backfill` and defaults to `upstream=off` (one tier).
- Child-execution-name length guard now checks the worst case across all
  pipelines + partitions in the plan (cross-pipeline names vary per item).

### Deploy note

⚠️ The bulk-backfill state machine changed this release. Cancel/restart any
in-flight backfills at deploy time (in-flight executions started with the old
input shape will not match the new SFN).

## v81.0 (0.81.0) - 2026-05-29

Upstream smart-fill foundation — the cross-pipeline backfill resolver
(Phases 1–2 of ADR #88), built on the partition-mapping model of ADR #87
(Dagster prior art) and the asset-centric concept of ADR #86. Authoring DSL
is unchanged; this is additive and backward-compatible (the `upstream`
option defaults to `off`).

### Added

- **`slsflow.upstream_resolver`** — pure cross-pipeline tiered resolver:
  `resolve_plan` returns dependency-ordered tiers (deepest upstream first),
  with cycle detection, diamond dedup, `smart`/`force` reuse modes, collected
  warnings, and per-item `dag_hash` recording (ADR #89 R5). Tiering is
  O(V+E) via Kahn propagation.
- **`slsflow.partitions.partitions_covering`** — intersecting-window
  partition mapping (ADR #87): 1↔1 for equal granularity, the covering set
  for cross-granularity (e.g. one daily target over 24 hourly upstream).
- **`upstream` backfill option** (`off`/`smart`/`force`, top-level, asset
  targets only). `off` is the default and preserves prior behavior exactly.
  In preview, the resolved tiered plan is returned (`upstream_plan`,
  `upstream_build_required`). A reserved window-offset surface (ADR #89 R2)
  is parsed but warns "not yet honored" until a later release.
- **`console_api/upstream_integration`** — builds the cross-pipeline
  `AssetGraph` from the pipeline registry (same-pipeline edges excluded — the
  DAG handles those) and an `exists` adapter over `_scan_completed_partitions`.

### Changed

- `start_backfill` resolves the upstream plan when `upstream != off` and
  draws an honest Phase 2/3 boundary: a real start that requires
  cross-pipeline upstream to be *built* returns 422 `upstream_execution_pending`
  with the plan attached, rather than silently running the target on missing
  upstream (no silent wrong data). Cross-pipeline tiered *execution* lands in
  the next release (Phase 3 SFN work).
- Extracted `_load_expected_tasks` helper (shared by the skip_completed
  pre-flight and the upstream exists-adapter).

## v80.1 (0.80.1) - 2026-05-28

Fix a backfill-blocking SFN template bug and add CI evaluation of skip-task
template JSONata (ADR #85).

### Fixed

- **Skip-task check threw `States.QueryEvaluationError` on non-empty
  `skip_tasks`** — `Check_Should_Skip_Task` in the run_task helper template
  used `$contains($states.input.skip_tasks, …)`, but `$contains` is a JSONata
  string function and `skip_tasks` is an array, so any task given a non-empty
  skip list (task-subset / skip-completed backfills, ADR #51) failed with a
  signature error and cascaded skips to its descendants. Replaced with the
  array-membership `in` operator (matching the dependency_wrapper template).
  Pipeline/asset backfills that pass a skip list now run correctly.

### Added

- **CI evaluation of skip-task template JSONata** —
  `tests/sdk/test_sfn_skip_task_jsonata.py` evaluates every skip-task Choice
  condition across the SFN templates (via `jsonata-python`, new dev
  dependency) against representative inputs, asserting no runtime error and
  correct membership — plus a static guard that `$contains()` is never
  applied to the `skip_tasks` array. Closes the gap that let malformed
  template JSONata ship without CI catching it. The static check runs even
  without `jsonata-python` installed (dependency-free backstop).
- **Defensive `$string()` wraps** in `Save_Success`, `Save_Canonical_Output`,
  and `Interactive_Slack` — `$length()` calls on `task_output` / `cause`
  fields now go through `$string()` first (idempotent on strings, graceful
  on non-strings), removing the latent dependency on upstream invariants
  flagged by the exhaustive audit. Production behavior unchanged.
- **`scripts/audit_jsonata.py` (run via `make audit-jsonata`)** — exhaustive
  JSONata edge-case audit: evaluates every `{% %}` expression across all
  SFN templates (~11k evaluations) against 35 baseline + aggressive variants
  (null fields, wrong types, unicode, special chars, populated arrays,
  error-as-object). Maintenance tool, not in CI — run before releases or
  after non-trivial template edits.

### Deploy

Backend (SFN template). After deploy, **cancel the stuck backfill and start a
new one** — in-flight executions under the old template are not retroactively
fixed.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.80.1.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

## v80.0 (0.80.0) - 2026-05-28


Backfill status consolidation + correctness hardening (ADR #83). Removes
the root cause of the ADR #81/#82 bug class — the "is this backfill done /
what's its terminal status" rule was implemented in several places and
drifted. Now: one authority, one typed accessor, one CI parity check.

### Added

- **`slsflow.backfill_status`** — the single Python authority for the
  terminal-status rule: `finalize_status(completed, failed, *, canceled)`
  and `all_map_done(total, completed, failed)`. Documents the counter
  semantics (total = to-run count; skipped is pre-flight, never in the
  done-check).
- **Backfill status parity drift check** —
  `slsflow.codegen.check_backfill_status_parity` (`make
  check-backfill-parity`). Verifies the bulk_backfill SFN Finalize JSONata
  encodes the same rule as the canonical Python function, and that it
  never references `skipped` in the aggregate (ADR #82 guard). Enforced via
  the SDK test suite.
- **`BackfillRecord`** value-object (`dal/backfills_repo.py`) — typed,
  read-only view over a Backfill DDB item. Centralizes id resolution,
  typed counters, status predicates (`is_active`/`is_terminal`/`map_done`),
  `derived_status()`, and `age_seconds()`. Consumers no longer read raw
  dict keys or re-derive status ad-hoc.
- **BackfillStatus set SSoT completed** — removed the manual class-level
  `BackfillStatus.TERMINAL`/`.ACTIVE`/`.ALL` (duplicated the codegen
  `BACKFILL_TERMINAL_STATUSES`/`BACKFILL_ACTIVE_STATUSES`; `.ALL` was dead).
  All 6 consumers migrated to the generated, slsflow-sourced sets — the
  terminal/active sets now have a single source, matching the TaskStatus
  migration (ADR #77).
- **`models/` layer** — `BackfillRecord` extracted from `dal/backfills_repo.py`
  to `models/backfill_record.py` so the DAL is persistence-only and the
  domain value-object lives in its own layer.
- **Class-level enum SSoT — full consolidation** — `console_api/constants.py`
  no longer defines any duplicated status class. TaskStatus, TriggerRule,
  PipelineStatus, BackfillStatus, AssetOperator (and the TASK_*/BACKFILL_*
  sets) are all re-exported from the codegen-generated module (single
  source). The divergent members that blocked this — `TriggerRule.DEFAULT`/
  `EARLY_TRIGGER`/`WAIT_ALL`, `PipelineStatus.PAUSED`/`ABORTED` — were
  verified to be dead (zero references) and removed (CLAUDE.md #1); canonical
  `TaskStatus` is a superset so re-export is non-breaking. `_shared`/
  `evaluate_deps` keep their classes manual (standalone-test resilience) but
  dead members were removed and a new guard,
  `slsflow.codegen.check_shared_constants` (run by `make sync-constants`),
  verifies they never drift from canonical. The old text-based sync-constants
  check was replaced with this value-based one.

### Changed

- `_compute_derived_backfill_status` now delegates to the canonical rule
  (kept as a thin shim); `_reconcile_backfill_status` / `_heal_backfill_status`
  refactored onto `BackfillRecord`. Removed the standalone
  `_backfill_age_seconds` and 6 copies of
  `item.get('backfill_id') or item.get('execution_name')`.

### Fixed

- **Child execution name length** — `start_backfill` now rejects
  (`child_name_too_long`, 422) when `{pipeline}-{partition}-bf-{hex8}`
  would exceed SFN's 80-char execution-name limit, instead of every
  partition silently failing inside the Map.

### Decisions

- **ADR #84** — ratifies how the SDK / shared constants reach each Lambda:
  guarded copy now (drift closed by `check_shared_constants`), PyPI as the
  target end-state, Lambda Layer as fallback; resolved as one packaging
  migration, not piecemeal for constants. No code change — records the
  v0.80.0 state as intentional.

### Audit (documented, not changed)

- Hourly partition keys (`YYYY-MM-DDTHH`) are SFN-name-safe — verified, not
  a bug.
- `.sync:2` child Retry likely re-attaches to the same failed execution
  (ineffective child-level retry). Low impact; backfill-level retry-failed
  is the real path. Specified in BACKLOG with candidate fixes — not edited
  blind, as it touches orchestrator JSONata that needs a deploy smoke test.
- Backlog hygiene: marked two already-implemented items done (real
  skip_completed pre-flight; partition_start from asset metadata).

### Tests

| Suite | Was | Now |
|---|---|---|
| console_api | 356 | **366** (+10) |
| SDK Python | 912 | **923** (+11) |
| **All gates** | green | **green** |

### Deploy

Backend-only (console_api Lambda; the SDK `slsflow` is bundled). No UI
changes. No API contract or behavior change for valid inputs.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.80.0.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

## v79.10 (0.79.10) - 2026-05-28

Correctness fix from a full backfill-subsystem audit (ADR #82).

### Fixed

- **Premature-terminal derived status.** `_compute_derived_backfill_status`
  added the pre-flight `skipped_partitions` count to its "processed" sum,
  but `total_partitions` is the to-RUN count (excludes pre-skipped) and
  the SFN Map increments only completed/failed. A partially-run backfill
  with skip_completed skips could therefore be reported terminal while
  still running. Combined with v0.79.9, this could heal a *running*
  backfill to terminal and let a concurrent backfill start (duplicate
  writes). Fix: `processed = completed + failed`. `skipped_partitions`
  stays for display only. The SFN's Finalize math was always correct;
  the Python mirror had drifted.
- **Retry eligibility uses reconciled status.** `retry_failed` checked the
  raw stored status, so a zombie parent stored `running` but effectively
  failed/partial was rejected as `not_eligible` even though the UI offered
  Retry. Now routed through `_reconcile_backfill_status` (which also
  self-heals the parent).

### Audit (reviewed, no change)

- SFN sets `is_backfill: true` on all child executions (pipeline + asset).
- No double-count of failures (Catch vs Choice are mutually exclusive).
- Canceled finalization honors `canceled` regardless of counters.
- DAL discriminators (`record_type`, sentinel pipeline) consistent.
- No client-side status-derivation duplicate (removed in v0.79.1).

### Audit (logged to backlog)

- Hourly partition keys in child SFN execution Name (verify format before
  enabling hourly).
- `.sync:2` Retry reuses execution Name+Input (may not produce a fresh
  attempt; needs live test).
- `force`/`incremental` options accepted-but-unused (API compat).

### Tests

| Suite | Was | Now |
|---|---|---|
| console_api | 355 | **356** |
| SDK Python | 912 | 912 |
| **All gates** | green | **green** |

The test `test_skipped_counts_toward_processed` (which had codified the
bug) was rewritten to assert correct semantics; added a retry-on-zombie
eligibility test.

### Deploy

Backend-only (console_api Lambda). No UI changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.10.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

## v79.9 (0.79.9) - 2026-05-28

Bug fix: **can't start a backfill — `concurrent_backfill_active` even
with nothing running** (ADR #81). A dead/stuck backfill was permanently
blocking all new backfills for its pipeline (including asset-tab
backfills).

### Fixed

- **Zombie-backfill reconciliation.** A backfill whose `bulk_backfill`
  SFN died before its Finalize step stays `running`/`pending` in DDB
  forever. The concurrency guard checked that raw status, so it blocked
  every new backfill for the pipeline. New `_reconcile_backfill_status`
  resolves the effective status:
  - **A** — derive from partition counters (no AWS call): all partitions
    processed → terminal.
  - **C** — if counters inconclusive, describe the SFN execution; a
    terminal or missing execution means it can't still be running.
  - **B** — self-heal: stamp the zombie terminal in DDB (idempotent,
    conditional), so it stops blocking and the "active backfills" badge
    clears.
- **Concurrency guard** now filters raw-active backfills through
  reconciliation — only genuinely running/pending ones block.
- **List + detail** report the reconciled status, so the badge and guard
  self-heal on any list/detail load (no manual cancel needed).
- Fail-closed on unexpected SFN errors (throttle/IAM): the backfill stays
  considered active so the guard keeps protecting against duplicate
  writes. `ExecutionDoesNotExist` heals to failed only when the record is
  older than a 120s grace window, so a just-created backfill whose SFN
  start hasn't propagated yet is never wrongly stamped failed.

This fixes backfills from every entry point (pipeline / asset / cell /
task) since they share the same guard.

### Immediate effect on a stuck instance

The first time the Backfills list (or any backfill detail) loads after
deploy, a zombie record is stamped terminal and the "Backfills N" badge
self-corrects. New backfills work immediately.

### Added

- `_reconcile_backfill_status`, `_describe_backfill_sfn`,
  `_heal_backfill_status` helpers in `routes/backfill.py`.
- 7 tests: `TestZombieReconciliation` (counters-heal, SFN-timeout-heal,
  execution-gone-heal, just-started-not-healed race guard,
  genuinely-running-blocks, SFN-error-fails-closed) +
  `TestListBackfills.test_list_self_heals_zombie_status`.

### Documentation

- **ADR #81** — root cause (computed truth vs. enforced truth split),
  the A→C→B resolution order, fail-closed rationale, why reconcile on
  read too, and the lesson: every consumer of a derived value must go
  through the same derivation or they drift.

### Tests

| Suite | Was | Now |
|---|---|---|
| console_api | 348 | **355** (+7) |
| SDK Python | 912 | 912 |
| **All gates** | green | **green** |

### Deploy

Backend-only (console_api Lambda). No UI changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.9.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

### Sanity

After deploy, open the Backfills tab once (heals any zombie + clears the
badge), then start a backfill from an asset — it should succeed instead
of returning `concurrent_backfill_active`. To confirm the guard still
protects real concurrency, start two backfills for the same pipeline in
quick succession: the second should be rejected while the first is
genuinely running.

## v79.8 (0.79.8) - 2026-05-28

Bug fix + cleanup: **backfill modal no longer overflows the viewport**
(ADR #80). The footer action buttons were unreachable when Options +
the task list were expanded.

### Fixed

- **Modal height cap.** Root cause was a class mismatch: the modal used
  `.bf-modal` (only `max-width`, no height cap), while the correct
  height-cap CSS sat under a dead `.bf-backfill-modal` class no component
  used. Moved the cap to `.bf-modal`: `max-height: calc(100dvh - 2rem)`,
  flex column, scrollable `.modal-body`, pinned header + footer. The
  Cancel / Preview / Start Backfill buttons now always stay visible;
  only the body scrolls.
- **Responsive task list.** `.bf-task-list` max-height now
  `min(180px, 24vh)` — shrinks on short screens so it never dominates
  the modal; the body scroll handles the rest.
- **All screen sizes.** Shared modal overlay gains `padding: 1rem` +
  `box-sizing: border-box` so no modal touches the viewport edge on
  small screens. `dvh` units mean a mobile browser's collapsing URL bar
  doesn't push the footer off-screen.

This fixes the overflow for every backfill context (pipeline / asset /
cell / task) since they all share one `BackfillModal`.

### Removed

- **220 lines of dead CSS** — the entire pre-v0.78 modal stylesheet
  (`.bf-backfill-*` × 17 classes + `.bf-nav-pills--plain`), unreferenced
  by any component since the modal redesign. The CSS comment had flagged
  these for removal "after old BackfillModal removed (Phase 5c)"; the
  removal finally happened. Live `.bf-option-*` / `.bf-task-*` rules
  interleaved between the dead blocks were preserved.

### Added

- 2 layout-contract guard tests in `BackfillModal.test.tsx`: modal
  container has `bf-modal` class (catches the rename that caused this
  bug), and `.modal-body` + `.modal-footer` are present (the elements
  the height-cap CSS depends on).

### Documentation

- **ADR #80** — root cause (class mismatch hiding behind dead CSS),
  the dvh/calc/min responsive approach, why the shared-overlay change
  is safe for all modals, and the lesson: renames must move CSS rules,
  and dead CSS hides working CSS.

### Tests

| Suite | Was | Now |
|---|---|---|
| vitest | 833 | **835** (+2) |
| Python total | 1358 | 1358 |
| tsc strict | 0 errors | **0 errors** |
| **All gates** | green | **green** |

### Deploy

UI-only release. No backend changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.8.zip
cd ui && npm run build && ../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity

Open a backfill modal (pipeline DAG → Backfill, or asset/cell), expand
Options, and confirm: the Start Backfill / Preview / Cancel buttons stay
visible at the bottom while the middle scrolls. Resize the window short
(or test on a laptop / phone) — the modal should never run off the top
or bottom edge, and the footer should always be reachable.

## v79.7 (0.79.7) - 2026-05-27

UI consistency fix: **single source of truth for the backfill icon**
(ADR #79). The backfill affordance used three different icons across
the console (Rocket / Rewind / History); now it's one icon, owned in
one place. Canonical icon: **Rewind** (Mike's choice).

### Changed

- **`ActionIcons.backfill`** is now THE backfill icon (`Rewind`),
  documented as canonical in `utils/icons.tsx`.
- **`ContextIcons.backfill`** aliases `ActionIcons.backfill` instead
  of hardcoding `History` — removes the divergent second definition.
- **10 call sites** across 8 files migrated from raw lucide imports
  (`Rocket` / `Rewind` / `History`) to `ActionIcons.backfill` /
  `ContextIcons.backfill`:
  - `Header.tsx` (nav tab)
  - `BackfillsListPage.tsx` (list header)
  - `BackfillModal.tsx` (modal header — "Backfill cell/asset")
  - `BackfillDetailPage.tsx` (detail header)
  - `AllRunsView.tsx` (run badge)
  - `PipelineDetail.tsx` (DAG "Backfill" button)
  - `Notifications.tsx` (item icon + toast icon)
  - `HelpModal.tsx` (legend entry + section header)

### Removed

- Dead `History` lucide icon import + re-export from
  `utils/icons.tsx` (no longer referenced after migration).

### Not changed (deliberate)

- **`Rocket` stays** for its real meaning — `ActionIcons.run`, the
  Run button, run notifications, DAG-trigger nodes, the run help
  legend entry. Rocket = "launch/run", the opposite of backfill;
  conflating them was the original bug.

### Added

- **`utils/icons.test.tsx`** — 3 guard tests locking the SSoT:
  `ContextIcons.backfill === ActionIcons.backfill` (same reference),
  backfill defined, backfill ≠ run. Catches re-divergence at test
  time.

### Test infrastructure

- Component test mocks for `@/utils/icons` changed from
  `ActionIcons: () => null` (function) to
  `new Proxy({}, { get: () => () => null })` (object resolving any
  key to a null component) — required because code now accesses
  `ActionIcons.backfill`. Applied to 15 + 14 test files; HelpModal
  mock gained a `ContextIcons` entry.

### Documentation

- **ADR #79** — SSoT rationale, the indirection pattern, what stays
  Rocket and why, guard-test design, lesson on structural vs.
  find-replace fixes for consistency.

### Tests

| Suite | Was | Now |
|---|---|---|
| vitest | 830 | **833** (+3 guard) |
| Python total | 1358 | 1358 |
| tsc strict | 0 errors | **0 errors** |
| **All gates** | green | **green** |

### Deploy

UI-only release. No backend changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.7.zip
cd ui && npm run build && ../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity

After deploy, the backfill icon (Rewind `«`-style) should be
identical in: the nav "Backfills" tab, the backfill list/detail
page headers, the "Backfill cell/asset" modal headers, backfill
run badges in All Runs, backfill notifications, the pipeline DAG
"Backfill" button, and the help legend. No rocket icons on any
backfill surface.

## v79.6 (0.79.6) - 2026-05-27

Closes BACKLOG item: **SFN template literals → canonical**. Reframed
from "generator" to "drift checker" after investigation (ADR #78).

### Added

- **`slsflow/codegen/check_sfn_templates.py`** — scans all
  `sam/sfn_templates/**/*.json` and validates embedded status
  string literals against canonical `slsflow.constants.TaskStatus`.
  Catches:
  - Typos in JSONata `$status = "value"` writes.
  - Status values removed from canonical but still referenced
    in templates.
  - Values added to templates without a corresponding canonical
    entry.
- **`make check-sfn-templates`** Makefile target. Use in CI to
  block merges with template drift.
- **`tests/sdk/test_sfn_template_drift.py`** — 11 tests covering
  detection patterns, allowlists, and the real-template
  consistency invariant.

### Why drift-check not substitution

Investigation showed mechanical substitution into JSONata
expressions like `$status = "{TASK_STATUS_FAILED}"` would:
- Break template readability for humans.
- Require a custom SAM deploy pre-processor.
- Add complexity for zero correctness benefit beyond what
  validation already provides.

The drift checker achieves SSoT enforcement with ~2 hours of
implementation vs. ~1 day for substitution. Same class of bugs
caught either way.

### Detection scope

Two patterns scanned:

1. **Pass-state writes:** `"status": "<value>"`
2. **DDB status updates:** `":status": {"S": "<value>"}` (also
   `:newstatus`, `:s` variants)

Two allowlists for exemptions:
- **`ALLOWLIST`** — JSON field names that pass status-shape
  (`name`, `value`, `task`, etc.).
- **`HELPER_OPERATION_STATUSES`** — helper Lambda Output values
  (currently just `restarted` from `restart_task`).

### Documentation

- **ADR #78** — drift checker vs. substitution generator decision,
  pattern scope, allowlist justification, lesson on choosing
  validation over generation when output is hand-authored.

### Tests

| Suite | Was | Now |
|---|---|---|
| SDK Python | 901 | **912** (+11) |
| Other | unchanged | unchanged |
| **All gates** | green | **green** |

The committed SFN templates pass the drift check unchanged
(`12/14 canonical values referenced` — `pending` and `succeeded`
not in any template, which is fine).

### Deploy

Pure infrastructure release — no Lambda code changed. CI will
gain the new `check-sfn-templates` step.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.6.zip
# No backend or UI rebuild needed; this is repo tooling.
# If CI was previously running gates manually, add:
make check-sfn-templates  # alongside existing make targets
```

### Sanity

After deploy, intentionally typo a status value in a template:

```bash
sed -i 's/"failed"/"faiiled"/g' sam/sfn_templates/helpers/run_task/sfn.tpl.json
make check-sfn-templates  # should fail with "faiiled" listed
git checkout sam/sfn_templates/helpers/run_task/sfn.tpl.json
```

## v79.5 (0.79.5) - 2026-05-27

Completes the backend SSoT enum migration deferred in ADR #72:
**TaskStatus class-level sets → generated module-level constants**
(ADR #77).

### Changed

- **Removed class-level sets** from hand-written `TaskStatus` class:
  `TERMINAL`, `SUCCESS_STATES`, `FAILURE_STATES`, `ACTIVE`,
  `WAITING_STATES`, `STOPPABLE` (in both
  `sam/lambdas/_shared/constants.py` and
  `sam/lambdas/console_api/constants.py`).
- **Re-exports module-level sets** from `constants_generated` so
  callers can `from constants import TASK_TERMINAL_STATUSES` without
  knowing about the generated module.
- **8 call sites migrated** from `TaskStatus.TERMINAL` → 
  `TASK_TERMINAL_STATUSES` (and similar) across `evaluate_deps`,
  `console_api/task_actions`, `console_api/routes/executions`,
  `console_api/routes/tasks`.
- **`evaluate_deps/constants_generated.py`** now generated too —
  added to codegen `PY_TARGETS`. Required because the synced
  `constants.py` imports from it.

### Behavior impact

`TASK_TERMINAL_STATUSES` now includes both `'success'` and
`'succeeded'` (canonical from `slsflow.constants` had both;
hand-written backend only had `'success'`). Tests updated to
reflect new set membership.

Code that did `status in TaskStatus.TERMINAL` previously didn't
recognize `'succeeded'` as terminal — silently buggy on Airflow-3-
style status writes. After v0.79.5, both forms recognized.

### Documentation

- **ADR #77** — "TaskStatus class-level sets → generated module-level".
  Mapping of 8 sites, fallback strategy in `_shared/constants.py`,
  behavior change on `'succeeded'` recognition, lesson on honest
  deferral vs. tech debt.

### Tests

| Suite | Was | Now |
|---|---|---|
| Python total | 1347 | **1347** |
| vitest | 830 | 830 |
| **All gates** | green | **green** |

2 smoke tests updated for new constant names; 3 evaluate_deps
TestStatusCategories tests updated for canonical set values
(now include `'succeeded'`).

### Deploy

Backend-only. All 5 helper Lambdas + console_api need the new
`constants_generated.py` in their deploy artifact.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.5.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

### Sanity

After deploy, downstream-failure detection in `evaluate_deps` for
tasks that completed with status `'succeeded'` (Airflow 3 form):
they're now counted as success-terminal. No specific test query
needed — covered by existing handler tests.

## v79.4 (0.79.4) - 2026-05-27

Closes Philosophy compliance gap from v0.78.10 audit (ADR #76):
**print() → structured logger** in all 4 helper Lambdas. Was tracked
in BACKLOG as "opportunistic".

### Added

- **`sam/lambdas/_shared/logger.py`** — canonical copy of the
  structured JSON logger (was `console_api/logger.py` only).
- **`logger.py` per-Lambda** — copied to evaluate_deps,
  notify_asset_subscribers, check_assets, query_subscriptions.
- **`make sync-loggers`** target with CI drift detection.

### Changed

- **21 `print()` calls replaced** with `log.info/warn/error`
  structured calls across 4 Lambdas:
  - evaluate_deps: 3 sites
  - notify_asset_subscribers: 9 sites
  - check_assets: 5 sites
  - query_subscriptions: 4 sites
- CloudWatch Insights queries now work uniformly across all
  Lambdas (filter by level + fn).

### Tests

No new tests — pure substitution. All existing tests pass.

| Suite | Was | Now |
|---|---|---|
| Python total | 1347 | **1347** |
| vitest | 830 | 830 |
| **All gates** | green | **green** |

### Deploy

Backend-only. All 5 Lambdas (4 helpers + console_api) ship with
identical `logger.py`.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.4.zip
cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

### Sanity

CloudWatch Insights query that should return data after deploy:
```
filter level = "WARN" and fn = "_check_freshness"
sort @timestamp desc
limit 20
```

## v79.3 (0.79.3) - 2026-05-27

Stage 7 of the multi-release alignment plan — **DAL migration for all
4 helper Lambdas** (ADR #75). Closes Q3 from the multi-release plan
(Mike's choice: "все під DAL").

### Added

- **`evaluate_deps/dal/__init__.py`** — `TokensRepo` with
  `batch_get_statuses`, `get_status_one`, `is_paused`. Preserves the
  BatchGetItem + retry-on-UnprocessedKeys logic verbatim.
- **`notify_asset_subscribers/dal/__init__.py`** —
  `SubscriptionsRepo` (`list_for_asset`, `delete`) +
  `AssetEventsRepo` (`query_recent`).
- **`check_assets/dal/__init__.py`** — `AssetEventsRepo`
  (`query_recent`, `get_latest`) + `SubscriptionsRepo`
  (`put_asset_subscription`, `delete`).
- **`query_subscriptions/qs_dal/__init__.py`** — `SubscriptionsRepo`
  (`list_for_dependency` with internal pagination). Named `qs_dal/`
  instead of `dal/` to avoid sys.path collision with console_api's
  `dal` package during SDK-side tests. ADR #75 has the full story.
- **`query_subscriptions/test_query_subscriptions.py`** — new test
  suite (11 tests).

### Changed

- **4 Lambdas migrated from raw boto3 to DAL.** Per CLAUDE.md "DAL
  repository pattern for all DynamoDB access". The architectural
  audit (v0.78.12 conversation) found this rule was honored only by
  console_api; v0.79.3 brings the other 4 in line.
- **`_get_dynamodb()` removed** from `evaluate_deps`,
  `notify_asset_subscribers`, `check_assets`. The lazy-init logic
  moved into the DAL's module-private `_resource()`.
- **Tests rewritten in place** — 29 patches across 3 Lambdas
  converted from `mock_dynamodb.Table().query.return_value = {...}`
  chains to `mocker.patch.object(repo, 'method', return_value=...)`.
  SDK-side `tests/backend/test_query_subscriptions.py` also rewritten
  for the DAL pattern.

### Not changed (deliberate)

- **`console_api/dal/`** unchanged — already followed the pattern.
- **No shared DAL layer.** Each Lambda's DAL is independent (per-
  Lambda deploy packages); a shared `_shared/dal/` would be premature
  abstraction. If three Lambdas grow to query the same table with
  the same access pattern, that's when to extract.
- **SFN/EventBridge clients stay inline** (`_get_sfn()` in
  notify_asset_subscribers). DAL pattern is for DynamoDB; symmetry
  isn't worth the abstraction cost for single-client services.
- **`ui_bootstrap`** — no DB access; nothing to migrate.

### Documentation

- **ADR #75** — "DAL repository pattern for all 4 helper Lambdas".
  Full migration plan, the per-Lambda decision, the `qs_dal/`
  naming caveat with the three options considered, what's
  explicitly NOT done, and the lesson on test infrastructure
  vs. package shadowing.

### Tests

| Suite | Was | Now | Δ |
|---|---|---|---|
| SDK Python | 900 | **901** | +1 (AccessDenied passthrough test) |
| console_api | 348 | **348** | 0 |
| evaluate_deps | 56 | **56** | 0 (6 rewritten) |
| notify_asset_subscribers | 12 | **12** | 0 (9 rewritten) |
| check_assets | 19 | **19** | 0 (14 rewritten) |
| **query_subscriptions Lambda** | (new) | **11** | +11 |
| **Python total** | **1335** | **1347** | **+12** |
| vitest | 830 | 830 | 0 |
| **All gates** | green | **green** | — |

### Deploy

Backend-only release (no UI changes). All 5 helper Lambdas need to
be redeployed.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.3.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
```

UI deploy not required for this release.

### Sanity after deploy

1. Each helper Lambda's CloudWatch logs should show no behavior
   change — DAL preserves semantics verbatim (BatchGet retry,
   pagination, pause-flag lookup, etc.).
2. If a Lambda fails to import on cold start, check:
   `aws logs tail --since 5m /aws/lambda/...-evaluate-deps`
   for `ImportError: No module named 'dal'` — would indicate the
   deploy package didn't include the new `dal/` directory.
3. No outward API contract change; integrations should be invisible.

### Plan progress

- ✅ Stage 1 v0.78.13 — Active → Running
- ✅ Stage 2 v0.78.14 — ExecutionStatus case normalize
- ✅ Stage 4 v0.79.0 — SSoT enums codegen
- ✅ Stage 5 v0.79.1 — Computation moved to backend
- ✅ Stage 6 v0.79.2 — Per-partition retry
- ✅ Stage 7 v0.79.3 — DAL migration for 4 Lambdas **(this release)**

**All 7 stages of the multi-release alignment plan complete.**

### Remaining BACKLOG

- `print() → logger` migration in 4 Lambdas (~30 min each,
  opportunistic; tracked via v0.78.10 self-audit).
- Per-partition CANCEL and SKIP (needs SFN template work; per ADR #74).
- Backend hand-written `TaskStatus` class → generated module-level
  sets (8 sites to migrate; per ADR #72).
- SFN template literals to canonical (different generator shape;
  per ADR #72).

## v79.2 (0.79.2) - 2026-05-27

Stage 6 of the multi-release alignment plan — **per-partition retry**
(ADR #74). Extends an existing endpoint rather than minting a new one.

### Added

- **Optional `partition_keys` parameter** on
  `POST /api/backfills/{id}/retry-failed`. If provided, only that
  subset of failed partitions is retried (caller's keys must all be
  in the actually-failed set, else 422). Body omitted or empty
  array → retry all failed partitions (v0.78.11 behavior preserved).
- **Strict validation**:
  - `422 partition_keys_not_failed` with `failed_partitions` array
    in response when the caller specifies a key that isn't actually
    failed (stale UI, typo, etc.). Diagnostic in the body lets
    clients offer recovery.
  - `422 invalid_partition_keys` for non-array shape
  - `422 malformed_body` for unparseable JSON
- **Frontend per-partition retry button** — small ↻ button at
  top-right of each `failed`-status cell in the heatmap. Click
  stops propagation (doesn't open DAG), confirms via `window.confirm`,
  POSTs with `partition_keys: [key]`, toasts result.
- **`useRetryFailedBackfillMutation` accepts new shape** —
  `{backfillId, partitionKeys?}` object. Backward-compatible: bare
  `mutateAsync('bf-id')` still works.

### Not changed (deliberate — BACKLOG)

- **Per-partition CANCEL.** Mid-flight cancel of a specific
  partition needs SFN template changes (additional DDB state +
  JSONata in `bulk_backfill/sfn.tpl.json`). Significant risk in a
  single release. BACKLOG.
- **Per-partition SKIP.** Same SFN-template constraint as cancel.
  BACKLOG.
- **Multi-partition select UI.** No checkbox column on the heatmap
  for batch retry. Single-partition button covers the common case;
  batch select is a separate UI design problem.

### Documentation

- **ADR #74** — "Per-partition retry-failed". Full rationale for
  extending existing endpoint over new routes, why strict validation
  catches stale-UI bugs, what's deliberately deferred, and the
  CLAUDE.md #4 connection on errors being visible.

### Tests

| Suite | Was | Now | Δ |
|---|---|---|---|
| console_api | 341 | **348** | +7 (TestRetryFailedWithPartitionKeys) |
| Python total | 1328 | **1335** | +7 |
| vitest | 827 | **830** | +3 (mutation shape variants) |
| **All gates** | green | **green** | — |

### Deploy

Full deploy (backend route extension + frontend button + new CSS).

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.2.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
cd ../ui && npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. Open a backfill detail page with at least one failed partition.
   Each red cell should show a tiny ↻ button at top-right.
2. Click the ↻ — confirm dialog → new backfill starts containing
   only that one partition. Toast confirms.
3. Click ↻ on a cell whose underlying status changed (e.g., parent
   was retried elsewhere) — should show 422 toast with diagnostic
   message including the actual current failed list.
4. The "Retry all failed" button at the top still works as before.

### Plan progress

- ✅ Stage 1 v0.78.13 — Active → Running
- ✅ Stage 2 v0.78.14 — ExecutionStatus case normalize
- ✅ Stage 4 v0.79.0 — SSoT enums codegen
- ✅ Stage 5 v0.79.1 — Computation moved to backend
- ✅ Stage 6 v0.79.2 — Per-partition retry **(this release)**
- ⏳ Stage 7 v0.79.3 — DAL migration for 4 Lambdas
- BACKLOG — per-partition cancel/skip (SFN template work);
  print() → logger in 4 Lambdas; backend hand-written TaskStatus
  class → generated

## v79.1 (0.79.1) - 2026-05-27

Stage 5 of the multi-release alignment plan — **computation moved to
backend** (ADR #73). Closes Q7 and Q9 from the multi-release plan.

### Changed

- **Backend computes derived backfill status server-side**.
  `_compute_derived_backfill_status(item)` in `routes/backfill.py`
  mirrors the (now-deleted) frontend `computeDerivedBackfillStatus`.
  Applied in `_format_backfill_summary` so list, detail, and retry-
  chain responses all return the derived value. Raw status is logged
  at `warn` level on divergence (stuck SFN diagnosis in CloudWatch)
  but **no longer exposed in API responses** (per Q7).
- **Backend computes per-partition aggregate status**.
  `_summarize_partition_status(children, partition_key)` in
  `routes/backfill.py`. Detail response gains a new field (per Q9):
  ```json
  "partitions": [{"key": "2024-01-15", "status": "success"}, ...]
  ```
- **Frontend deletions**:
  - `ui/src/utils/backfillStatus.ts` — removed entirely; no
    client-side derivation left.
  - Its test file removed.
- **Frontend simplifications**:
  - `BackfillsListPage` reads `b.status` directly (no override).
  - `BackfillDetailPage` reads `detail.status` and
    `detail.partitions[]` directly. The `useEffect` that logged
    raw≠derived divergence to the browser console is gone — that's
    a CloudWatch concern, not a browser concern.
  - `isBackfillActive` becomes a one-liner against
    `BACKFILL_TERMINAL_STATUSES` (from `@/generated/enums`).

### Not changed (deliberate)

- **`utils/staleness.ts` kept.** The original Q8 answer said "delete
  entirely". On closer reading, the file has picker-scoped
  resolution logic (recent-events within the date picker → fallback
  to backend `last_updated`) that the backend doesn't replicate
  — backend computes staleness from a single timestamp without
  picker context. Deleting the util would lose real behavior. The
  original recommendation was based on a shallower read; ADR #73
  documents the correction transparently.
- **SFN templates unchanged.** `bulk_backfill/sfn.tpl.json` writes
  the terminal status from JSONata; that's a fine source of truth.
  The override exists for the *stuck-without-Finalize* case, which
  is what backend now handles.

### Documentation

- **ADR #73** — "Computation moved to backend". Full rationale for
  derived status + per-partition aggregation, explicit note on the
  Q8 staleness.ts revision, and the lesson on planning vs. actual
  code reading.

### Tests

| Suite | Was | Now | Δ |
|---|---|---|---|
| console_api | 326 | **341** | +15 (derived helper × 8 + partition helper × 7) |
| Python total | 1313 | **1328** | +15 |
| vitest | 838 | **827** | −11 (deleted util test file; existing tests rewritten in place) |
| **All gates** | green | **green** | — |

Vitest count dropped because the deleted `backfillStatus.test.ts`
file's coverage moves to `console_api/tests/routes/test_backfill.py`
where the logic now lives. Net coverage of the contract increased
(+15 backend > −11 frontend).

### Deploy

Full deploy (backend + frontend). Frontend will see legacy responses
during the rolling deploy window — the `partitions` field has a
legacy fallback in `BackfillDetailPage` for that case.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.1.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
cd ../ui && npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. **Stuck SFN detection works server-side.** Find a known stuck
   backfill (or wait for one) — CloudWatch should show
   `log.warn("backfill", "Derived status differs from raw (stuck SFN?)", ...)`
   in console_api logs. List + detail pages should show the
   *derived* status (e.g. 'completed') even though DDB still has
   raw='running'.
2. **Per-partition heatmap renders without client-side aggregation.**
   Detail page shows partition badges; turn on network panel to
   verify the response includes the new `partitions[]` field.
3. **No browser console warnings** about backend status discrepancy
   — those moved to CloudWatch.

### Plan progress

- ✅ Stage 1 v0.78.13 — Active → Running
- ✅ Stage 2 v0.78.14 — ExecutionStatus case normalize
- ⏭️ Stage 3 — folded into Stage 7
- ✅ Stage 4 v0.79.0 — SSoT enums codegen
- ✅ Stage 5 v0.79.1 — Computation moved to backend **(this release)**
- ⏳ Stage 6 v0.79.x — Per-partition cancel/retry/skip
- ⏳ Stage 7 v0.79.x — DAL migration for 4 Lambdas
- BACKLOG — print() → logger in 4 Lambdas; backend hand-written
  TaskStatus class → generated

## v79.0 (0.79.0) - 2026-05-27

Stage 4 of the multi-release alignment plan — **SSoT enums codegen**
(ADR #72). The largest change in the plan: removes the multiplicity
of enum definitions across SDK, Lambdas, and frontend.

This is a **minor version bump** because the canonical contract
location moved (slsflow/constants.py is now authoritative for status
enums) and a new codegen module ships in the SDK.

### Added

- **`slsflow/constants.py` extended** with 7 enum families lifted into
  the SDK as canonical: `PipelineStatus`, `ExecutionStatus`,
  `BackfillStatus`, `BackfillCascade`, `BackfillGranularity`,
  `StalenessStatus`, `AssetOperator`. Plus derived sets
  (`EXECUTION_STATUS_CANONICAL`, `BACKFILL_TERMINAL_STATUSES`,
  `BACKFILL_ACTIVE_STATUSES`) and `normalize_execution_status` helper
  (lifted from v0.78.14 Lambda code).
- **`slsflow/codegen/` module** — new SDK submodule. Houses code
  generators that produce derived artifacts from canonical sources.
- **`slsflow/codegen/sync_enums.py`** — generator that imports
  `slsflow.constants` (NOT regex-parses) and writes:
  - `sam/lambdas/_shared/constants_generated.py`
  - `sam/lambdas/console_api/constants_generated.py`
  - `ui/src/generated/enums.ts`

  Each generated file has a `DO NOT EDIT` banner with canonical SHA
  (first 16). Idempotent: re-running on unchanged source produces
  identical bytes.
- **`make generate-enums`** target — regenerate all derived files.
- **`make check-generate-enums`** target — CI drift gate. Exits 1
  if any generated file would change.
- **`tests/test_enum_drift.py`** (console_api, 5 tests) — runtime
  drift guard. Asserts hand-written backend enums agree with
  canonical, generator output is in sync, and `normalize_execution_status`
  behavior matches between backend and canonical.

### Changed

- **Frontend `ui/src/types/index.ts`** — `TaskStatus`, `TriggerRule`,
  `PipelineStatus`, `ExecutionStatus`, `BackfillStatus`,
  `BackfillCascade`, `BackfillGranularity`, `StalenessStatus` no
  longer defined inline. Re-exported from `@/generated/enums`. Plus
  `BACKFILL_TERMINAL_STATUSES`, `TASK_TERMINAL_STATUSES` constants.
- **Frontend is fully SSoT.** Any new enum value or rename now flows:
  edit `slsflow/constants.py` → `make generate-enums` → frontend
  types auto-update.

### Not changed (deliberate)

- **Backend `sam/lambdas/console_api/constants.py`** keeps its
  hand-written `TaskStatus`/`TriggerRule`/etc. classes. Reason:
  class-level sets like `TaskStatus.TERMINAL` are used at 8 sites,
  and the generated module-level sets (`TASK_TERMINAL_STATUSES`)
  don't match that access pattern. The drift test
  (`test_enum_drift.py`) catches divergence; full migration is
  incremental and will land in a v0.79.x release.
- **Lambda `evaluate_deps/constants.py`** — copied from `_shared`
  via existing `make sync-constants`. The generated mirror lives
  alongside but isn't imported yet.
- **SFN templates** — embed `'running'` / `'SUCCEEDED'` etc. as
  Jsonata literals. Not migrated; BACKLOG (different generator
  shape needed).

### How to update an enum value (going forward)

```bash
# 1. Edit canonical
vi slsflow/constants.py

# 2. Regenerate
make generate-enums

# 3. Verify
make check-generate-enums  # should print "in sync"
pytest sam/lambdas/console_api/tests/test_enum_drift.py
```

Frontend imports `@/generated/enums` directly. Backend hand-written
copies need a parallel manual edit + commit (until full migration).

### Documentation

- **ADR #72** — "SSoT enums codegen". Full rationale, mapping of
  what's generated, why Python-import (not regex/AST), why class-level
  not Enum, what's explicitly NOT done yet, and CI integration plan.

### Tests

| Suite | Was | Now | Δ |
|---|---|---|---|
| console_api | 321 | **326** | +5 (enum drift suite) |
| Python total | 1308 | **1313** | +5 |
| vitest | 838 | **838** | 0 |
| **All gates** | green | **green** | — |

### Deploy

Backend deploy required (`constants_generated.py` ships with each
Lambda but is unused at runtime by this release — they're additive).
Frontend deploy required (build picks up new `generated/enums.ts`).

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.79.0.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
cd ../ui && npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. CI on next PR should call `make check-generate-enums` (add the
   step in `.github/workflows/ci.yml`). For this release, manual
   `make check-generate-enums` confirms in-sync state.
2. Frontend bundle should be the same size or slightly smaller (one
   fewer inline type definition).
3. Any code that imports `TaskStatus` etc. from `@/types` still
   works — re-exports preserve the public API.

### Plan progress

- ✅ Stage 1 v0.78.13 — Active → Running
- ✅ Stage 2 v0.78.14 — ExecutionStatus case normalize
- ⏭️ Stage 3 — folded into Stage 7 (Q3=A "all under DAL")
- ✅ Stage 4 v0.79.0 — SSoT enums codegen **(this release)**
- ⏳ Stage 5 v0.79.x — Computation moved to backend
- ⏳ Stage 6 v0.79.x — Per-partition actions
- ⏳ Stage 7 v0.79.x — DAL migration for 4 Lambdas
- BACKLOG — print() → logger in 4 Lambdas; backend hand-written
  TaskStatus migration to generated sets

## v78.14 (0.78.14) - 2026-05-27

Stage 2 of the multi-release alignment plan (ADR #71). ExecutionStatus
case normalization. The frontend type used to accept 12 variants for
what should be 6 statuses — UPPERCASE leaking from SFN, lowercase from
DDB, plus a `'success'` legacy form. Now canonicalized at the boundary.

### Added

- **`normalize_execution_status(status, log_warn=None)` helper** in
  `sam/lambdas/_shared/constants.py` (and mirrored copy in
  `console_api/constants.py` per the existing sync pattern). Canonical
  set: `{running, succeeded, failed, timed_out, aborted, stopped}`.
  Maps UPPERCASE SFN values, legacy `'success'`/`'SUCCESS'`, and is
  idempotent on canonical inputs. Optional `log_warn` callable for
  diagnostic warnings on unexpected values (CLAUDE.md #4 visibility).
- **18 helper tests** — UPPERCASE → canonical, idempotence per
  canonical value, legacy `'success'` handling, `None` input, unknown
  value behavior (log + return original), and a lock test on the
  canonical set to catch accidental drift.

### Changed

- **`pipelines_list._reconcile_running`** — replaced local
  `sfn_status_map` with the helper. Removed the duplicate.
- **`TIMED_OUT` precision restored.** Previously the local map
  collapsed `TIMED_OUT → 'failed'`; now preserved as `'timed_out'`.
  Downstream "SFN-failed-but-tasks-resolved" recovery check updated
  from `if sfn_status == 'failed'` to
  `if sfn_status in {'failed', 'timed_out'}` to keep semantics
  identical for that code path.
- **Frontend `ExecutionStatus` type narrowed** — from 12 variants down
  to 6 canonical lowercase values. TypeScript now enforces canonical
  contract at compile time.
- **`CalendarView.tsx`** — removed UPPERCASE branches in
  status-to-visual-bucket mapping (5 expressions reduced to 4).
  Added `'timed_out'` → `'failed'` visual bucket so the new precision
  doesn't accidentally drop those into a "partial" miscellaneous
  bucket.
- **`evaluate_deps/constants.py`** — synced from `_shared/constants.py`
  via `make sync-constants`. The Lambda doesn't use the new helper
  yet, but the constant set is available for future migration.

### Not changed (deliberate)

- **`SFN_STATUS_MAP` in `console_api/constants.py`** stays. It's a
  different mapping (SFN UPPERCASE → `TaskStatus.SUCCESS`/etc., not
  ExecutionStatus). Stage 4 (SSoT enums codegen, v0.79.0) will
  deduplicate across files at the same time it handles 7 other
  enum families.
- **`evt.metadata.status` in `TabEvents.tsx`** still accepts both
  cases. That field is free-form metadata set by various SFN
  templates, not `ExecutionStatus`. Migrating SFN templates to write
  canonical values is a separate cleanup.

### Documentation

- **ADR #71** — "ExecutionStatus case normalization". Captures root
  cause (UPPERCASE leak from `DescribeExecution`), the canonical
  helper, where it's applied, the `TIMED_OUT` precision change, what
  explicitly stays out of scope, and the lesson on narrowing types
  to enforce contracts.

### Tests

| Suite | Was | Now | Δ |
|---|---|---|---|
| console_api | 303 | **321** | +18 (normalize helper) |
| Calendar (vitest) | unchanged count, 1 test rewritten for canonical-only contract |
| Python SDK | 900 | 900 | 0 |
| evaluate_deps / notify / check_assets | 56 / 12 / 19 | unchanged | 0 |
| vitest total | 838 | 838 | 0 (1 test rewritten, not added) |
| **Python total** | **1290** | **1308** | **+18** |
| **All gates** | green | **green** | — |

### Deploy

Full deploy needed (backend + frontend).

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.14.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
cd ../ui && npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. Pipeline detail view — running execution that finishes between
   polls reconciles to canonical lowercase status (`succeeded`,
   `failed`, `timed_out`, or `aborted`)
2. CloudWatch logs (filter `_reconcile_running`) — no `log.warn`
   entries for "Unexpected execution status". If you see one, raw
   non-canonical value leaked from somewhere new
3. Calendar view — execution dots colored correctly for all statuses
   including the new `timed_out` precision
4. Browser console on any page reading executions — no TypeScript
   build warnings about UPPERCASE comparisons (those got fixed at
   compile time, not at runtime)

### Plan progress

- ✅ Stage 1 v0.78.13 — rename Active → Running
- ✅ Stage 2 v0.78.14 — ExecutionStatus case normalize **(this release)**
- Next — Stage 3 was "CLAUDE.md DAL exception"; replaced by Q3=A
  ("all under DAL"). Moved to Stage 4-after work.
- Next — Stage 4 v0.79.0 — SSoT enums codegen (~half day)
- Stage 5 v0.79.x — Computation moved to backend
- Stage 6 v0.79.x — Per-partition cancel/retry/skip
- BACKLOG — print() → logger in 4 Lambdas; DAL migration for 4 Lambdas

## v78.13 (0.78.13) - 2026-05-27

Stage 1 of the multi-release alignment plan (ADR #70). UI label change
and filter logic narrowing.

### Changed

- **"Active" filter chip renamed to "Running"** in the Backfills list
  page. Previously "Active" was a synthetic bucket meaning
  `{running, pending}`. Mike's question — *"active = running?"* —
  confirmed users see no meaningful distinction. The chip now maps
  1:1 to the derived `running` status.
- **`statusFilter` state type narrowed** from
  `BackfillStatus | 'active' | 'all'` to `BackfillStatus | 'all'`.
  No synthetic value. Filter logic simplifies to a direct equality
  check on `computeDerivedBackfillStatus(b)`.

### Not changed

- **`BackfillStatus.PENDING` constant stays in backend**. The value
  is theoretically possible (DDB write before SFN start) but never
  seen operationally. Removing it would be a larger backend change.
  If a pending backfill appears, it shows under "All" with an explicit
  `pending` status pill — but no "Pending" chip in the filter row.

### Documentation

- **ADR #70** — "Active filter renamed to Running". Captures the
  rename, why pending is excluded from "Running", and why the
  constant is kept despite no UI affordance.

### Tests

- `BackfillsListPage.test.tsx` — 2 new tests:
  - "Running" chip present, "Active" chip gone
  - "Running" filter narrows to derived-running only (excludes
    stuck-running with derived=completed)
- Total vitest: **838** (was 836; +2). Python unchanged at 1290.

### Deploy

Frontend-only. No backend changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.13.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check

cd ui && npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. Backfills list page filter chips read: All / **Running** /
   Completed / Failed / Partial / Canceled
2. Click "Running" → only backfills with derived status `running`
   appear (stuck-running with all partitions done don't show — they're
   under "Completed")
3. Genuinely-pending backfill (theoretical) would NOT appear under
   "Running" — only under "All". If you create one, verify this.

### Next in the plan

This is Stage 1 of 7 from the alignment plan. Upcoming:
- v0.78.14 — ExecutionStatus case normalize
- v0.78.15 — CLAUDE.md DAL exception edit
- v0.79.0 — SSoT enums codegen (the big one)
- v0.79.x — Computation moved to backend
- v0.79.x — Per-partition cancel/retry/skip
- BACKLOG (opportunistic) — print() → logger in 4 Lambdas

## v78.12 (0.78.12) - 2026-05-27

Two related fixes from v0.78.11 review (ADR #69). Both root-cause to
the same incomplete fix in v0.78.8: `derivedStatus` was added only to
the detail page, leaving the list page unguarded against stuck-SFN
state.

### Fixed

- **Status inconsistency between list and detail**. The SAME backfill
  showed `RUNNING` in the list and `COMPLETED` in the detail —
  `derivedStatus` (ADR #67) lived only in `BackfillDetailPage`.
  Extracted to `utils/backfillStatus.ts` and applied across both
  surfaces. Pill, progress segments, status filter — all consistent.

### Added

- **Inline Cancel button on list rows**. Right-most cell, `X` icon,
  visible only for active backfills (raw `running`/`pending` AND not
  derived-terminal). Confirms before sending; toast feedback on
  success/error. Doesn't navigate to detail when clicked. Stuck-
  running backfills correctly DON'T get the button.
- **`utils/backfillStatus.ts`** — new shared module exporting
  `computeDerivedBackfillStatus`, `isBackfillActive`, and
  `BACKFILL_TERMINAL_STATUSES`. Pure functions, fully tested.

### Changed

- **List status filter switched to client-side**. List query always
  fetches with `null` (no API filter); component filters by derived
  status. Reason: if API filtered by raw `status='completed'`,
  stuck-running backfills (derived=`completed`) would not appear
  under "Completed" tab. Backfills are infrequent so over-fetch is
  cheap (revisit at >5000 records).
- **`BackfillDetailPage`** refactored to use shared util. Behavior
  unchanged; ~30 lines of inline logic removed.

### Documentation

- **ADR #69** — "derivedStatus lifted to shared util + inline Cancel
  on list". Captures why client-side filtering is acceptable at
  current volume, what the API/client trade-off costs, and the lesson
  about applying defensive heuristics in one place rather than
  scattered.

### Tests

- New `utils/backfillStatus.test.ts` — 10 tests (terminal-respected,
  three stuck overrides, skipped-toward-processed, isBackfillActive
  truth table).
- `BackfillsListPage.test.tsx` — 5 new tests for stuck-running pill
  consistency, Cancel button visibility matrix (active/terminal/stuck/
  hidden), client-side filter behavior with mixed raw + derived
  statuses. Updated 1 existing test to reflect client-side filter.
- Total: 836 vitest (was 821; +15). 1290 Python unchanged.

### Honest self-review

The v0.78.8 fix was demonstrably incomplete. ADR #67 explicitly said
"the override drives pill, banner, isActive, canRetry" — all four
were on the detail page, but the SAME concerns exist on the list page
(pill, progress, action gating) and I didn't extend the fix there.
Mike's screenshot pair (RUNNING in list, COMPLETED in detail) is the
exact failure mode the original ADR was trying to prevent.

This release closes that gap by lifting the logic out of one component
and making it the One Way to compute backfill status. Future surfaces
(e.g. notification bell badges, calendar overlays) will use the same
util.

### Deploy

Frontend-only. No backend changes.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.12.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ symlink check
cd ui && npm run build && ../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity checks after deploy

1. Stuck-running backfill (raw='running' in DDB but counts say done):
   pill in list shows correct derived status (completed/partial/failed)
2. Cancel button visible only on active backfill rows; not visible on
   any terminal or stuck-running row
3. Click Cancel in list → confirm dialog → toast → row updates on
   next 30s poll
4. Filter tabs (Completed/Failed/Partial) include stuck-running
   backfills whose derived status matches

## v78.11 (0.78.11) - 2026-05-27

Backfill UX/DX bundle (ADR #68). Three small but distinct gaps from
v0.78.10 user review, shipped together because they share code surface.

### Added

- **Partial ratio in status pill**. Was: `partial`. Now: `partial (4/5)`.
  Applied to both BackfillsListPage (list pill) and BackfillDetailPage
  (header pill + retry chain children pills). Other statuses unchanged —
  ratio only adds value when the count is mixed.
- **Retry chain on detail page**. New section between metadata and
  partition heatmap, hidden when no chain exists. Shows:
  - **↑ Retry of:** `<bf-parent-id>` (clickable when `onBackfillNav`
    provided)
  - **↓ Retried by (N):** list of child backfill IDs with their
    status pills (clickable too)
  - Navigates within retry chain — click parent or any child to
    jump to that backfill detail.
- **Backfill terminal events in notification bell**. New `type='backfill'`
  notification rendered with a `Rocket` icon, color-coded by terminal
  status (green/red/amber/grey). Click navigates to backfill detail.
  Both dropdown and toast views support it.
- **Backend**:
  - `backfills_repo.list_retries_of(parent_backfill_id)` — new DAL
    method. Scan + filter (Backfills are infrequent; if volume grows,
    add GSI). Sorted by `started_at` asc.
  - `_format_backfill_summary` now returns `parent_backfill_id` (was
    only on the raw DDB record).
  - Detail endpoint adds `retried_by[]` to response — direct children
    only, not transitive descendants.
  - `get_notifications` endpoint appends terminal backfill events
    matching the time window, re-sorted into the combined feed.

### Renamed

- **"Partitions" → "Backfilling dates"** in the partition heatmap
  section heading. User-facing language only; internal data model
  still uses `partition_keys` / `partition_*` field names. No schema
  impact.

### Documentation

- **ADR #68** — "Backfill UX/DX bundle — partial ratio, retry chain,
  notification source". Captures the bundle rationale, scan-vs-GSI
  trade-off, poll-vs-push trade-off, naming choices, and what
  explicitly stays out of scope (per-partition cancel, cost preview,
  Slack).

### Tests

- BackfillDetailPage: +7 tests covering partial ratio, "Backfilling dates"
  heading rename, retry chain visibility (hidden vs shown), parent link
  rendering, child list rendering, click navigation. Was 24 → **31**.
- BackfillsListPage: +2 tests for partial ratio + non-partial leaving
  raw text. Was 15 → **17**.
- backfills_repo: +2 tests for `list_retries_of` — sort + empty case.
- Total: 821 vitest (was 812), 1290 Python (was 1288), all green.

### Removed

Nothing.

### Deploy

Full deploy needed (backend + frontend changes).

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.11.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ verify symlink

cd sam && sam build && sam deploy --no-confirm-changeset --profile slsflow-dev
cd ../ui && npm run build && ../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

### Sanity after deploy

1. List page — partial backfill shows "partial (X/Y)" pill
2. Detail page — heading reads "Backfilling dates (N)"
3. Trigger Retry failed → original detail page now shows ↓ child link;
   click navigates; new detail page shows ↑ parent link
4. After any backfill terminal event, within 30s the bell badge
   increments; click shows `Backfill completed/failed/partial: pipeline-name`
   with the partition ratio
5. Click notification → navigates to backfill detail; notification
   dismissed

## v78.10 (0.78.10) - 2026-05-27

Documentation-only release. No behavior changes.

### Added — CLAUDE.md Coding Philosophy refinements

Following v0.78.9 honest audit measuring philosophy against actual
code. The section now matches reality, not aspiration.

- **CLI argparse handlers exception** added to Python style block.
  `cmd_*` functions in `slsflow/cli.py` may omit docstrings when they
  just unpack argparse args and delegate to documented functions.
  Argparse help text IS the user-facing doc.
- **Refined 12-Factor logs paragraph**. Explicit: `console_api`
  follows structured logging (160+ `log.*` calls); 5 small Lambdas
  (`evaluate_deps`, `notify_asset_subscribers`, `check_assets`,
  `query_subscriptions`, `ui_bootstrap`) still use bare `print()` —
  tracked in BACKLOG, not silently swept under rug. CloudWatch
  captures stdout regardless so logs are visible; the gap is
  parse-ability for alarms.
- **CLI tool exception** explicit. `slsflow/cli.py`, `register.py`,
  `init.py`, `output.py`, `ai/*` use `print()` correctly — CLI tools
  ARE the event stream output, not log producers. Don't migrate them.
- **ErrorBoundary class component exception**. React's error boundary
  API (`getDerivedStateFromError`) has no hook equivalent; class is
  the only option. `ErrorBoundary.tsx` is the only sanctioned class
  component. Don't write any other.
- **"This section describes the codebase, not an aspiration"
  subsection** at end of Philosophy. Lists 10 principles "already
  followed in practice" with concrete numbers (91% type hints, 0
  wildcard imports, 0 other UI libs, etc.) and 4 known gaps with
  context.

### Added — BACKLOG.md

New section: "🧹 Philosophy compliance gaps (v0.78.9 audit)". Four
entries with cost estimates and apply-when guidance:
- Migrate 5 Lambdas from `print()` to `slsflow.logger`
- Docstring pass on `cmd_*` CLI handlers
- Inline-style cleanup in `AssetLineageFlow.tsx` (3 occurrences)
- Icon-only button ARIA audit

Each entry says: do it opportunistically when you're already in the
file, not as a dedicated cleanup PR.

### Why the honest audit matters

The Coding Philosophy section was added in v0.78.9 derived from real
practice, but went unchecked. Mike's pushback ("наскільки ці філософії
актуальні для нас") forced a measurement pass that surfaced gaps. The
v0.78.10 changes ensure CLAUDE.md doesn't drift into aspirational
fiction — every claim is backed by a number or explicitly flagged as
a known gap.

### Tests

No code changes. All gates from v0.78.9 still pass: 1288 Python +
812 vitest = 2100 tests, tsc strict clean, cfn-lint clean.

### Deploy

No deploy needed. Doc + BACKLOG changes don't ship to production.

## v78.9 (0.78.9) - 2026-05-27

Documentation-only release. No behavior changes.

### Added

- **CLAUDE.md — "Coding Philosophy" section** between Core Principles
  and What is SLSFlow. Captures the broader style frame underlying
  the 12 Core Principles:
  - **Python**: PEP 8 + Google Python Style Guide (surface) + Zen of
    Python PEP 20 (taste) + 12-Factor App (architecture, with
    serverless adaptations).
  - **Frontend**: React function components + hooks, TypeScript strict
    mode, shadcn/ui + Tailwind as component primitive layer, state
    separation (component / Zustand / React Query), one file one
    purpose, accessibility non-optional.
  - **Bridge section** showing how each hard rule traces back to a
    philosophy principle (no duplication ↔ "one obvious way", no
    silent excepts ↔ "errors should never pass silently", etc.).

  The intent: provide a taste reference for judgment calls that the
  hard rules don't cover, plus give new contributors a shared frame
  for what "good code in this codebase" means.

### Internal

- Version bumped to 0.78.9 across pyproject.toml, slsflow/__init__.py,
  ui/package.json for version-consistency check.

### Tests

- No new tests; no code changed.
- All gates still green from v0.78.8: 1288 Python + 812 vitest = 2100
  tests, tsc strict clean, cfn-lint clean.

### Deploy

No deploy needed. CLAUDE.md changes don't ship to production.

## v78.8 (0.78.8) - 2026-05-27

Fixes three issues from v0.78.7 deploy review:
1. **Status pill invisible in light mode** — 53 broken CSS variable
   refs across `_modals.css` (52) and `_navigation.css` (1).
2. **BY column kept against user request** — removed in v0.78.7 review
   discussion, but Mike re-flagged that I kept it. Now actually gone.
3. **Status banner shows "Running" when counters say done** — stuck
   `bulk_backfill` SFN before Finalize step. Defensive override.
4. **"Started by" row** — removed entirely (no audit infrastructure).

### Fixed

- **CSS variable name drift across backfill UI** — pre-existing tech
  debt from v0.78.0. The CSS used `var(--accent-blue)`, `var(--danger)`,
  `var(--border-default)`, `var(--border-subtle)` — none of which are
  defined in `_base.css`. Defined vars are `--accent`, `--error`,
  `--border` (with `--border-strong` as the contrast variant). In light
  mode, undefined vars resolved to nothing, leaving status pills with
  transparent background and white text → invisible on white page bg.
  Dark mode happened to look okay because page bg is dark and other
  fallback cascades filled gaps.

  53 refs fixed via sed bulk rename across both files. Same fix
  ALSO repairs other affected elements (cards, banners, dropdown
  borders) that I had unknowingly broken when first authoring the
  backfill UI in v0.78.0. The bug existed since v0.78.0; nobody
  caught it because dev was always in dark mode.

  Pinned by `derivedStatus` tests that check the pill's modifier
  class is set correctly (the BEM class itself isn't enough; the
  underlying CSS now must render).

### Changed (BackfillsListPage)

- **BY column removed**. Mike's first v0.78.7 review explicitly asked
  for this, and I incorrectly kept it (rationalized as audit trail
  even though no audit infrastructure exists). Header cell, body
  cell, and `formatUser` import all removed.

### Changed (BackfillDetailPage)

- **"Started by" row removed entirely** (was hidden via formatUser in
  v0.78.7; now the row itself is deleted). No backend infrastructure
  tracks who triggered a backfill — the field was always either
  literal `'unknown'` or, with Cognito auth enabled, an email. Mike's
  call: *"давай приберемо, у нас ніде не трекається хто саме запустив"*.
- **`derivedStatus` defensive override**. Status pill, banner choice,
  `isActive` (Cancel button gate), and `canRetry` (Retry button gate)
  now use a derived status that re-interprets `running`/`pending` when
  partition counters indicate the work is done. See ADR #67 for the
  full reasoning, recovery path, and the symptom (Mike's case: TOTAL=2,
  COMPLETED=2, banner still said "Running. 2 of 2 processed so far").
  When raw and derived disagree, `console.warn` emits a diagnostic
  breadcrumb pointing at the ADR.

### Documentation

- **ADR #67** — "Client-side derived status for backfills". Documents
  why the workaround is client-side (real fix is investigating SFN
  Finalize step that didn't run), why the override is conservative
  (only re-interprets non-terminal), how to clean it up later, and the
  general lesson about derived state vs. stored state.

### Tests

- `BackfillDetailPage.test.tsx`: replaced "Started by uses formatUser"
  test with "Started by row removed" assertion. Added 6 tests for
  `derivedStatus`: terminal-respected, stuck→completed, stuck→partial,
  stuck→failed, genuinely-running, Cancel-hidden-when-stuck-overridden.
  Now 24 tests (was 18).
- `BackfillsListPage.test.tsx`: replaced "renders em-dash for unknown"
  test with "BY column is removed" assertion that checks both the
  thead and that 'unknown' doesn't leak anywhere.
- Total vitest: **812 passed** in 55 files (was 806; +6 derivedStatus).
- Python: 1288 total (900 SDK + 301 console_api + 56 evaluate_deps +
  12 notify_asset_subscribers + 19 check_assets), all green.

### Honest self-review against v0.78.7 audit

The CSS variable bug should have been caught earlier:
- I edited `_modals.css` in v0.78.7 adding `--border-subtle` refs for
  the combobox without checking whether the variable was defined.
- The pre-existing 52 broken refs in the same file pre-dated my work,
  but I now own the CSS module — should have grepped for undefined
  vars during the v0.78.7 audit.
- Mike's screen showed status pill invisible since v0.78.0; nobody
  flagged it until light mode review.

The BY column removal request was also missed. In v0.78.7 I wrote
*"Decision: keep — it's the audit trail column"*, treating Mike's
question as if it were genuinely open. It wasn't — he was asking why
I hadn't removed it yet. Fixed in this release with explicit
acknowledgment.

The status banner issue (`derivedStatus`) is a legitimate workaround
for a backend SFN edge case, documented in ADR #67. Real fix is in
BACKLOG: investigate why `Finalize` step skips in some cases.

### Deploy notes

Frontend-only changes (CSS + UI logic). No backend deploy needed.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.8.zip
ls -la sam/lambdas/console_api/slsflow   # ⚠️ verify symlink
cd ui
npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

After deploy, hard-refresh in light mode to verify status pills are
visible. Click into a backfill with TOTAL==COMPLETED to verify status
pill shows "completed" (not "running") and Cancel button is hidden.

## v78.7 (0.78.7) - 2026-05-27

Backfill UI audit pass — fixes the partition-click date-routing bug
(real bug, ADR #63 regression) plus five UX-polish items reported in
v0.78.5 deploy review, and adds one feature (pipeline filter combobox).

### Fixed

- **Partition click → today instead of partition's date** (ADR #63
  regression, reported by Mike). Clicking a partition cell in
  BackfillDetailPage was supposed to navigate to the pipeline DAG for
  that partition's date (`/pipelines/?pipeline=X&date=Y`), but the
  user landed on today's date instead.

  Root cause: race in `useStoreInit`. The push/replace URL-sync
  effects fired on first commit with the STALE `store.date` (from
  previous session) and stripped the date param from the URL via
  `pushState` before the mount-once effect could apply `urlState.date`.
  Zustand state updates don't propagate mid-commit, so even though
  mount-once and push are declared in the right order, the push
  effect's closure captured today, not Y.

  Fix: replaced `initialized` ref with `isInitialized` state, so push
  and replace effects skip the first commit and re-fire on the second
  commit when store.date has propagated. New CLAUDE.md section
  "Zustand + React effect closures — URL sync gotcha" documents the
  pitfall with the failing pattern + the fix.

  Pinned by new test `useStoreInit.test.ts` "preserves URL date param
  when store has stale date on mount (ADR #63 regression)" — asserts
  no `pushState`/`replaceState` call during mount produces a URL with
  `pipeline=X` but missing `date=`.

### Changed (BackfillDetailPage UX)

- **"Started by: unknown"** now uses `formatUser()`, displaying `—`
  for the literal string `'unknown'` returned by the backend when no
  JWT claim is available (e.g. dev environment without Cognito auth).
  Matches the behavior in BackfillsListPage `By` column.
- **"DAG hash: unknown"** row is now hidden entirely when the value
  is `'unknown'` or null. Bulk-backfill SFN template writes
  `'unknown'` literally when the pipeline registry has no
  `dag_hash` field, which made the value meaningless to display.
- **Cancel button** got an explicit tooltip: "Cancel this backfill —
  in-flight partitions will complete, queued partitions will be
  skipped". Previously the button's behavior was opaque to users
  (Mike asked "що робить cancel?").
- **Export CSV button removed.** The CSV contained `partition_key`,
  `status`, `child_count`, `child_execution_ids` — none of which were
  useful for the audit workflows users actually run. Code deleted
  (~30 lines), `Download` icon import removed.

### Added (BackfillsListPage)

- **Pipeline filter combobox** (`PipelineFilterCombobox.tsx`, ~200
  lines). Replaced the plain text input with a combobox that
  dropdown-lists known pipelines from `usePipelinesQuery`:
  - Click input or chevron → opens dropdown
  - Type → filters dropdown by substring
  - Click option → sets filter to exact name
  - ArrowDown/ArrowUp + Enter for keyboard nav
  - Esc closes dropdown without clearing
  - Clear button (×) when value is non-empty
  - Max 20 visible options + "+N more — keep typing to narrow" hint
  - Full ARIA: `role="combobox"`, `aria-expanded`,
    `aria-activedescendant`, options have `role="option"`
  - BEM prefix `bl-pcb-*` (BackfillsList — PipelineCombobox)

### Tests

- New `useStoreInit.test.ts` — 7 tests covering URL→store date/mode
  init, fallback to today, pipeline restoration after async load,
  `navigateToExecution`, no-touch-URL on non-/pipelines routes, and
  the ADR #63 regression pin.
- New `PipelineFilterCombobox.test.tsx` — 13 tests covering render,
  open-on-focus, type-filters, click-selects, clear button, Esc
  closes, empty message, "+N more" hint, ArrowDown+Enter, ref
  forwarding.
- `BackfillDetailPage.test.tsx` — replaced Export CSV test with
  removal assertion; added 3 tests for formatUser + DAG hash hide/show
  (now 18 total, was 15).
- `BackfillsListPage.test.tsx` — added `usePipelinesQuery` mock
  (combobox dependency).
- Total vitest: **806 passed** in 55 files (was 783 in 53; +23 tests,
  +2 new files).
- Python: 900 SDK + 301 console_api + 56 evaluate_deps + 12
  notify_asset_subscribers + 19 check_assets = **1288 total** (the
  last three were missed in v0.78.4–0.78.6 release reports due to
  not running `find . -name pytest.ini` per CLAUDE.md hard-won lesson;
  caught and re-run in v0.78.7 self-audit, all green).

### Documentation

- **ADR #66** — "Export CSV removed from BackfillDetailPage". Captures
  what the feature was, why removal is better than improvement, and
  the recovery path if it needs to come back. Pinned by test.
- **CLAUDE.md** — new section under "Approach & patterns":
  "Zustand + React effect closures — URL sync gotcha". Documents
  the failing pattern with `useRef`, why state updates don't
  propagate within a commit, and the `useState` fix. Includes the
  symptom-to-recognize for future debugging.

### Deferred to BACKLOG

- **BY column** (BackfillsListPage) — shows `—` when no auth context.
  Mike asked if it's needed. Decision: keep — it's the audit trail
  column, becomes useful when Cognito auth is enabled in production.
  Consider hiding column entirely when ALL values are `—` (future).
- **Status filter chips visual confirmation** — Mike wasn't sure if
  they work. They do (verified via code review + existing tests).
  Could add a subtle "Filtering by: active" pill above the table for
  extra clarity (future).
- **Child executions UI clarity** — works correctly when SFN produces
  children. Mike's sample backfill happens to have 0 (likely all
  partitions short-circuited or still pending). No fix needed.

### Deploy notes

Frontend-only changes. No backend deploy needed.

```bash
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.7.zip
# ⚠️ Verify symlink
ls -la sam/lambdas/console_api/slsflow
# If 16 bytes: cd sam/lambdas/console_api && rm -f slsflow && ln -s ../../../slsflow slsflow

cd ui
npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

## v78.6 (0.78.6) - 2026-05-27

Fix: clicking Backfills tab redirected to Pipelines tab. Caused by
missing entries in two non-TypeScript locations that the Backfills
view was never registered in when it was added (v0.75.x).

### Fixed

- **Backfills tab redirect bug.** Pre-existing since v0.75.x. The
  CloudFront URL-rewrite function only knew about `pipelines | assets
  | tasks | runs`. Request to `/backfills/` got no rewrite, S3 returned
  404 on the directory path, CloudFront `CustomErrorResponses`
  masqueraded the 404 as 200 + `/index.html`, RootPage mounted and
  redirected to `/pipelines/`. User saw: "click Backfills, end up on
  Pipelines". Discovered after v0.78.5 deploy when shortcut fixes
  cleared the air and only this remained. ADR #65 documents the
  three-place sync requirement.

### Changed

- **`sam/template.yaml`** — `ConsoleUiUrlRewriteFunction` regex now
  matches `pipelines|assets|tasks|runs|backfills`. Inline comment warns
  that the list must stay in sync with two other files.
- **`ui/src/app/page.tsx`** — `validViews` array now includes
  `backfills`. Legacy `/?view=backfills` URLs now redirect to
  `/backfills/` instead of falling through to `/pipelines/`.

### Documentation

- **ADR #65** — Top-level view registration must be synced across
  three files: `ui/src/types/index.ts` (MAIN_VIEWS), `sam/template.yaml`
  (CloudFront function regex), `ui/src/app/page.tsx` (validViews).
- **CLAUDE.md rule #20** — Adding a top-level view requires updates
  in all three locations + both backend and frontend deploy in the
  same release. Tagged "this is the silent failure mode" with the
  exact symptom chain.

### Deploy notes

This release requires **both backend and frontend deploy**:

```bash
# Backend (CloudFront function change requires SAM deploy)
cd /home/makskoval/my/sam/slsflow
unzip -o ~/Downloads/slsflow-0.78.6.zip
ls -la sam/lambdas/console_api/slsflow  # verify symlink
cd sam
sam build && sam deploy --profile slsflow-dev

# Frontend
cd ../ui
npm run build
../sam/deploy-ui.sh slsflow-dev us-east-1 ./out --profile slsflow-dev
```

After both ship, hard-refresh the browser (CloudFront invalidation
clears the old function but the browser may have cached the
RootPage redirect chain).

### Tests

- No new tests (infrastructure-as-code change inside a YAML string
  isn't unit-testable). Mike to verify manually by clicking the
  Backfills tab after deploy.
- Total vitest: **783 passed** in 53 files (no change from v0.78.5;
  CloudFront and root page changes are infrastructure-level).

## v78.5 (0.78.5) - 2026-05-27

Fix: keyboard shortcut conflicts. v0.78.3 wired numeric keys `1`-`9`
to inner-surface tab switching (PipelineDetail viewMode,
AssetDetailPage tabs, TaskDetailModal, HelpModal), but App.tsx **already**
used `1`-`5` for top-level navigation. Both listeners fired on each
numeric keypress, producing unpredictable behavior — e.g. pressing `2`
on a Pipeline page navigated to Assets AND switched viewMode to Gantt
simultaneously.

### Fixed

- **Keyboard shortcut double-fire** on numeric keys. Inner-surface tab
  switching now uses letter keys matching the first letter of the tab
  name. Numeric keys are reserved exclusively for App.tsx top-level
  navigation. ADR #64.1 documents the conflict and the new convention.

### Changed (shortcut bindings)

- **PipelineDetail viewMode**: `1`/`2`/`3` → `d` / `g` / `c`
  (DAG / Gantt / Calendar).
- **AssetDetailPage tabs**: `1`-`6` → `o` / `s` / `p` / `e` / `c` / `l`
  (Overview / Schema / Partitions / Events / Checks / Lineage).
- **TaskDetailModal tabs**: `1`/`2`/`3` → `d` / `t` / `a`
  (Details / Timeline / Actions).
- **HelpModal tabs**: `1`/`2`/`3`/`4` → `s` / `i` / `b` / `a`
  (Shortcuts / Icons / Backfill / API).
- **App.tsx top-level navigation**: `1`-`5` unchanged.

### Removed

- `SHORTCUTS.TAB_1` through `SHORTCUTS.TAB_9` constants from the
  catalog. No consumers; keeping them invited future regressions of
  the same bug.

### Documentation

- ADR #64.1 — Revised key allocation (supersedes the numeric-tab
  guidance from ADR #64; rest of ADR #64 still applies).
- CLAUDE.md rule #19 updated:
  - Numeric `1`-`9` reserved exclusively for App.tsx top-level nav.
  - Inner tab containers use letter keys (first letter of tab name).
  - Pre-merge checklist: `grep` for the key in `ui/src` before adding
    any new shortcut.
- `HelpModal::KeyboardShortcutsTab` rewritten:
  - New group "Top-level navigation (numeric keys reserved)" lists
    `1`-`5` for Pipelines/Assets/Tasks/Runs/Backfills.
  - Separate groups for "Pipeline view modes" (D/G/C), "Asset detail
    tabs" (O/S/P/E/C/L), "Task Detail modal tabs" (D/T/A), "Help modal
    tabs" (S/I/B/A) — each showing actual letter keys.

### Tests

- Shortcut tests on PipelineDetail (3), AssetDetailPage (3),
  TaskDetailModal (2), HelpModal (3) rewritten to use letter keys.
- New HelpModal test: "KeyboardShortcutsTab lists numeric keys for
  top-level navigation" — guards against silent drift if the doc
  rewrite forgets to mention the global nav keys.
- Total vitest: **783 passed** in 53 files (was 782; +1 doc test).

## v78.4 (0.78.4) - 2026-05-27

Test coverage catch-up for v0.78.3 keyboard shortcuts. v0.78.3 shipped
shortcut wiring across 9 surfaces but only 3 had tests; this release
brings the remaining 6 surfaces to parity, plus introduces the first
`HelpModal.test.tsx` file. No behavior changes — pure test additions.

### Added

- **Keyboard shortcut tests** on every surface wired in v0.78.3 (per
  CLAUDE.md #19, ADR #64):
  - `AllTasksView.test.tsx`: +2 (`⌘R`, `/` focus filter)
  - `AllRunsView.test.tsx`: +1 (`⌘R`)
  - `AssetMatrixView.test.tsx`: +1 (`⌘R`)
  - `AssetDetailPage.test.tsx`: +3 (tabs `1`/`2`/`3`/`4` for Overview/
    Schema/Partitions/Events)
  - `PipelineDetail.test.tsx`: +3 (viewMode `1`=dag, `2`=gantt, `3`=
    calendar)
  - `BackfillModal.test.tsx`: +2 (`⌘↵` submits when valid, no-op when
    modal closed)
- **`HelpModal.test.tsx`** — new file (9 tests). Covers tab rendering,
  default tab landing, `1`/`2`/`3`/`4` switching, modal-closed no-op,
  grouped shortcut content (Global / List views / Detail pages / Tabs /
  Modals), and presence of `j`/`k` and `⌘↵` references in the help text.

### Internal

- `PipelineDetail.test.tsx` mock fix: `vi.mock('../hooks', …)` now
  composes with `vi.importActual` so the real `useKeyboardShortcuts` +
  `SHORTCUTS` reach the component. Previously, the hook was stubbed
  with `() => {}`, which made any keyboard shortcut test impossible.
  Also added `AuthProvider` to the `@/hooks/useAuth` mock (re-export
  chain through `hooks/index.ts`).
- `AllTasksView.test.tsx` mock fix: `useAllTasksQuery` mock now exposes
  `refetch` so `⌘R` exercises the same code path as the (unmocked)
  refresh button would.
- Total vitest: **782 passed** in 53 files (was 761 in 52; +21 tests,
  +1 file).

### Why a separate release

v0.78.3 satisfied CLAUDE.md #19 "wire shortcuts" but slipped on rule
#7 "finish what you start" — tests are part of done. Rather than
silently re-pack v0.78.3 with the tests bolted on, v0.78.4 is the
honest version bump: same behavior, properly tested.

## v78.3 (0.78.3) - 2026-05-27

Keyboard shortcut convention applied across the app. Codifies the
expected shortcut wiring per surface type (ADR #64) and adds a CLAUDE.md
rule (#19) requiring it on every new view/page/modal/tab before merge.

### Added

- **Standard keyboard shortcut convention** wired across all major
  surfaces. Mapping by surface type (per ADR #64):
  - **List views** (`BackfillsListPage`, `AllTasksView`, `AllRunsView`,
    `AssetMatrixView`): `⌘R` refresh, `/` focus filter (where applicable),
    `j`/`k` next/prev row, `Enter` open highlighted (BackfillsListPage).
  - **Detail pages** (`BackfillDetailPage`, `AssetDetailPage`):
    `⌘R` refresh, `Esc` back to list. `AssetDetailPage` also: `1`–`6`
    for tab switching.
  - **Multi-tab containers** (`TaskDetailModal`, `PipelineDetail`
    viewModes, `HelpModal`): `1`/`2`/`3`/`4` switch tab in declaration
    order.
  - **Modals with primary action** (`BackfillModal`): `⌘↵`
    (ctrl+enter) submit/start.
- **`SHORTCUTS` catalog extended** with `FOCUS_FILTER`,
  `OPEN_SELECTED`, `SUBMIT`, and `TAB_1` through `TAB_9`.
- **`HelpModal::KeyboardShortcutsTab` rewritten** to group shortcuts
  by surface type with explicit "Global / List views / Detail pages /
  Tabs / Modals" sections. Keeps the user-facing reference in sync
  with what's actually wired.
- **`bl-row--selected` BEM modifier** on `BackfillsListPage` so the
  j/k navigation highlight is visible (left blue border + hover bg).

### Fixed

- **Shortcut wiring gap**: every view, modal, and tab container added
  after v0.7x silently shipped without keyboard shortcuts, even where
  the visible buttons clearly invited it (Refresh, tab switch, modal
  Submit). All major surfaces now have appropriate shortcuts per the
  convention above.

### Internal

- ADR #64 — Standard keyboard shortcut convention (codifies the table
  and reserves single-letter keys for the standard mapping only).
- CLAUDE.md rule #19 — Keyboard shortcuts on every new surface.
  Means a PR adding a new list view without `⌘R` is incomplete in
  the same way a PR adding a new endpoint without an e2e test is
  (per existing rule #16).
- 9 new vitest tests covering shortcut wiring on `BackfillsListPage`
  (4), `BackfillDetailPage` (2), `TaskDetailModal` (3).
- Total vitest: **761 passed** (was 752, +9 new).

## v78.2 (0.78.2) - 2026-05-27

UX polish + cost-estimate removal. All visual changes; backwards-compatible
except the `estimated_sfn_cost_usd` field removal (see "Removed" below).

### Removed

- **`estimated_sfn_cost_usd` field** from `POST /api/backfill`,
  `POST /api/backfill?preview=true`, the backfill DDB record, and the
  UI (Cost column in `BackfillsListPage`, "Estimated cost" row in
  `BackfillDetailPage`, preview line in `BackfillModal`). ADR #53's
  cost preview methodology was technically sound but the "estimate
  alone" surface created systematic user confusion — "Cost: $0.0047"
  reads as actuals, but the value diverges from real SFN bills by
  1.5–3× on small backfills. Cost reporting (estimate + actual
  reconciliation + budgets) is a coherent Pro-tier feature spec'd in
  BACKLOG; shipping it as a complete workflow rather than half-
  delivering an estimate. ADR #62. Partial supersession of ADR #53.
- **`slsflow.partitions.PartitionRange.cost_estimate()`** SDK method.
  Recoverable from git tag v0.78.1 if/when Pro re-introduces.
- **`dal/ddb_schema.py BackfillCols.ESTIMATED_SFN_COST_USD`** constant.
- **`TestCostEstimate`** class in `tests/sdk/test_partitions.py` (5 tests
  removed per CLAUDE.md #11 — no skipped tests; class no longer exists).

### Fixed

- **Status pill invisible in light mode** on `BackfillsListPage` and
  `BackfillDetailPage`. Inline `style={{ background }}` with `color:
  white` rendered the pill invisible when background resolved to
  `var(--text-secondary)` (mid-grey) for `pending`/`canceled` statuses.
  Replaced with BEM modifier classes (`.bl-status-pill--running`,
  `--completed`, `--failed`, `--partial`, `--pending`, `--canceled`),
  each with tested foreground/background contrast for both themes.
- **Started By column displayed literal "unknown"** when backend
  returned the string `"unknown"` instead of `null`. New `formatUser()`
  helper collapses null, empty, whitespace, and any-case `"unknown"`
  to em-dash for consistent UX.
- **`"$—"` display** for backfills with null cost (now moot — column
  removed).

### Added

- **Segmented progress bar** on `BackfillsListPage` replaces the single
  solid fill. Each non-zero partition class (completed / failed /
  skipped / in-flight) renders its own colored segment, so users see
  backfill health at a glance instead of reading "2/5 (2 failed)".
  Running segment animates so active backfills are visually distinct
  from stopped.
- **Clickable partition cells and child rows** in `BackfillDetailPage`.
  Click a partition `2026-05-22` → opens `/pipelines/?pipeline=X&date=2026-05-22`.
  Click a child execution → opens that execution's DAG view. ADR #63.
  Both behaviors gated on optional `onPartitionClick` / `onChildClick`
  props for backwards compatibility. Keyboard a11y: Enter/Space on
  focused cells, `aria-label` for screen readers.
- **Relative timestamp on "Started"** column (`formatRelativeTime`).
  Shows "5m ago" / "3h ago" / "2d ago" / ISO date for older items.
  Full timestamp on hover via `title` attribute.
- **Contextual empty state** on `BackfillsListPage`. When filter is
  "All" and there are zero backfills, suggests "Start one from a
  Pipeline or Asset page" instead of generic "no match".
- **Filter chip active state contrast**. Active chip now has stronger
  blue glow (box-shadow) on top of the accent-blue background, so the
  "you are here" indicator survives at-a-glance use.

### Internal

- New formatters in `ui/src/utils/formatters.ts`: `formatUser`,
  `formatRelativeTime`. 12 unit tests pinning all cases.
- ADR #62 — Cost estimate removal.
- ADR #63 — Backfill detail navigation.
- Pro-tier cost reporting spec consolidated in BACKLOG.md under
  "Cost reporting (full workflow)" — supersedes the previous
  "Per-pipeline cost budget" entry.

## v78.1 (0.78.1) - 2026-05-22

Bug-fix release addressing three issues found during v0.78.0 external
review. No breaking changes; backwards-compatible bug fixes only.

### Fixed

- **`skip_on_backfill` runtime enforcement (ADR #60).** The DSL flag
  was declared, stored, and silently ignored at runtime — scrapers
  declared `skip_on_backfill=True` were running on every backfill.
  Fix: backfill API now reads the flag from `pipeline_registry` and
  injects the matching task IDs into `skip_task_ids`. Explicit
  `tasks=[...]` from the user overrides the flag (developer override
  wins). 4 contract tests pin all merge scenarios.

- **Pipeline-vs-asset modal asymmetry.** The Cascade section was
  hidden entirely for pipeline targets, making the two modals look
  gratuitously different. Fix: section header now always shows; for
  pipeline targets a placeholder explains "Not applicable for
  pipeline targets" (ADR #57 reaffirmed).

### Added

- **Task subset selection in BackfillModal (ADR #61).** Multi-select
  task picker inside the Options accordion of `BackfillModal`,
  visible only for pipeline targets. Default is "All tasks"
  (sends `tasks: null`); user-selected tasks send a positive subset
  to the API. Rows for `skip_on_backfill=True` tasks display a flag
  badge — picking such a task overrides the default skip (ADR #60).

### Internal

- New hook `usePipelineTasksList(pipelineName)` — lightweight
  `/pipeline-dag` projection to `[{task_id, skip_on_backfill?}, ...]`.
  Cached 60s in React Query.
- New helper `_compute_skip_task_ids(pipeline, task_subset)` in
  `routes/backfill.py` — unified merge of subset complement and
  skip_on_backfill flags.

## v78.0 (0.78.0) - 2026-05-20

### Backfill Unification (ADR #51)

**Major release**: unified backfill model — one endpoint, one orchestrator
SFN, one persisted record. Replaces six legacy code paths (pipeline-backfill,
asset-backfill, force-trigger, manual run, task-level run, matrix cell click)
with a single seed-driven flow.

#### Backend
- New `POST /api/backfill` endpoint with target/partitions/options/cascade payload.
  Replaces `/api/pipeline-backfill`, `/api/pipeline-force-trigger`, `/api/assets/backfill`.
- New `GET /api/backfills`, `GET /api/backfills/by-id`, `POST /api/backfills/cancel`,
  `POST /api/backfills/retry-failed`.
- New `slsflow-bulk-backfill` Standard SFN with Map iteration over partitions,
  cooperative cancel via DDB status check at each iteration, child SFN sync
  invocation with 24h timeout and retry (per ADR #54).
- New `backfills_repo` DAL with sentinel pipeline_name + record_type
  discriminator for filtering backfill records from execution lists.
- New `backfill-id-index` GSI on pipeline-tokens for child-execution lookup.
- Rename: `run_id` → `parent_execution_id` (resolves ADR #51 naming collision;
  TaskEvents GSI `run-index` → `parent-execution-index`).
- SFN templates (`dependency_wrapper`, `run_task`) propagate `backfill_id` and
  `partition_key` fields on every DDB write (3 sites each).
- Prepare_Task_Input now exposes `partition_key`, `backfill_id`, `is_backfill`
  variables to task code; legacy `minus_1_month`/`minus_3_months`/`day_of_year`/
  `week_of_year`/`is_reprocess` removed (ADR #51).

#### SDK
- New `slsflow.granularity` — `infer_cron_cadence()` per ADR #52 (standard
  cron, AWS rate(), shorthand).
- New `slsflow.partitions.PartitionRange` per ADR #58 — granularity-aware
  partition key formatting, range expansion, cross-granularity translation,
  cost estimation with 5000-partition hard limit.

#### UI
- New universal `BackfillModal` (seed-driven; replaces old `BackfillModal` +
  `AssetBackfillModal`).
- New `BackfillsListPage` (`/backfills/`) with status filters and progress
  bars.
- New `BackfillDetailPage` (`/backfills/{id}/`) with partition heatmap,
  cancel/retry actions, child executions table.
- New `useBackfillQueries` hooks: start / preview / list / detail / cancel /
  retry-failed.
- Entry points wired through `openBackfillModal({seed})` store action:
  PipelineDetail, AssetsView, AssetMatrixView (cell click), TaskDetailModal,
  AssetDetailModal.
- AllRunsView: new `Backfill` column linking to detail page.
- Header: new `Backfills` nav tab; keyboard shortcut `5`.

#### CLI
- New `slsflow backfill pipeline NAME --start ... --end ...` command.
- New `slsflow backfill asset NAME --start ... --end ... --cascade ...` command.
- New `slsflow backfills list/show/cancel/retry-failed` commands.
- Configuration via `SLSFLOW_API_URL` + optional `SLSFLOW_API_TOKEN` env vars.

#### Migration notes
- Old `useBackfillMutation` / `useAssetBackfillMutation` removed in UI.
- Old `BackfillModalProps` / `BackfillPayload` types removed.
- Old `routes/backfill.py` handlers (`force_trigger_dag`, `backfill_by_asset`,
  `backfill_pipeline`) removed; old `/api/pipeline-backfill`, `/api/pipeline-force-trigger`,
  `/api/assets/backfill` endpoints removed.
- Legacy `Python` and `flag` source variables removed from `task_variables`
  schema (jsonata source only post-v0.78).

#### Child SFN options end-to-end (audit-driven fixes)

External code review identified that several backfill options were
silently ignored by the run_task helper SFN — the API plumbed them
through bulk_backfill SFN, but the per-task child template didn't read
them. v0.78.0 now honors these end-to-end:

- **`task_subset` (skip_tasks)** — backend computes complement
  (`skip_task_ids`), bulk_backfill passes it via Input, generators.py
  forwards via wrapper input, run_task helper has a new
  `Check_Should_Skip_Task` Choice state at the very start. Tasks in
  the skip list emit a synthetic `status='skipped'` and terminate
  immediately. Downstream trigger_rules handling `none_failed_or_skipped`
  work correctly.
- **`cascade='none'` (_suppress_asset_event)** — `Check_Has_Outlets`
  Choice in run_task now AND-guards with `_suppress_asset_event` flag.
  When true, asset events are NOT emitted, so downstream consumers
  don't fire. Used by isolated backfills.
- **`cascade='all'` (cascade_all)** — forwarded through the chain to
  the notify helpers (consultation point for broader downstream).
- **Lambda packaging** — `sam/lambdas/console_api/slsflow` is a
  committed symlink to the repo-root `slsflow/` package. SAM's default
  Python builder follows the symlink, packaging the SDK as a normal
  subdirectory of the Lambda artifact. Zero-setup: `git clone` restores
  the symlink, `sam build && sam deploy` works as expected. No
  Makefile, no pre-build step, no extra tooling. (Earlier attempts
  with `BuildMethod: makefile` + relative paths and a vendor-copy
  `make sam-build` target were both abandoned — symlink is simpler and
  has no daily-workflow cost.)
- **SFN dynamic MaxConcurrency** — was hardcoded to 5, now reads from
  `$states.input.options.max_parallel`.
- **SFN skip_tasks JSONata** — was `? [] : []` (broken both branches);
  now reads from input.skip_task_ids correctly.
- **Misconfig guard** — `BULK_BACKFILL_ARN` env var is now validated
  BEFORE writing the DDB record, eliminating orphan pending records on
  misconfigured deploys.
- **UI old endpoints removed** — `useForceTriggerMutation`, `HelpModal`
  no longer reference deleted `/pipeline-force-trigger`,
  `/pipeline-backfill`, `/assets/backfill`. All flow through unified
  `/api/backfill`.
- **Ambiguous-cron selector visibility** — fixed regression where the
  granularity selector was hidden in the only case it should appear.

`options.force` and `options.incremental` accepted by the API for
backward compatibility but are documented no-ops in v0.78:
`force` is redundant with backfill semantics (a backfill bypasses
scheduled-run dependency wait by design); `incremental` was a v0.77
concept that didn't carry forward.

#### Documentation
- 8 new ADRs (#51–#58) covering Backfill Unification, granularity inference,
  cost methodology, bulk-backfill SFN architecture, scheduled runs, status
  model, cascade semantics, and partition keys/range expansion.
- CLAUDE.md expanded with 6 new principles (#13–#18) focused on test
  quality (integration contracts, boundary mocking, smoke before tag, e2e
  for new endpoints, cross-system integration verification, YAGNI).

#### Quality audit & quick wins (post-initial v0.78 work)
- **Quick win #1 + #9** — cron string display next to inferred granularity
  in BackfillModal preview, plus warning banner when cron is ambiguous.
- **Quick win #3** — CSV export of partition status from BackfillDetailPage.
  Download button → file with partition_key, status, child execution IDs.
- **Quick win #4** — client-side pipeline-name filter on /backfills/ list page.
- **Quick win #7** — concurrency guard: starting a backfill against a pipeline
  that already has an active backfill is rejected with 409
  `concurrent_backfill_active` unless `options.allow_concurrent=true`.
- **Quick win A** — granularity override selector in BackfillModal when
  cron is ambiguous. Backend accepts `granularity_override` field;
  honored only when `cron_was_ambiguous=true`, else 400
  `granularity_override_not_allowed`. Closes the gap where the warning
  banner told users to "override via the granularity selector" that
  didn't exist.
- **Quick win D** — active backfill count badge on the Backfills nav
  tab. Reuses existing `GET /api/backfills?status=active` query (5s
  polling). Pattern matches Slack/GitHub/Linear unread indicators —
  situational awareness without clicking the tab.
- **UI test coverage gap closed** — `BackfillModal` (7 tests),
  `BackfillDetailPage` (8), `BackfillsListPage` (6), `useBackfillQueries` (8).
  Per CLAUDE.md #7 / #16.
- **DDB schema constants** — `dal/ddb_schema.py` enforces field-name
  contracts so a rename in production code triggers a failing test
  (regression for the v0.78 `pipeline_status` vs `status` audit finding).
- **Moto-based integration tests** — `tests/integration/test_backfill_collision.py`
  exercises `put_if_new` against real-DDB-behavior in-memory fake, not just
  pytest-mock stubs.
- **Conditional backfill_id put** — `backfills_repo.put_if_new()` with retry
  loop (5 attempts) handles the ~10% birthday-paradox collision probability
  at 30k retained records. 503 `id_space_exhausted` on saturation.

#### Quality
- 863 SDK/backend tests pass.
- 296 console_api Lambda tests pass (+36 from initial v0.78 — schema
  constants, collision retry, concurrency guard, real skip_completed,
  granularity override, retry-failed granularity preservation).
- 30 integration tests pass (+5 moto-based DDB conditional put).
- 713 UI tests pass (+32 covering 4 previously-untested components and
  the active-backfill badge).
- 12 e2e backfill tests (`tests/e2e/test_backfill.py`, marked `@smoke`,
  skip-if-no-`SLSFLOW_API_URL`).
- All gates green: `cfn-lint`, JSONata compile (617 expressions), `tsc --strict`.

## v77.2 (0.77.2) - 2026-05-19

### Housekeeping release — quality audit follow-up

Pure cleanup release, no behavior or API changes. Four small fixes
raised during a code-quality audit; each is independently low-risk
which is why they're bundled instead of deferred.

#### Fix 1: Doc drift — route count

**Symptom.** Several docs (CLAUDE.md, README, CONTRIBUTING, docs/README,
BACKLOG section "Current Lambdas") said "49 routes" or "49 endpoints"
in the Console API, but the real `ROUTES` dict in `main.py` has had
52 entries since v0.77.0 (after `/api/assets/drift` and `/api/assets/matrix`
landed). `tests/sdk/test_templates.py` already asserts `len(ROUTES) == 52`,
so the drift was docs-only — but it was visible drift, which erodes
trust in every other number in the docs.

**Fix.** Updated all 6 stale references to "52". Left the historical
entry in `BACKLOG.md` line 88 (`Route table (49 routes, replaces
if/elif chain)`) untouched — that's a completed-achievement marker
recording the count at the time the route table was introduced, not
a live spec.

#### Fix 2: `cfn-lint` enforced locally and in CI

**Context.** CLAUDE.md Principle 4 says "Every change goes through:
pytest + cfn-lint + syntax check." `cfn-lint` was missing in two
places:

- `make lint` (and therefore `make check`) — local devs running
  the pre-commit gate didn't run it, so a CFN regression could
  reach push.
- `.github/workflows/ci.yml` — CI had no job running it, so a
  push could land if local was also skipped.

**Fix.** Added in both:

- `make lint` now runs `cfn-lint sam/template.yaml` after the
  Python syntax and JSON template checks, with a guard that
  prints an install hint (`pip install cfn-lint`) if the binary
  isn't available.
- New `cfn-lint` job in `.github/workflows/ci.yml`, parallel
  to the existing `python` / `lambdas` / `sfn-templates` / `ui`
  jobs. Kept as its own job (rather than tacking onto `python`)
  so a CFN regression is visible in the GitHub Actions UI
  without scrolling through unrelated test logs.

Template was already lint-clean (0 errors); the gates just
enforce it going forward in both places.

#### Fix 3: Error visibility on 4 silent excepts in Lambdas

**Background.** ADR #38 (Error Visibility — Product Requirement) says
every error must be visible to the operator. Four `except Exception:`
clauses in production Lambdas were swallowing failures silently:

| File | Function | Default on error | Risk |
|------|----------|------------------|------|
| `notify_asset_subscribers/index.py:181` | `_check_freshness` | return True ("fresh") | **High** — masks systematic timestamp parse failures across an entire pipeline group |
| `check_assets/index.py:401` | `_is_fresh` | return False ("not fresh") | Low — fails-safe (waits for next event) but still invisible |
| `console_api/routes/executions.py:548` | `get_execution_pause_status` | return False ("not paused") | Low — false negative means one extra poll, never an unintended resume |
| `console_api/routes/tasks.py:899` | `get_task_events` | task_run_id fallback | Low — GSI query downstream still works |

**Fix.** All four now emit a `Warning:`/`log.warn` line that includes
the function name, the input that triggered the failure, and the
exception type — so a single jq query against CloudWatch surfaces
them. Return values are preserved unchanged — the goal is visibility,
not behavior change.

The other 6 silent excepts in `slsflow/ai/*` and 1 in
`slsflow/config.py` are SDK-side, lower-priority, and tracked in
BACKLOG for a follow-up pass.

#### Fix 4: Dead CSS cleanup — 119 classes, ~700 lines removed

**Context.** v0.70.17–18 deleted 28 dead `.module.css` files. Inside
the surviving global CSS modules (`_assets.css`, `_tasks.css`, etc.),
older Asset View / Pipeline Detail iterations had left ~120
BEM-prefixed classes that no `.tsx` file references anymore.

**Verification method (three-pass strict verifier).** False positives
in dead-CSS detection come from three sources:

1. Template-literal composition — `\`task-icon-${status}\``
   produces `.task-icon-running` etc. at runtime, but the string
   never appears verbatim in source.
2. CSS parent-selector usage — `.parent .child` references `.parent`
   even when `.parent` is itself only used as a scope, not a class
   set on any element.
3. Framework-injected classes — `.react-flow__node`, etc.

The verifier handles all three: scans every backtick string for
`<prefix>-${...}` patterns anywhere inside (not only at start);
treats CSS rules as deletable only when EVERY class in the selector
is dead; lists framework classes as always-keep. Survivors of the
filter were spot-checked manually.

**Result.** 119 verified-dead classes removed across 6 CSS files:

| File | Classes removed |
|------|-----------------|
| `_utilities.css` | 43 (mostly leftover Tailwind-shadowing utilities like `.text-xl`, `.flex-1`, `.gap-sm`) |
| `_assets.css` | 30 (Asset List sidebar, Queued Events, Lineage placeholders) |
| `_dag.css` | 13 (Logs panel, container tabs `.ct-container--*`) |
| `_tasks.css` | 15 (DSL container, metrics chart bars, zoom controls) |
| `_mobile.css` | 6 (within `@media (max-width: 768px)` blocks) |
| `_layout.css` | 6 (Stats grid, SLA Badge variants) |
| `_navigation.css` | 3 (`.nav-pill--lg/sm`, `.nav-tab--md`) |
| `_accessibility.css` | 2 (sub-selectors in `:focus-visible` comma lists) |
| `_pipeline-pause.css` | 1 (`.task-node` — never rendered) |

Compound modifier rules whose dead parent was the load-bearing
selector (`.av-asset-item.selected`, `.sla-badge.warning`,
`.wait-countdown-box.completed`, etc.) were removed together with
the parent, since the rule cannot match without it.

CSS module totals: 7942 → 7242 lines (−8.8%). Audit script now
reports 78 "potentially unused" (down from 197); those 78 are the
template-literal composition + parent-selector + framework cases
the verifier intentionally kept.

#### Quality gates

All gates green:

- `ruff check slsflow/ sam/lambdas/` — 0 errors
- `cfn-lint sam/template.yaml` — 0 errors
- `make check-versions` — 0.77.2 consistent across `pyproject.toml`,
  `slsflow/__init__.py`, `ui/package.json`, `ui/package-lock.json`
- `make sync-constants` — `_shared` ↔ console_api in sync
- `make smoke-pipelines` — all 6 `dag.py` import
- Python tests: 712 passed + 16 skipped (SDK / backend / integration)
  + 193 (console_api) + 56 (evaluate_deps) + 12 (notify_asset_subscribers)
  + 19 (check_assets) = **992 passing**
- JSONata: 34 explicit + 563 compile
- `tsc --noEmit` — 0 errors
- `eslint` — 0 errors, 35 pre-existing warnings (untouched)
- `vitest run` — 716 passed
- `next build` — successful

#### Files changed

**Python (4 files):**
- `sam/lambdas/notify_asset_subscribers/index.py` — added Warning log
  to `_check_freshness` silent except
- `sam/lambdas/check_assets/index.py` — added Warning log to `_is_fresh`
  silent except
- `sam/lambdas/console_api/routes/executions.py` — added `log.warn` to
  `get_execution_pause_status` silent except
- `sam/lambdas/console_api/routes/tasks.py` — added `log.warn` to
  `get_task_events` silent except

**CI (2 files):**
- `.github/workflows/ci.yml` — new `cfn-lint` job
- `Makefile` — `cfn-lint sam/template.yaml` added to `make lint`

**CSS (9 files):**
- `ui/src/styles/modules/_accessibility.css`
- `ui/src/styles/modules/_assets.css`
- `ui/src/styles/modules/_dag.css`
- `ui/src/styles/modules/_layout.css`
- `ui/src/styles/modules/_mobile.css`
- `ui/src/styles/modules/_navigation.css`
- `ui/src/styles/modules/_pipeline-pause.css`
- `ui/src/styles/modules/_tasks.css`
- `ui/src/styles/modules/_utilities.css`

**Docs (6 files):**
- `CLAUDE.md` — 3 × "49 routes" → "52 routes"
- `README.md` — "49 endpoints" → "52 endpoints"
- `docs/README.md` — "49 endpoints" → "52 endpoints"
- `docs/reference/BACKLOG.md` — current-state "49 routes" → "52 routes";
  added 7 follow-up items to backlog
- `CONTRIBUTING.md` — "49 endpoints" → "52 endpoints"
- `CHANGELOG.md` — this entry

**Version (4 files):**
- `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` — 0.77.1 → 0.77.2

#### Deferred to backlog (intentionally not in this release)

- `useUrlSync.ts` refs updated in render body (react-hooks/refs warning)
  — real React 19 anti-pattern, needs its own commit + tests for
  back/forward URL sync
- `_shared/logger.py` extraction + `print()` → structured log migration
  in `evaluate_deps` and `notify_asset_subscribers` — changes
  CloudWatch log format, needs separate release in case any Insights
  queries / Slack alerts parse the current `[evaluate_deps] ...`
  format
- `ruff format` on the 82 currently-unformatted files — style-only
  but creates large git-blame churn, deserves its own commit
- mypy as blocking CI gate — requires a baseline cleanup pass first
- `generators.py` split into submodules (1719 lines, 38 functions)
  — refactor, not fix; do next time we land a feature touching it
- Large UI component splits (`AssetMatrixView` 825 lines,
  `AssetLineageFlow` 798, `AssetsView` 775) — same rationale
- 6 silent excepts in `slsflow/ai/*` and 1 in `slsflow/config.py`
  — SDK-side, lower priority than the Lambda ones fixed here

---

## v77.1 (0.77.1) - 2026-05-19

### Asset Matrix UX fixes from post-deploy review

Three follow-up issues raised after v0.77.0 deploy. None blocked the
release but combined into a noticeable friction in production use.

#### Fix 1: Empty state no longer traps users

**Symptom.** Switching Granularity to a value with no matching assets
(e.g., "Weekly" when all assets are daily) replaced the entire UI with
an empty state containing only a "Clear filter" button. That button
called `setRangeDays(rangeDays)` — a no-op — and there was no way to
return to the working view without reloading the page.

**Fix.** The toolbar (Granularity / Range / Status / Groups dropdowns +
Refresh) now stays visible regardless of whether rows are present. The
empty state moved inside the grid area and became context-aware: it
identifies the most likely cause (granularity / status filter /
deselected groups / group URL filter) and offers a recovery button
that fixes that specific cause — "Switch to Daily", "Show all statuses",
"Select all groups", etc.

The previous single-purpose "Clear filter" button is gone; recovery
actions are always pointed at the real cause now.

#### Feature: Group multi-select filter

**Context.** Group filtering used to come exclusively from the URL
(`?group=acme`), inherited from navigation out of the Catalog view.
Users with multiple groups in their workspace had no way to compare
groups in a single matrix view.

**Fix.** New "Groups" dropdown in the matrix toolbar (renders only
when ≥ 2 groups present, so single-group workspaces aren't cluttered).
Click opens a checkbox popover listing every group in the current data,
with "Select all" / "Clear" actions. Default state is `null` = "all
groups visible", so future data refreshes that introduce new groups
include them automatically.

#### Confirmation: all 5 cell statuses retained

The 5 cell types (materialized / failed / running / queued / missing)
all surface real states from `pipeline-tokens` and are kept as-is. The
`Status` filter dropdown exposes each — useful during incidents to
filter "only failed" or "only queued" rows.

#### Files changed

  - `ui/src/components/AssetMatrixView.tsx` — empty state restructure,
    new `GroupFilter` component, granularity-aware empty messaging
  - `ui/src/styles/modules/_assets.css` — popover styles for
    `.amv-group-filter*`

#### Test coverage

  - +4 new frontend tests for v0.77.1 recovery flows
  - 716 frontend tests total (all passing)
  - No backend changes — backend test count unchanged

#### Code cleanup (CLAUDE.md #1)

Removed 16 pre-existing ruff warnings that accumulated over prior
releases, with locked-in test coverage so future refactors can't
silently re-introduce the dead patterns:

  - **6× F541 (empty f-strings)** — `f'literal text'` → `'literal text'`.
    Cosmetic; no behavior change.
  - **9× F841 (unused locals)** — actual dead code, including one
    wasted DynamoDB query in `executions.py::pause_execution` whose
    result was never read (was burning RRU for no reason), and two
    unused fields (`source_task`, `source_dag`) in the
    `notify_asset_subscribers` Lambda handler.
  - **1× F841 (intentional side-effect)** — `result = sfn.start_execution(...)`
    in `slack.py::slack_action_restart` rewritten as a bare call.

**New tests (+16 in console_api)** lock in behavior of the cleaned
functions so the dead patterns can't return silently:

  - `test_executions_pause.py` (4 tests) — `pause_execution` happy path,
    409 on terminal, 500 on DDB failure, **no redundant query**.
  - `test_slack_actions.py` (9 tests) — `slack_action_skip` happy path,
    409 terminal, 404 missing, 400 missing param, orchestration callback
    when token present / absent. `slack_action_restart` SFN side-effect
    fires with helper ARN, falls back to stop+reset without ARN, 404
    on missing task.
  - `test_pipelines_list_cleanup.py` (3 tests) — `list_pipelines` empty
    registry, registry entries surface correctly, no-stats path skips
    expensive scan.

Inlined here rather than deferred per Mike's direct request
("давай фіксити прям тут бо воно пізніше забудеться").


## v77.0 (0.77.0) - 2026-05-18

### Asset granularity — declarative partition cadence (ADR #50)

Response to tech lead Myroslav's review of the v0.76 Asset Matrix:
"granularity is hardcoded as day — reality is more complex." v0.77 adds
explicit per-asset cadence declarations, advisory Glue auto-detect at
deploy time, and runtime drift detection so the silent default never
lies for long.

#### What's new

**Asset DSL** (`slsflow/assets.py`):
  - New `granularity` kwarg: `"hourly" | "daily" | "weekly" | "monthly"`
    (IDE autocompletes via `Literal` type).
  - New `partition_start` kwarg (optional) — must match granularity format.
  - Default `granularity="daily"` — backward compatible.

```python
Asset("acme/orders")                                  # default daily
Asset("acme/weekly_summary", granularity="weekly")
Asset("acme/monthly_report", granularity="monthly",
      partition_start="2024-01")
Asset("acme/hourly_events", granularity="hourly")
```

**Matrix endpoint** (`GET /api/assets/matrix`):
  - New `granularity` query param (default daily). Date format of
    from/to adapts: `YYYY-MM-DD` / `YYYY-Www` / `YYYY-MM` / `YYYY-MM-DDTHH`.
  - Filter mode: matrix shows only assets matching requested granularity.
  - Cell payload includes per-status counts so tooltips surface re-runs.

**Drift detection** (new endpoint `GET /api/assets/drift`):
  - Counts successful materializations over last 30 days per asset,
    compares to declared granularity expectations.
  - Severity tiers: `≥0.5` → healthy (no entry), `0.25-0.5` → warning,
    `<0.25` → critical.
  - UI binds result to per-row badge with hover tooltip.

**Glue auto-detect** (`slsflow-deploy`):
  - Reads Glue `PartitionKeys` for `from_glue_table`-backed assets,
    infers granularity from naming conventions.
  - Advisory only — declared value wins; mismatches print warnings:
    ```
    ⚠ acme/weekly_x: declared daily but Glue partition keys
      ['year', 'week'] suggest weekly. Update granularity="weekly".
    ```

**UI** (`AssetMatrixView`):
  - Three dropdowns: Granularity / Range / Status.
  - Column headers adapt to granularity (Day/Week/Month/Hour formats).
  - Drift badge (yellow/red triangle) on rows with drift.
  - Tooltip count surfaces hidden re-runs.

#### Backward compatibility

  - Existing `Asset(...)` calls keep working (default daily).
  - Pre-v0.77 pipeline_registry records (no `granularity` field)
    interpreted as daily.
  - v0.76 matrix API clients keep working — `granularity` defaults to
    daily server-side.
  - No DDB schema changes, no SFN template changes, no new tables.

#### Cost impact

  - Matrix endpoint: same ~35 RRU/render as v0.76.
  - Drift endpoint: ~35 RRU per 5-min refresh = ~$0.13/month per 100
    SaaS customers. Negligible.
  - Glue auto-detect: 1 GetTable call per Glue-backed asset at deploy.

#### Test counts

  - SDK: +16 partition + 16 Glue inference = 32 new
  - Backend matrix: +11 granularity/count tests = 38 total
  - Drift endpoint: 11 new tests
  - Frontend: +10 (granularity/status/count/drift badge) = 32 total

#### Out of scope (explicit non-goals, see ADR #50)

  - Multi-dimensional partitions (region × date)
  - Dynamic partitions (sensors)
  - Unified multi-granularity view → v0.78 if requested
  - Data quality on cells → integrate with Great Expectations later
  - `partition_value` ≠ `execution_date` → v0.79 (SFN template change)


## v76.1 (0.76.1) - 2026-05-13

### Asset Matrix view — bugfix release

Post-deploy bug fixes for the v0.76.0 Asset Matrix view. Both reported
from production after first deploy:

#### Fix 1: All cells appearing as ⚪ Missing (no producer cross-reference)

**Root cause.** `_build_asset_to_tasks_index` in `routes/matrix.py`
looked up the producer task identifier as `task.get('task_name')` /
`task.get('name')`. The canonical field in `pipeline_registry.tasks[]`
is `task_id` (see `_build_assets_from_pipelines` for the established
pattern). The lookup returned `None` for every task, so the
asset→producers reverse index was empty, so `_derive_cell` never found
any matching task records, so every cell fell through to "missing".

The field is also `task_name` in `pipeline-tokens` records (different
table, short identifier matches `task_id` value), which is what
misled the initial implementation. The CLAUDE.md #2 rule ("follow
existing patterns — `grep` first") would have caught this — corrected
the lookup to match the canonical `task_id` key used everywhere else.

**Fix.** `_build_asset_to_tasks_index` now reads `task.get('task_id')`
first, falling back to `task_name`/`name` only for forward
compatibility. Test helper `_pipeline_with_outlet` updated to mirror
the real schema.

#### Fix 2: Layout — large empty gap between ASSET column and matrix grid

**Root cause.** `.amv-grid` had `min-width: 100%` and `.amv-asset-name`
had `min-width: 240px` (no max). When the viewport was wider than the
table's natural content width, the browser distributed the extra
horizontal space inside the table — and the ASSET column absorbed it
because it was the only column without a fixed `width`. Result: a
short asset name like `attribute_tags` would render in a column ~500px
wide, with the date grid pushed far to the right.

**Fix.** ASSET column now has explicit `width: 240px` (with matching
`min-width` / `max-width`) so it doesn't absorb extra space; long
names ellipsis. Date cells widened from 40 → 48 px for better
readability. `.amv-grid` switched from `min-width: 100%` to `width:
auto` so the table sits at content width and whitespace on wide
screens goes to the right of the table, not inside it. Mobile
breakpoints (≤1024 / ≤768 / ≤480 px) follow the same pattern with
appropriately smaller fixed widths (200 / 160 / 130 px).

#### Deploy notes

  - SAM redeploy required (matrix endpoint logic change)
  - UI redeploy required (CSS only — no JS / TSX changes)
  - No DDB or SFN changes
  - Same backward-compatibility guarantees as v0.76.0


## v76.0 (0.76.0) - 2026-05-12

### Asset Matrix view — cross-asset temporal grid (ADR #49)

A new **Matrix** tab in the Assets page renders a 2D grid: rows are
assets (grouped by `group`), columns are dates over a configurable
range (5, 7, 14, 30, or 60 days). Each cell shows the asset's status
on that date — answering *"what's broken, and when did it start?"* at
a glance.

The matrix is the gap industry tooling leaves open: Airflow Grid is
per-DAG, Dagster's Asset Catalog is a list, Dagster's Partition Status
is single-asset. A cross-asset temporal view is what operators reach
for during outage forensics or partition-status review.

#### Cell types

| Cell | Meaning |
|------|---------|
| 🟢 Materialized | Latest producer-task record has `status='success'` |
| 🔴 Failed | Latest producer-task record has `status='failed'` |
| 🟡 Running | Some producer task is currently running (running beats older finalized records) |
| 🟠 Queued | No producer record yet, but at least one consumer DAG awaits this asset |
| ⚪ Missing | No producer record and no consumer waiting |

The Queued cell answers the operator question *"which assets are
blocking downstream DAGs right now?"* It's derived from `asset_schedule`
declarations in `pipeline_registry` — a single scan per request covers
the whole date range. Clicking a queued cell opens the Backfill modal
pre-filled with that (asset, date) just like missing and failed cells.

Staleness is intentionally *not* a matrix cell type — it's a "now"
concept and would misrepresent historical truth at each date. The
Catalog tab continues to show staleness as before.

#### Architecture: state-based derivation, not event sourcing

Cell status is **derived** from canonical state that already exists in
the project. **Nothing new is written** to support this view.

Sources:

  - `pipeline-tokens.date-pipeline-index` (existing GSI) — per-task
    status, finished_at, error, etc. by date
  - `pipeline_registry.tasks[].outlets` — task → produced assets
  - `pipeline_registry.asset_schedule` — DAG → consumed assets

The matrix endpoint is a *projection* over these tables. See ADR #49
for the full design history including why we initially shipped a
different (event-sourcing) approach and reverted within the same
release — short version: it duplicated state that `pipeline-tokens`
already canonically holds, violating CLAUDE.md #12, and added
material per-task cost that hurt the project's pricing positioning.

#### Regenerate semantics

When backfill re-runs a date, `pipeline-tokens` holds multiple records
for the same (task_name, date) pair. Resolution: running beats older
finalized records (so operators see what's happening now); among
finalized records, latest `finished_at` wins. Materialized →
backfill-failed correctly shows 🔴 Failed with the backfill's error.

#### What's in the release

  - **No SFN template changes.** `RunTaskHelperSfn` is bit-identical to
    v0.75.8 — the matrix view is a pure read-side feature.
  - **New endpoint** `GET /api/assets/matrix?from=&to=&group=&include_views=`:
    parallel `Query` on `pipeline-tokens.date-pipeline-index` per date,
    plus one Scan of `pipeline_registry` for outlets and consumer
    schedules. Hard cap of 60 days per request.
  - **New component** `AssetMatrixView` with sticky headers, weekend
    dimming, today highlighting, group summaries, keyboard navigation,
    and aria-labels on every cell (color-blind / screen-reader
    accessible).
  - **Click-to-backfill**: missing, failed, and queued cells open the
    existing `AssetBackfillModal` pre-filled with that (asset, date).
    The modal gained two optional props (`defaultStartDate`,
    `defaultEndDate`) — non-breaking.
  - **Failure tooltip** shows the actual `error` field from
    `pipeline-tokens` for failed cells, so operators see *why* without
    clicking through.
  - **Responsive (ADR #40)**: range default shrinks (14 → 7 → 5 days)
    and cells narrow at ≤1024, ≤768, ≤480 px breakpoints. Rules in
    `_mobile.css`.

#### Migration

None. Zero schema changes, zero data migration. The view goes live the
moment the Lambda code deploys.

#### Cost

Verified against AWS pricing (DynamoDB on-demand $0.125/1M eventual
reads, $0.625/1M writes):

  - Per task with outlets: **$0 added** (no SFN changes, no DDB writes)
  - Per matrix render: ~28 RRU (14-day range), one extra `pipeline_registry`
    scan
  - Single-tenant cost addition with 30 s polling and 4 h/day usage:
    **~$0.05/month**
  - 100-customer SaaS estimate (500 tasks/day each): **~$3-8/month total**

Approximately 98 % cheaper than the rejected event-sourcing approach.

#### Deploy notes

  - SAM redeploy required (Lambda code change only — SFN templates
    unchanged, so the SFN definition update phase is a no-op)
  - UI redeploy required
  - Backward compatible — no DDB schema migration, no breaking API
    changes

#### Out of scope (deferred for future releases)

Per-tenant permissions, pre-computed snapshots, real-time SSE,
cron-aware "expected" definitions, bulk cell select, column filters,
export. Documented in ADR #49 §Out of scope.

#### Files touched

Backend (new endpoint, no SFN changes):
  - `sam/lambdas/console_api/routes/matrix.py` (new, 383 lines)
  - `sam/lambdas/console_api/routes/__init__.py` (export)
  - `sam/lambdas/console_api/main.py` (route entry)
  - `sam/lambdas/console_api/tests/routes/test_matrix.py` (new, 27 tests)
  - `tests/sdk/test_templates.py` (route count assertion bump)

Frontend (new tab + cell renderer):
  - `ui/src/components/AssetMatrixView.tsx` (new)
  - `ui/src/components/AssetMatrixView.test.tsx` (new, 22 tests)
  - `ui/src/components/AssetBackfillModal.tsx` (optional default dates)
  - `ui/src/components/AssetsView.tsx` (third tab wired)
  - `ui/src/hooks/queries/useAssetQueries.ts` (new hook + types)
  - `ui/src/hooks/queries/index.ts` (barrel re-export)
  - `ui/src/lib/queryClient.tsx` (queryKey helper)
  - `ui/src/styles/modules/_assets.css` (matrix BEM rules)
  - `ui/src/styles/modules/_mobile.css` (responsive breakpoints)

Docs:
  - `docs/reference/DESIGN_DECISIONS.md` (ADR #49 — full history)
  - `docs/features/ASSETS.md` (Matrix section)


## v75.8 (0.75.8) - 2026-05-08

### AssetDetailPage refactor — split monolith into tab components (ADR #48)

The asset-detail view grew from a modest component to 1124 lines across
v0.75.0 → v0.75.7 as the schema feature, drift detection, copy buttons,
status banner refinements, and cross-account/region support all landed
inline in `AssetDetailPage.tsx`. By v0.75.7 the file had crossed the
readability and maintainability threshold — any change required
scrolling through ~1000 lines of unrelated tab code.

This release does not change behaviour. It restructures the page into
an orchestrator plus one component per tab, with the architectural
rationale and procedural follow-up documented so the next contributor
doesn't have to re-derive the design.

#### Structure after refactor

```
ui/src/components/
├── AssetDetailPage.tsx        ← orchestrator (~370 lines):
│                                 header, tab nav, body dispatcher,
│                                 sidebar, page-scoped queries
└── asset-tabs/
    ├── types.ts               ← TabContext + AssetDerived contracts
    ├── index.ts               ← barrel re-export
    ├── TabOverview.tsx        ← (~245 lines)
    ├── TabSchema.tsx          ← (~175 lines)
    ├── TabPartitions.tsx      ← (~125 lines)
    ├── TabEvents.tsx          ← (~85 lines)
    ├── TabChecks.tsx          ← (~30 lines, placeholder)
    ├── TabLineage.tsx         ← (~40 lines, wraps AssetLineageFlow)
    ├── GlueSyncPanel.tsx      ← (~205 lines, used by TabSchema)
    ├── SchemaCopyButtons.tsx  ← (~110 lines, used by TabSchema)
    └── glueHelpers.tsx        ← humanizeGlueError + DriftSection
```

Total lines essentially unchanged (~1556 across all files vs 1124 in
the monolith — the increase is docstrings + interface declarations,
not duplicated logic). The win is per-file readability and isolated
testability, not LOC reduction.

#### State allocation (the heart of the design)

- **Page-scoped state stays in the orchestrator**: `activeTab`,
  `useAssetEventsQuery` (shared by 3 tabs), `useAssetGlueSchemaQuery`
  (must outlive tab switches), `derived` memoization. Anything that
  would surprise the user by resetting on tab switch.
- **Tab-local state stays inside the tab**: `selectedPartition` in
  TabPartitions, `selectedEvent` in TabEvents, `copied` in
  SchemaCopyButtons. Interaction state where reset-on-navigate is
  acceptable UX.

#### Props contract — `TabContext`

Every tab receives a `TabContext` (defined in `asset-tabs/types.ts`)
with the seven fields used by 2+ tabs. Tab-specific extras extend
the context on the tab's own Props interface (e.g. `TabSchemaProps`
adds `derived`, `schemaConflicts`, `glueQuery`). This pressure keeps
the shared context narrow — when a field is needed by exactly one
tab, putting it on `TabContext` would force every other tab to
accept a useless prop.

#### ADR #48 — full design rationale

The decision document captures:

- Why React Context was rejected (hides dependency graph, harder
  to test, encourages "since we have it, we'll use it everywhere"
  creep)
- Why lazy-loading tabs was deferred (no measurable bundle pressure)
- The mechanical refactor triggers — when to apply this pattern
  elsewhere in the codebase
- The state-allocation rule in one sentence: "If losing this on
  tab-switch would surprise the user, hoist it; otherwise it's
  tab-local"

#### `docs/development/ADDING_ASSET_TABS.md` — procedural howto

Step-by-step procedure for adding a new tab, covering:

- Decision tree before writing code (is this a tab or a section?)
- File template with required conventions (`adp-content` wrapper,
  BEM classes, no `.module.css`)
- Barrel-export wiring, `TabId` extension, orchestrator dispatch
- When to lift state to orchestrator vs keep it tab-local
- Required tests at minimum (empty state, happy path, interactions)
- Anti-patterns to avoid (Context for prop-drilling, query in tab
  body, "small helper" turning into 80 lines)
- Worked examples (TabChecks as minimal, TabSchema as complex)
- Pre-ship checklist

### Fixture regeneration script committed

`tools/regen_ddl_parity.py` — committed script that regenerates
`tests/fixtures/ddl_parity.json` from the current SDK output. Closes
the loop on ADR #46's parity-test pattern: previously the fixture
was generated by a one-shot Python snippet that lived nowhere
committed. Now a future maintainer who changes `_render_glue_ddl`
has a clear path: edit the renderer, run `python3 tools/regen_ddl_parity.py`,
update the TypeScript mirror, run both parity tests.

The script includes:

- Top-of-file docstring explaining when to run vs when not to run
  (regenerating is NOT a fix for failing parity — figure out which
  renderer drifted)
- Path resolution from script location (runs from anywhere)
- All 6 canonical fixtures inline so the script is self-contained
- "Next steps" output telling the user which tests to run after

### Tab unit tests — 63 new cases (closing CLAUDE.md #7 + #11 debt)

The v0.75.8 split created 9 new tab/sub-component files. The initial
implementation passed only because the existing 46 `AssetDetailPage`
integration tests still rendered the page successfully — but no tab
had its own unit tests. A self-audit caught this:
`docs/development/ADDING_ASSET_TABS.md` (added in the same release)
states "Required tests at minimum: empty state, happy path, each
interactive element", and the implementation violated its own rule.

Closes the gap with one test file per new component:

| File                              | Tests | Covers                                                   |
|-----------------------------------|------:|---------------------------------------------------------|
| `TabChecks.test.tsx`              |     2 | Placeholder renders, copy stays stable                  |
| `TabLineage.test.tsx`             |     5 | Prop forwarding to AssetLineageFlow                     |
| `TabEvents.test.tsx`              |     6 | Empty state, list, selection, metadata, status icons    |
| `TabPartitions.test.tsx`          |     6 | Empty, summary, list, range labels, click → detail      |
| `TabOverview.test.tsx`            |    14 | Banner cases, description, schema summary, lineage, latest exec, tags |
| `SchemaCopyButtons.test.tsx`      |     5 | All 3 copy actions, clipboard, visual feedback          |
| `GlueSyncPanel.test.tsx`          |    11 | All 5 body branches, header scope variants, refresh     |
| `TabSchema.test.tsx`              |    14 | Header, conflict banner, GlueSyncPanel mount, table, empty |

Plus a shared `test-setup.tsx` module with icon/utils/Button mocks +
factory helpers (`makeAsset`, `makeEvent`, `makeDerived`,
`makeContext`) so each test file stays focused on assertions rather
than scaffolding.

#### Why this matters more than the test count

The principle being repaid is "follow your own rules". A howto
document that the author doesn't follow when writing the original
code is dead-on-arrival. Future contributors who see the howto but
notice the original tabs shipped without tests would (correctly)
infer that the rule is optional. Adding the tests in the same
release as the howto preserves the rule's force.

### Files

**New**

- `ui/src/components/asset-tabs/` directory:
  - `types.ts` — TabContext, AssetDerived
  - `index.ts` — barrel
  - `TabOverview.tsx`, `TabSchema.tsx`, `TabPartitions.tsx`,
    `TabEvents.tsx`, `TabChecks.tsx`, `TabLineage.tsx`
  - `GlueSyncPanel.tsx`, `SchemaCopyButtons.tsx`, `glueHelpers.tsx`
  - `test-setup.tsx` — shared mocks + factory helpers
  - 8 sibling `*.test.tsx` files (63 tests total)
- `tools/regen_ddl_parity.py` — committed regen script
- `docs/development/ADDING_ASSET_TABS.md` — procedural howto

**Changed**

- `ui/src/components/AssetDetailPage.tsx` — full rewrite as
  orchestrator. 1124 → 376 lines. Public API (props) unchanged.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #48 added.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.8`.

### Verification

- `pytest tests/`: 680 passed, 62 skipped (no SDK changes).
- `pytest sam/lambdas/console_api/tests/`: 128 passed (no backend changes).
- `vitest run`: **680 passed**, 48 files (was 617 / 40; +63 tests, +8 files).
- `tsc --noEmit`: clean.
- `python3 tools/regen_ddl_parity.py` runs cleanly, generates
  byte-identical fixture to the committed one.

No public API changes. No backend changes. No behaviour changes.
The 46 existing `AssetDetailPage` integration tests pass against
the refactored orchestrator without modification — they test
through the public component interface, which is unchanged. Safe
to deploy as UI-only update; backend deploy not required.

## v75.7 (0.75.7) - 2026-05-08

### CLAUDE.md compliance — closing v0.75.x technical debt

A retrospective audit of the v0.75.0 → v0.75.6 release cycle against
the project's 12 Core Principles (CLAUDE.md) surfaced two real
omissions and one debt item carried since v0.75.3. This release
closes all three. No behaviour changes.

#### ADR #47 — Asset Lineage `last_updated` Enrichment

v0.75.5 introduced `_enrich_assets_with_last_updated` in the lineage
endpoint, splitting concerns between `/recent-events` (date-scoped,
for the date picker) and `/lineage` (last-known per asset, for the
catalog Status column). This was an architectural decision — two
endpoints with two distinct scopes, neither duplicating the other —
but only documented in CHANGELOG, not in DESIGN_DECISIONS.md.

CLAUDE.md #6 requires an ADR for any change affecting the API
contract. The CHANGELOG entry described *what* changed; ADR #47 now
documents *why* the split exists, why pre-computation in
`pipeline_registry` was rejected, why parallel point-lookups beat a
new GSI, and which optimisations are deferred (caching, multi-region).
Future authors who need to evolve the lineage response now have the
rationale.

#### `TaskNode` exported as named component → unit tests reinstated

In v0.75.3, three tests for the `trigger_rule` badge in
`DAGGraphFlow.test.tsx` were deleted with a comment that the file's
ReactFlow mock made them untestable. CLAUDE.md #11 explicitly
forbids "skipping or weakening assertions in failing tests instead
of fixing the underlying issue" — deleting the tests was the wrong
call. The right fix was to make TaskNode independently renderable.

This release:
- `DAGGraphFlow.tsx` — `TaskNode` is now a named export rather than
  a module-private const. No behaviour change; just visibility.
- New file `DAGTaskNode.test.tsx` — 9 unit tests rendering TaskNode
  directly. Covers what the parent test file's mock can't reach:
  - trigger_rule badge: renders for `all_done`, `one_failed`;
    silent for default `all_success`; silent when undefined; has
    correct `title` attribute for hover discoverability
  - notification_failed warning icon: renders/hides correctly
  - status icon and label render
- `DAGGraphFlow.test.tsx` — obsolete "untestable" comment replaced
  with a pointer to the new unit-test file. The parent file
  continues to test wiring (edges, panel layout, callbacks); node
  internals now live next to TaskNode itself.

The pattern matches existing project conventions — `BaseModal`,
`StalenessIcon`, `useUrlSync` are all named exports with sibling
test files.

#### Why this release exists at all

Each individual borderline call in v0.75.3-v0.75.6 was small.
Together they amounted to drifting away from CLAUDE.md compliance
through a pattern of "fix the bug, defer the principle, document
the deferral in CHANGELOG". That pattern reaches a point where
the principles stop being load-bearing — that's the real cost,
not any single skipped ADR.

Treating this audit as a separate release (rather than rolling it
into the next feature work) keeps the principle-debt and feature-
debt clearly separated in the git history. If a future cycle
introduces similar drift, this release establishes the precedent
of paying it back explicitly rather than letting it compound.

#### Files

**New**

- `ui/src/components/DAGTaskNode.test.tsx` — 9 unit tests for the
  TaskNode component (trigger_rule badge × 5, notification warning
  × 2, status icon, label).

**Changed**

- `docs/reference/DESIGN_DECISIONS.md` — ADR #47 added.
- `ui/src/components/DAGGraphFlow.tsx` — `TaskNode` becomes a named
  export. No runtime change; `nodeTypes` still references it the
  same way internally.
- `ui/src/components/DAGGraphFlow.test.tsx` — obsolete "untestable"
  comment replaced with cross-reference to `DAGTaskNode.test.tsx`.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.7`.

#### Verification

- `pytest tests/`: 680 passed, 62 skipped (no SDK changes).
- `pytest sam/lambdas/console_api/tests/`: 128 passed (no backend changes).
- `vitest run`: 617 passed, 40 files (was 608 / 39; +9 from new file).
- `tsc --noEmit`: clean.

No public API changes. No backend changes. No behaviour changes.
Pure principle-debt repayment + ADR documentation. Safe to deploy
as a UI-only update; backend deploy not required.

## v75.6 (0.75.6) - 2026-05-08

### Status banner / Latest Execution — date-aware time labels

A user-driven test surfaced an ambiguity carried over from before
v0.75.0: the Asset Detail Overview tab rendered event timestamps as
bare `HH:MM:SS` ("21:29:43"), which is meaningless when the event
was actually yesterday or earlier — the operator can't tell at a
glance whether the asset materialized recently or a week ago.

Two spots affected, both upgraded to a new date-aware helper:

- Status banner: `Materialized — Updated 21:29:43`
  → `Materialized — Updated Yesterday at 21:29:43`
- Latest Execution card: `21:29:43`
  → `Yesterday at 21:29:43`

#### New helper `formatDateTime(iso)`

Lives next to `formatTime` in `ui/src/utils/formatters.ts`. Output
adapts to recency:

| Event when           | Output                          |
|----------------------|---------------------------------|
| Same calendar day    | `Today at 21:29:43`             |
| Previous day         | `Yesterday at 21:29:43`         |
| This year, earlier   | `May 7 at 21:29:43`             |
| Different year       | `May 7, 2025 at 21:29:43`       |

Why a new helper rather than upgrading `formatTime`: many other UI
spots (DAG node duration, Gantt time markers, event list time-of-day
column where date is shown separately) want the bare time and would
become noisy with a date prefix. The two helpers cover distinct
contexts; calls migrate site-by-site.

#### Files

**Changed**

- `ui/src/utils/formatters.ts` — new `formatDateTime` export.
- `ui/src/components/AssetDetailPage.tsx` —
  - Banner `formatTime(lastEventTime)` → `formatDateTime(...)`.
  - Latest Execution card `formatTime(assetEvents[0].event_time)` →
    `formatDateTime(...)`.
  - `formatDateTime` added to existing utils import.
- `ui/src/components/AssetDetailPage.test.tsx` —
  - Mock `vi.mock('../utils', ...)` extended with `formatDateTime`.
  - "Materialized + last update" assertion tightened to require the
    date prefix (`Today|Yesterday|<MonthShort> <day>`), preventing
    a future regression to time-only labels.

**New tests**

- `ui/src/utils/formatters.test.ts` — 9 cases:
  null/undefined/empty/invalid handling, today, yesterday, earlier
  this year, different year, mid-week disambiguation.

#### Verification

- `pytest tests/`: 680 passed (no SDK changes).
- `pytest sam/lambdas/console_api/tests/`: 128 passed (no backend changes).
- `vitest run`: 608 passed, 39 files (was 599 / 38; +9 new formatters).
- `tsc --noEmit`: clean.

UI-only release. No backend deploy needed — only S3 sync + CloudFront
invalidation.

## v75.5 (0.75.5) - 2026-05-08

### Catalog Status column — show last materialization regardless of date picker

A user-driven test surfaced a regression introduced in v0.75.3:
all 23 catalog rows showed `"Never"` even though events for those
assets clearly existed (visible on each Asset Detail page's Events
tab, going back ~2 weeks). Root cause was a combination of two
behaviours:

1. The `/recent-events` endpoint scopes its DDB GSI query to the
   header date picker's selected day. After a fresh deploy the picker
   defaults to today, but a same-day deploy + backfill produces events
   on **historical** `execution_date` values (yesterday and earlier),
   so today's window returns zero events for every asset.
2. v0.75.3's `stalenessText` helper substituted the calculator's
   honest `"No data"` (= "no events for this scope") with `"Never"`
   (= "ever, in history"). The stronger phrasing was wrong because
   events do exist outside the scope.

Both changes were defensible in isolation; together they made the
catalog list lie about asset state.

#### Backend — assets carry their real `last_updated`

`get_asset_lineage` now enriches each asset's response payload with
`last_updated`: the ISO timestamp of the most recent event, looked up
directly against the `asset-events` table by primary key
(`asset_name` HASH + `event_time` RANGE, descending, LIMIT 1).
Lookups are parallelised across a 10-worker thread pool — for a
typical 23-asset catalog the page-load cost is bounded by RTT
(~50-100ms total), not serial latency. Failed lookups for individual
assets degrade to `last_updated: ""` and log a warning; one asset's
DDB throttle does not 500 the whole page.

The new field is in addition to the existing `/recent-events`
endpoint, which keeps its date-scoped behaviour for the date picker
filter feature. Two endpoints, two roles:

  - `/recent-events?date=...` — what happened on the picker's day
    (used for "events on May 7" filter)
  - `/lineage` (with `last_updated`) — last known state per asset,
    independent of any picker (used for catalog Status column)

This split matches what the UI already wanted but couldn't get
without backend support.

#### Frontend — staleness calculator gains `fallbackLastUpdated`

`getAssetStaleness(assetName, recentEvents, options)` now accepts
`options.fallbackLastUpdated` and resolves in three paths:

  1. Match in scoped `recentEvents` → use that event_time
  2. Else fallback timestamp (asset.last_updated) → use that
  3. Else → unknown / "No data"

`AssetsView.tsx` passes `assets[name]?.last_updated` as the fallback,
so a row's status reflects the asset's real last materialization
even when the picker is on a day the asset didn't run.

#### Frontend — `stalenessText` helper removed (revert v0.75.3)

The helper was the wrong fix for the wrong problem. With path 2
delivering real timestamps from the backend, no string substitution
is needed — the calculator's natural label (`"5h ago"`, `"3d ago"`,
or `"No data"` only when truly nothing exists) is correct.

`AssetsView.tsx` reverts to `staleness.label || '—'` for cell
rendering. The shared helper module (`utils/staleness.ts`) drops
the `stalenessText` export.

#### Asset Detail banner — `last_updated` fallback wired through

Detail page `assetEvents` is queried by asset_name (not date-scoped),
so paths 1/2 in the banner logic were already reliable. The fix
plumbs `asset.last_updated` as a third tier so the banner can show
"Materialized — Updated N ago" on assets where this UI session
hasn't loaded the event list yet (rare, but keeps the banner
consistent with the catalog list).

The "Never materialized" copy now requires **both** no events on
this page AND no `last_updated` from the backend — the genuinely
empty case.

#### Files

**Changed**

- `sam/lambdas/console_api/routes/assets.py` —
  - New private helper `_enrich_assets_with_last_updated(assets)` —
    parallelised per-asset point-lookup against `asset_events_repo`.
  - `get_asset_lineage` calls the helper after `_build_assets_from_pipelines`.
- `ui/src/utils/staleness.ts` —
  - `getAssetStaleness` signature extended with
    `options.fallbackLastUpdated`. Three-path resolution documented.
  - `stalenessText` export removed (was a v0.75.3 wrong-fix).
- `ui/src/components/AssetsView.tsx` —
  - Local `getAssetStaleness` wrapper passes `fallbackLastUpdated`.
  - Two cell renders revert to `{staleness.label || '—'}`.
  - `stalenessText` import dropped.
- `ui/src/components/AssetDetailPage.tsx` —
  - Banner reads `asset.last_updated` as fallback when `assetEvents`
    is empty. "Never materialized" requires neither source.

**New tests**

- `sam/lambdas/console_api/tests/routes/test_lineage_last_updated.py`
  — 4 cases: enrichment populates `last_updated`, uses cheap
  query pattern, degrades on partial failure, no-op on empty list.
- `ui/src/utils/staleness.test.ts` — replaced (8 cases now): three
  resolution paths × happy/empty/null variants.

**Verification**

- `pytest tests/`: 680 passed, 62 skipped (no SDK changes).
- `pytest sam/lambdas/console_api/tests/`: 128 passed (was 124, +4 new).
- `vitest run`: 599 passed, 38 files (was 597; +2 net — replaced
  6 stalenessText tests with 8 fallback-path tests).
- `tsc --noEmit`: clean.

No public API changes — the new `last_updated` field is additive on
the lineage response. Old UI versions that don't read it still work.

## v75.4 (0.75.4) - 2026-05-08

### DDL renderer — Phase-1 scaffolding for future dialect plug-ins (ADR #46)

The "Copy as DDL" feature shipped in v0.75.0 with the Python renderer
inside `Asset.to_ddl()` and a TypeScript mirror inline in
`AssetDetailPage.tsx`. This release does not change behavior — it
restructures the code so when a second dialect lands (BigQuery,
Iceberg, Postgres, Snowflake), the refactor into a plug-in pattern is
a 30-minute job rather than a 4-hour rewrite that touches public API.

The duplication between Python and TypeScript is intentional and
documented (see ADR #46) — UI ships independently of the SDK and
cannot import Python at runtime. Alternatives (per-click backend
endpoint, pre-rendered DDL in `/api/assets`, Pyodide in browser) all
have higher cost than the duplication itself. Drift between the two
is enforced down to zero by parity tests on both sides reading a
shared fixture file.

#### `Asset.to_ddl()` is now a thin dispatcher

`slsflow/assets.py:Asset.to_ddl()` validates dialect + schema, then
delegates to a module-private `_render_glue_ddl(asset)` helper at the
end of the same file. Public API unchanged; behavior unchanged. The
helper is kept at module scope (rather than as a method on Asset or
in a separate module) so when Phase 2 fires, extracting it to
`slsflow/renderers/glue.py` is one `git mv` plus an import update.

#### TS mirror extracted to `ui/src/utils/ddl-glue.ts`

The 30-line `renderDDL()` that previously lived inline in
`AssetDetailPage.tsx` is now an exported `renderGlueDDL(input)`
function in its own utility module. Takes a single options object
(`RenderGlueDDLInput`) so call sites are self-documenting and so the
shape extends naturally when more dialects ship (one option per
dialect, dispatched by a string).

#### Shared fixture file `tests/fixtures/ddl_parity.json`

Six canonical input/expected pairs covering every renderer branch:

| Fixture            | What it locks down                                                  |
|--------------------|--------------------------------------------------------------------|
| `simple`           | Minimal `CREATE EXTERNAL TABLE` — no partition, no description, no URI |
| `with_partition`   | Partition column extracted into `PARTITIONED BY`                    |
| `with_description` | Asset and column COMMENTs; single quotes doubled (Hive escape rule) |
| `with_uri`         | `s3://` URI emitted as `LOCATION`                                   |
| `bare_name`        | No `glue_table` set — asset name in backticks                       |
| `all_features`     | Combined: partition + description + URI                             |

Both renderers must produce byte-identical output to each fixture's
`expected` string. The fixture format is forward-compatible: when a
second dialect ships, `expected` becomes `expected_glue` and a
sibling `expected_bigquery` joins it; both parity tests parametrize
on dialect.

#### Parity tests on both sides

- `tests/sdk/test_ddl_parity.py` — pytest, 9 cases (6 fixtures + 3
  dispatcher tests for unsupported dialect, empty schema, dispatcher
  delegation).
- `ui/src/utils/ddl-glue-parity.test.ts` — vitest, 8 cases (1 sanity
  load + 6 fixture cases + 1 error case mirroring the Python
  ValueError).

Both load the same JSON file. If the Python renderer changes without
updating the fixture, pytest fails. If TypeScript changes, vitest
fails. The fixture file is the contract; both renderers must conform.

How to update the fixture intentionally: edit one renderer, run the
SDK to regenerate the file (helper script not yet committed; the
v0.75.4 fixture was generated by the SDK in a one-shot Python
snippet — see CHANGELOG generation script note in
`tests/fixtures/ddl_parity.json` if present, otherwise just call
`asset.to_ddl()` for each fixture and dump JSON), then run both
parity tests until both pass.

#### ADR #46 — full phased plan

The design decision document captures the three-phase roadmap:

- **Phase 1 (current):** mirror code + parity tests + extracted
  helpers. We are here.
- **Phase 2 (trigger: second dialect lands):** move helpers to
  `slsflow/renderers/`, design `Renderer` Protocol *after* seeing
  the second dialect's requirements, split UI strategy (mirror
  common formats, route uncommon ones through a new backend
  endpoint).
- **Phase 3 (trigger: custom-dialect user request):** publish the
  `Renderer` Protocol as a public extension point, discover via
  Python `entry_points` (matches the `dbt-<warehouse>` plug-in
  pattern).

Includes the YAGNI rationale: designing the `Renderer` Protocol from
a single Glue implementation almost always produces an interface that
doesn't fit the second dialect (BigQuery has column-level
`partitioning_field`, Iceberg uses transforms, Snowflake has
`CLUSTER BY` post-hooks, Postgres has no external tables). dbt
themselves waited until ~5 working warehouse adapters before
stabilizing their Adapter Protocol.

#### Files

**New**

- `tests/fixtures/ddl_parity.json` — shared 6-fixture parity contract.
- `tests/sdk/test_ddl_parity.py` — pytest, 9 cases.
- `ui/src/utils/ddl-glue.ts` — `renderGlueDDL(input)` exported function.
- `ui/src/utils/ddl-glue-parity.test.ts` — vitest, 8 cases.

**Changed**

- `slsflow/assets.py` —
  - `Asset.to_ddl()` is a thin dispatcher: validation + delegation to
    `_render_glue_ddl(self)`.
  - New `_render_glue_ddl(asset)` module-private helper at end of file
    with full docstring referencing ADR #46 and the parity test paths.
- `ui/src/components/AssetDetailPage.tsx` —
  - Imports `renderGlueDDL` from `../utils/ddl-glue`.
  - Removes the inline 32-line `renderDDL()` function.
  - Copy button call site uses `renderGlueDDL({ assetName, glueTable, ... })`.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #46 added.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.4`.

#### Verification

- `pytest tests/`: 680 passed, 62 skipped (was 671 + 9 new parity tests).
- `pytest sam/lambdas/console_api/tests/`: 124 passed (no backend changes).
- `vitest run`: 597 passed, 38 files (was 589 / 37; +8 parity, +1 file).
- `tsc --noEmit`: clean.

No public API changes. No backend changes. No DDB schema changes.
Behavior is byte-identical to v0.75.3 — verified by parity tests
running against fixtures that were generated from the v0.75.3 renderer
output. Safe to deploy without coordinating SDK upgrades.

## v75.3 (0.75.3) - 2026-05-08

### Asset Detail / Catalog UX polish — 5 fixes from screenshot review

A walkthrough of the Asset Detail page surfaced five UX issues. All are
frontend-only — no backend or API changes. Two were copy bugs (opaque
"No data" labels), two were affordance bugs (clickable-looking thing
not clickable, unhelpful column), one was a discoverability gap
(non-default `trigger_rule` invisible on the DAG canvas).

#### Fix A — "Latest Execution" card is now actually clickable

The card on Asset Detail's Overview tab looked like a link (rounded
border, separate region) but had no `onClick`. Now it's a `<button>`
that navigates to the producing pipeline's DAG view, which auto-
highlights the most recent run. Operators get one-click access from
"asset I'm investigating" to "the run that produced it".

The asset events table doesn't store SFN `execution_name`, so we route
to the pipeline overview rather than a specific execution. In practice
the latest run is what the operator wants 99% of the time — and the
pipeline view's existing UI surfaces older runs from there.

```tsx
<button
    type="button"
    className="adp-latest-exec adp-latest-exec--clickable"
    onClick={() => {
        window.location.href = `?pipeline=${encodeURIComponent(sourceDag)}`;
    }}
    title="Open the pipeline that produced this asset"
>
```

CSS `.adp-latest-exec--clickable` adds the cursor + hover affordances
that the prior card lacked (the visual style was already link-like,
just missing the interactivity).

#### Fix B — Status banner copy: three distinct cases instead of "Updated No data"

The Overview banner used to say `Unknown — Updated No data` when an
asset had never been materialized. Now it disambiguates three cases
with copy tailored to each:

| State                                      | Banner copy                                                |
|--------------------------------------------|------------------------------------------------------------|
| Never materialized (no events)             | `Never materialized — Pipeline has not produced this asset yet` |
| Materialized, no `freshness_hours`         | `Materialized — Updated 2h ago`                            |
| Materialized + `freshness_hours` set       | `Fresh / Warning / Stale — Updated 2h ago`                 |

The "Materialized" state is new — it acknowledges the asset has run at
least once without grading freshness (because the asset author didn't
declare a freshness policy, the system has no opinion to volunteer).

#### Fix C — Catalog list "Status" column: "Never" replaces "No data"

The asset list (both flat and folder-asset views) showed `No data` for
every never-materialized asset. With 23 such rows on a fresh deploy,
the column became visual noise. Replaced with `Never` — same width,
clearer meaning, and qualitatively distinct from "data is stale".

Refactored as a reusable helper in `utils/staleness.ts`:

```ts
export function stalenessText(s: StalenessResult): string {
    if (s.status === 'unknown' && (!s.label || s.label === 'No data')) {
        return 'Never';
    }
    return s.label || '—';
}
```

Materialized assets keep their relative-time label (`2h ago`, `5m ago`)
unchanged. The helper sits in a shared utility module so any future
table that renders staleness (lineage view, dependency list, etc.)
gets the same display logic without copy-paste.

#### Fix D — Folder *group* view: drop the Status column

The top-level folder list showed `Status: —` for every group row.
There is no meaningful per-group status to compute (a group of 23
assets can't be summarised by a single label without either over-
simplifying or duplicating per-asset info that's one click away).
Dropped the column entirely.

Per-asset views (folder asset list, flat list) keep their Status
column — that's where status is meaningful.

#### Fix E — `trigger_rule` badge on DAG nodes when non-default

Tasks with `trigger_rule="all_done"` (or `one_failed`, etc.) execute
even when upstream tasks fail or are skipped — that's the rule's
purpose, but it surprises operators looking at a green
`mark_daily_complete` next to a red upstream task. The DAG canvas
never surfaced the rule.

Now: when a task's `trigger_rule` is non-default, a small yellow
badge with the rule name renders next to the task label. The node's
`title` attribute also includes the rule for hover discoverability.
Default `all_success` tasks render unchanged — no visual noise for
the common case.

```css
.dag-node-trigger-rule {
    font-size: 0.625rem;
    font-family: var(--font-mono, monospace);
    background: rgba(234, 179, 8, 0.18);
    color: rgb(180, 130, 0);
    border: 1px solid rgba(234, 179, 8, 0.35);
    padding: 1px 5px;
    border-radius: 3px;
}
```

#### Files

**Changed**

- `ui/src/components/AssetDetailPage.tsx` —
  - Latest Execution card → `<button>` with `onClick` navigate
    (`?pipeline=<sourceDag>`).
  - Status banner: new `hasMaterialization` + `hasFreshnessPolicy`
    derived flags, three-branch copy logic.
- `ui/src/components/AssetsView.tsx` —
  - Folder group view: removed `<th>Status</th>` and corresponding `<td>`.
  - Folder asset view + flat list: status cell uses new `stalenessText`
    helper instead of raw `staleness.label`.
- `ui/src/components/DAGGraphFlow.tsx` —
  - `TaskNode` reads `data.task?.trigger_rule`; renders badge + tooltip
    when non-default.
- `ui/src/utils/staleness.ts` —
  - New exported `stalenessText(s: StalenessResult): string`.
- `ui/src/styles/modules/_assets.css` —
  - `.adp-latest-exec--clickable` rules (hover, focus, cursor).
- `ui/src/styles/modules/_dag.css` —
  - `.dag-node-trigger-rule` rules.

**Tests**

- `ui/src/components/AssetDetailPage.test.tsx` — 5 new cases:
  - Banner: never-materialized / materialized-no-policy / freshness-known.
  - Latest Execution: button shape, navigation target.
- `ui/src/components/AssetsView.test.tsx` — 3 new cases:
  - Group view has no Status header; asset views keep it.
- `ui/src/utils/staleness.test.ts` — new file, 6 cases for `stalenessText`.

(Tests for the `trigger_rule` badge intentionally omitted from
`DAGGraphFlow.test.tsx` — the file's ReactFlow mock renders nodes as
plain divs that bypass `nodeTypes`, so TaskNode internals don't execute
under that test setup. Documented in a code comment in that file.)

#### Verification

- `pytest tests/`: 671 passed, 62 skipped (no Python changes).
- `pytest sam/lambdas/console_api/tests/`: 124 passed (no backend changes).
- `vitest run`: 589 passed, 37 files (was 575 / 36; +14 frontend).
- `tsc --noEmit`: clean.

No backend changes, no API changes, no CHANGELOG-noted IAM/ops impact.
Pure frontend polish — safe to deploy without coordinating SDK upgrades.

## v75.2 (0.75.2) - 2026-05-07

### Glue Catalog terminology + IAM/LF docs aligned with actual AWS

A user-driven review surfaced terminology drift between SLSFlow's
documentation and AWS's actual three-level Glue Data Catalog model
(Account → Database → Table) plus Athena's four-level UI hierarchy
(Data source → Catalog → Database → Table). This release tightens
language, expands the IAM and Lake Formation guidance, and replaces
demonstrably wrong phrasing introduced earlier.

#### Bug — `Asset.__init__` error message named "default catalog"

The validation error for malformed `glue_table` told users to "set the
database (e.g. 'default.example' for the default catalog)". `default`
is a Glue **database**, not a catalog. Replaced with a precise message
that names the three Glue concepts (catalog, database, table) correctly
and points at `glue_catalog` / `glue_region` for cross-targeting:

```
glue_table must be 'database.table', got 'broken'.
The format references a Glue database (e.g. 'default') and a table
within it (e.g. 'example'). The Glue Data Catalog itself is implicit —
by default the AWS account of the Console API Lambda. Set
`glue_catalog=<account-id>` to target another account's catalog, and
`glue_region=<region>` for cross-region.
```

#### Bug — `humanizeGlueError` for `EntityNotFoundException` did not name wrong-region

The hint said "The asset has no row materialized yet, the table was
renamed, or `glue_table` points to a path that does not exist."
**Wrong-region is a third distinct cause** for `EntityNotFoundException`
— a table in `eu-west-1` is invisible to a Lambda querying `us-east-1`
even when CatalogId is correct. Glue Data Catalogs are per-region,
without automatic cross-region replication. Replaced with:

```
Either the table does not exist in the targeted Glue Data Catalog,
or `glue_region` / `glue_catalog` point at the wrong catalog. Glue
Data Catalogs are per-AWS-account and per-region — a table in
`eu-west-1` is invisible to a Lambda querying `us-east-1` even when
the Catalog ID is correct.
```

The hint test was updated accordingly (`/per-region|wrong catalog/`).

#### Acme example — point at the user's real Athena table

`pipelines/acme/daily/dag.py` previously declared
`glue_table="default.example"`. The `default` database exists in every
Glue catalog by default but won't typically have an `example` table.
Switched to `glue_table="test.example"` to match the database visible
in the user's Athena query editor (`test.example`), so drift detection
becomes immediately demonstrable. The accompanying comment was
rewritten to lay out the three-level Glue addressing model and the
expected drift output for the screenshot's
`(id INT, name STRING, price DOUBLE)` fixture.

#### `Asset.__init__` docstring — full AWS-aligned glue_*/Athena mapping

Replaced the terse `glue_table`/`glue_catalog`/`glue_region` field
descriptions with a precise mapping to AWS Glue API parameters
(`DatabaseName`, `Name`, `CatalogId`, `region_name`) and a callout
that Athena's four-level UI hierarchy is Athena-side, not Glue, so
SLSFlow targets Glue directly and federated catalogs are out of scope.

#### `docs/features/ASSETS.md` — full mapping table + IAM checklist

The Glue Catalog Reference section now opens with a mapping table
(AWS Glue concept → SDK field → default) and a worked ARN, then
covers the same-account / cross-account / cross-region cases each as
a single example. A new "Note on Amazon Athena's data sources"
sub-section calls out what is **not** covered: Athena Federated
Catalogs and Athena DataSource aliases.

The cross-account section was rewritten as an IAM checklist with a
concrete `template.yaml` snippet for resource ARN expansion. A new
**Lake Formation interaction** sub-section explains why IAM alone
isn't sufficient when the catalog is managed by LF, with the
`IsRegisteredWithLakeFormation` self-check command and the
expected `AccessDeniedException` symptom.

#### ADR #45 — Athena/LF out-of-scope explicitly named

ADR #45 grew two new sections:
- **"Out of scope (by design — won't add)"** — Athena Federated
  Catalogs and Athena DataSource aliases, with rationale (Athena-side
  abstractions; underlying catalog is addressable directly).
- **"Lake Formation interaction (operator concern, not an API change)"**
  — clarifies that LF gates IAM-correct calls separately, and that
  the existing friendly Glue error mapping already surfaces the symptom.

#### Files

**Changed**

- `slsflow/assets.py` — error message corrected; docstring rewritten
  with full Glue-API and Athena mapping.
- `pipelines/acme/daily/dag.py` — `glue_table` → `test.example`;
  comment rewritten with three-level addressing model.
- `ui/src/components/AssetDetailPage.tsx` — `humanizeGlueError`
  for `EntityNotFoundException` now names wrong-region as a
  distinct cause.
- `ui/src/components/AssetDetailPage.test.tsx` — error-hint regex
  updated to match the new wording.
- `docs/features/ASSETS.md` — Glue Catalog Reference section
  rewritten with mapping table, ARN, IAM checklist, Lake Formation
  guidance, Athena callout.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #45 expanded with
  Athena and Lake Formation sub-sections.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.2`.

#### Verification

- `pytest tests/`: 671 passed, 62 skipped.
- `pytest sam/lambdas/console_api/tests/`: 124 passed.
- `vitest run`: 575 passed, 36 files (the 1 case touching the
  `EntityNotFoundException` hint was updated; the rest were
  unaffected).
- `tsc --noEmit`: clean.

No code logic changed — this release is documentation, error message
text, and one example fixture.

## v75.1 (0.75.1) - 2026-05-04

### Cross-account / cross-region Glue Catalog support (ADR #45)

Closes three silent gaps in the Glue Catalog reference path that surfaced
in user testing of v0.75.0:

1. **Cross-region drift detection mis-targeted region.** Backend always
   used the Lambda's default region. An asset declared with `glue_table`
   pointing at a Glue Catalog in `eu-west-1` (Lambda in `us-east-1`)
   returned `EntityNotFoundException` — the table existed, but the
   request hit the wrong region.
2. **`from_glue_table(region=...)` did not persist the value.** Authoring
   worked (the deploy-time fetch used the right region); runtime drift
   detection silently mis-targeted because no `glue_region` was stored
   on the Asset.
3. **Cross-account asset name collision.** Two pipelines pulling
   `default.example` from different AWS accounts collapsed into one
   asset entry — `from_glue_table("default.example", catalog_id="222")`
   produced the same default name as the local-account version.

#### `Asset.glue_region: str = ""` field

New constructor field. Empty string preserves current same-region
behaviour; non-empty string pins the runtime drift-detection boto3
client to that region.

```python
orders = Asset(
    name="retail/orders",
    glue_table="default.example",
    glue_catalog="222222222222",   # cross-account: AWS account ID
    glue_region="eu-west-1",       # cross-region: target region
    schema=[...],
)
```

`glue_catalog` and `glue_region` are independent: set neither, either,
or both.

#### `glue_table` validated at construction

The constructor now rejects malformed `glue_table` values (must contain
exactly one `.` with both sides non-empty). Catches the bug in the
developer's editor instead of as a 422 from the Console API after
deploy.

```python
Asset(name="x", glue_table="missing_dot")
# ValueError: glue_table must be 'database.table', got 'missing_dot'.
# Set the database (e.g. 'default.example' for the default catalog).
```

#### `from_glue_table` smart default name

When `catalog_id` is non-empty, the default asset name now prepends
the account ID:

```python
# Local account → simple name
a = Asset.from_glue_table("default.example")
# a.name == "default.example"

# Cross-account → catalog-qualified name (collision-free)
a = Asset.from_glue_table("default.example", catalog_id="222222222222")
# a.name == "222222222222.default.example"
```

`region=` kwarg now persists into `glue_region` on the resulting Asset.

#### Backend — region-aware Glue client factory

New `config.get_glue_client(region: str)` helper with per-region cache.
Empty string returns the same default-region client the legacy `glue`
proxy uses (single source of truth, no duplication — CLAUDE.md #12).
The schema-fetch route now reads `glue_region` from the asset and pins
its boto3 client accordingly.

```python
# Inside routes/assets.py:
client = get_glue_client(glue_region)
kwargs = {'DatabaseName': database, 'Name': table}
if glue_catalog:
    kwargs['CatalogId'] = glue_catalog
response = client.get_table(**kwargs)
```

`glue_region` joins the existing pipeline_registry serialization, the
`_new_asset_entry` template, the last-writer-wins enrichment, and the
schema-fetch response payload. All paths surface it; UI renders it
when non-empty.

#### UI — scope subtitle in GlueSyncPanel header

GlueSyncPanel header gains a scope subtitle showing
`account 222222222222 · eu-west-1` when either field is non-empty.
Local-account, local-region assets — the common case — see no clutter.

The label changed from `catalog <id>` (legacy) to `account <id>` because
the AWS-side concept operators recognize is the account ID, not the
"Glue Catalog ID" (which is the same thing). One legacy test caught
this rename and was updated.

The sidebar gains explicit `Account: ...` / `Region: ...` rows so the
default Overview tab also surfaces scope without forcing a click into
Schema.

#### IAM caveat (out of scope)

Cross-account drift detection requires both:
- `glue:GetTable` on the target ARN in the Console API Lambda's role.
- A resource policy on the target catalog/table (or a Lake Formation
  share) granting access from the Lambda's account.

This release adds the *mechanism*; users configuring cross-account
references must arrange the *permissions* themselves. The friendly
Glue-error mapping (`AccessDeniedException` → "Permission denied for
Glue — the Console API Lambda needs `glue:GetTable` on this catalog")
already covers the most common misconfiguration.

#### Files

**New**

- `sam/lambdas/console_api/tests/test_config.py` — 5 tests covering the
  `get_glue_client` factory: default-region path, region-pinned path,
  per-region caching, distinct-region cache keys, and the default ↔
  specific-region cache separation.

**Changed**

- `slsflow/assets.py` —
  - `Asset.__init__` accepts `glue_region: str = ""`.
  - `glue_table` is structurally validated at construction time.
  - `Asset.to_dict()` serializes `glue_region`.
  - `Asset.from_glue_table()` persists `region` into `glue_region`,
    smart default name with `catalog_id` prefix.
- `slsflow/generators.py` — outlet serialization includes `glue_region`.
- `sam/lambdas/console_api/config.py` —
  - New `get_glue_client(region)` factory with per-region cache.
  - `Dict` typing import added.
- `sam/lambdas/console_api/routes/assets.py` —
  - `_new_asset_entry` includes `glue_region`.
  - `glue_region` in the last-writer-wins enrichment field list.
  - Schema-fetch route uses `get_glue_client(glue_region)` and surfaces
    `glue_region` in the response payload (success and error paths).
  - List endpoint returns `glue_region`.
- `sam/lambdas/console_api/tests/routes/test_assets_glue_schema.py` —
  - `patch_glue` fixture rewritten to patch `get_glue_client` while
    staying backward-compatible (forwarder class). 17 existing tests
    kept their assertion style without modification.
  - 6 new tests in `TestCrossAccountAndRegion` covering the default,
    cross-region, cross-account, and combined paths plus payload
    surfacing.
- `ui/src/types/index.ts` — `AssetData.glue_region: string`.
- `ui/src/hooks/queries/useAssetQueries.ts` — `AssetGlueSchema.glue_region`.
- `ui/src/components/AssetDetailPage.tsx` —
  - GlueSyncPanel scope subtitle (`account <id> · <region>`).
  - Sidebar Account/Region rows.
  - `glueRegion` destructured and threaded through.
- `ui/src/components/AssetDetailPage.test.tsx` — 5 new vitest cases for
  scope display (none-set, account-only, region-only, both, sidebar);
  one legacy test updated for the `catalog → account` label rename.
- `ui/src/styles/modules/_assets.css` — `.adp-glue-panel-scope` reuses
  the `.adp-glue-panel-catalog` styling block (CLAUDE.md #12: extend,
  don't fork).
- `tests/sdk/test_asset_helpers.py` — 17 new tests across
  `TestGlueTableValidation` (7), `TestGlueRegion` (4),
  `TestFromGlueTablePersistsRegion` (2), `TestFromGlueTableDefaultName` (4).
- `docs/features/ASSETS.md` — Glue Catalog Reference and Glue Catalog
  Sync sections updated for cross-region; new explanation of the
  cross-account default-name strategy.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #45 added.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.1`.

#### Verification

- `pytest tests/`: 671 passed, 62 skipped (was 654 / 62; +17 SDK tests).
- `pytest sam/lambdas/console_api/tests/`: 124 passed (was 113; +5 in
  `test_config`, +6 in `test_assets_glue_schema`).
- `vitest run`: 575 passed, 36 files (was 570 / 36; +5 cross-account/
  region UI cases).
- `tsc --noEmit`: clean.
- SDK smoke: 10 cross-account/region scenarios round-trip through
  Asset construction, `to_dict`, and `from_glue_table` correctly.

## v75.0 (0.75.0) - 2026-05-04

### Schema feature — UX/DX expansion across SDK, CLI, backend, and UI

Builds on v0.74.x foundations to make typed schemas useful beyond the Schema
tab. New SDK methods (`print_schema`, `to_ddl`, `to_jsonschema`, `from_iceberg`),
deploy-time conflict detection in `slsflow-validate`, cross-pipeline conflict
surfacing in the UI, schema summary on Overview, friendly Glue error messages,
and a Copy-as-X toolbar on the Schema tab.

#### `slsflow.normalize_schema` rejects duplicate column names

Catalog systems (Glue, Iceberg, BigQuery) all reject duplicate column names,
but until v0.74.1 a user could declare two columns with the same name and
the failure would only surface during the first `CREATE TABLE` call in
production. v0.75.0 catches it at deploy-time on the developer's machine:

```python
Asset(name='x', schema=[
    Column('id', t.bigint()),
    Column('id', t.string()),  # ← raises ValueError now
])
# ValueError: Duplicate column name in schema: 'id' appears at positions
# 0 and 1. Catalog systems (Glue, Iceberg, BigQuery) reject duplicate
# column names; rename one of the columns.
```

The check runs in `normalize_schema`, so it fires for every accepted input
form (Column instances, tuples, dicts).

#### REPL-friendly `Column.__repr__` and `Asset.print_schema()`

The dataclass-default `repr(Column(...))` lists every field including six
defaults — a 5-column schema becomes an unreadable wall of text. v0.75.0
gives `Column` a default-eliding repr and adds `Asset.print_schema()`:

```python
>>> orders.schema
[Column('order_id', bigint, nullable=False, primary_key=True),
 Column('amount', decimal(10,2), description='USD amount'),
 Column('event_date', date, partition_key=True)]

>>> orders.print_schema()
Asset 'retail/orders' — 3 columns:
  #  name        type           constraints   description
  -  ----------  -------------  ------------  -----------
  0  order_id    bigint         PK, NOT NULL  Primary key
  1  amount      decimal(10,2)                USD amount
  2  event_date  date           Partition
```

`print_schema` is column-aligned, emits singular/plural correctly, and
no-ops on empty schemas with a one-line message.

#### `Asset.to_ddl()` and `Asset.to_jsonschema()` exporters

Two new methods turn the typed schema into something the user can paste
into Athena or hand to a downstream consumer:

```python
>>> print(orders.to_ddl())
CREATE EXTERNAL TABLE analytics.orders (
  `order_id` bigint COMMENT 'Primary key',
  `amount` decimal(10,2) COMMENT 'USD amount'
)
PARTITIONED BY (
  `event_date` date
)
LOCATION 's3://lake/orders/'

>>> orders.to_jsonschema()  # Draft 2020-12
{'$schema': 'https://json-schema.org/draft/2020-12/schema',
 'title': 'retail/orders',
 'type': 'object',
 'properties': {
     'order_id': {'type': 'integer', 'description': 'Primary key'},
     'amount': {'type': ['number', 'null'], 'format': 'decimal(10,2)'},
     'event_date': {'type': ['string', 'null'], 'format': 'date'},
 },
 'required': ['order_id']}
```

`to_ddl` currently emits Glue/Hive DDL only (the project's primary catalog).
Other dialects (`bigquery`, `postgres`, `iceberg`) raise `ValueError` until
a real user need surfaces. Partition columns are routed into `PARTITIONED BY`
per Hive convention; descriptions become `COMMENT 'literal'` with single-quote
escaping. `to_jsonschema` covers all 21 SDK types, marks non-nullable columns
as `required`, and folds `Optional[T]` semantics into JSON Schema's
`type: ["x", "null"]` union.

The JSON-Schema converter lives module-level in `slsflow.schema` as
`_slsflow_type_to_jsonschema(t, nullable)` so backend tooling can reuse it
without importing from `assets`.

#### `Asset.from_iceberg(iceberg_table)` shortcut

ADR #44 listed Iceberg as a target of the pyarrow bridge but never made
the convenience constructor explicit. v0.75.0 adds it:

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog('default')
iceberg_table = catalog.load_table('analytics.orders')
orders = Asset.from_iceberg(iceberg_table, name='retail/orders')
```

`pyiceberg` is NOT a slsflow dependency — the user already has it (otherwise
they have no Iceberg table to pass). We duck-type access via `.schema()` and
`.as_arrow()`, raise a clear `AttributeError` if the object doesn't look
like a `pyiceberg.table.Table`. Default name falls back to the Iceberg
identifier (`"namespace.tablename"`), mirroring `from_glue_table`.

#### `slsflow-validate` — cross-pipeline schema consistency

`validate_all` now runs `validate_schema_consistency(all_dags)` and adds the
results to the warnings list. Two checks:

1. **Type mismatch on same-name column.** Asset `retail/orders` declared as
   `amount: decimal(10,2)` in `producer-pipeline` and `amount: string` in
   `consumer-pipeline` — produces:

   ```
   Asset 'retail/orders' has type conflict on column 'amount' across
   pipelines — 'consumer-pipeline': 'string', 'producer-pipeline': 'decimal(10,2)'
   ```

2. **Different column counts** (less serious — backend resolver picks the
   richer one — but documented for hygiene):

   ```
   Asset 'retail/orders' declared with different column counts —
   'producer': 4 columns, 'consumer': 6 columns. Backend will pick the
   richest schema; consider reconciling the declarations.
   ```

Warnings only — `validate_all` does not block deploy. The richer-wins backend
resolver still runs unchanged. Output is sorted by asset name for deterministic
reads, and per-asset by column name for stability across runs.

`DAGInfo` gains a new `outlet_schemas: Dict[str, List[Dict]]` field populated
by `extract_dag_info` when an outlet has a real `Asset` instance with typed
schema (string/AssetRef outlets carry no schema and stay invisible to this
check, as expected).

#### Backend — `schema_conflicts` field on the Asset response

`_build_assets_from_pipelines` now populates `assets[name]['schema_conflicts']`
with a list of `{pipeline, columns}` entries every time a divergent schema is
seen for an already-declared asset. Empty list when no conflict. Existing
conflict-resolution behaviour (richer-wins via `dict_schema_richness`,
CloudWatch warning, last-equal-richness keeps first) is unchanged — this is
purely surfacing the conflict to the UI without altering resolution.

The first declaration is the baseline; subsequent divergent declarations are
recorded. So 3 pipelines declaring 3 different schemas produces 2 entries
(p2's contribution and p3's contribution; p1 is the baseline).

#### UI — Schema-conflict banner on Schema tab

When `asset.schema_conflicts` is non-empty, a yellow banner above the schema
table displays:

> ⚠ **Schema declared differently in N pipelines.** Showing the richest
> declaration; below are the divergent ones:
>
>   - `consumer-pipeline` — 3 columns
>   - `analytics-archiver` — 5 columns

This means an operator who opens Asset Detail to investigate now has the
info they need without tailing CloudWatch Logs.

#### UI — Schema summary on Overview tab

The Overview tab now shows a clickable schema summary card under the
description, with column count, constraint breakdown (`3 PK, 1 partition,
2 NOT NULL`), Glue-table reference if set, and a conflict marker if
applicable. Clicking the card jumps to the Schema tab.

Without this, a user landing on Overview had no signal that schema was
declared at all — the Schema tab was the only surface. Now schema presence
is visible from the first tab.

#### UI — friendly Glue error messages

Raw Glue error codes (`EntityNotFoundException`, `AccessDeniedException`, …)
were rendered as-is — useful for AWS engineers, cryptic to typical
operators. v0.75.0 maps the seven most common codes to title + actionable
hint pairs:

| Code                          | Title                       | Hint                                                          |
|-------------------------------|-----------------------------|---------------------------------------------------------------|
| `EntityNotFoundException`     | Glue table not found        | The asset has no row materialized yet, the table was renamed, or `glue_table` points to a path that does not exist. |
| `AccessDeniedException`       | Permission denied for Glue  | The Console API Lambda needs `glue:GetTable` on this catalog. |
| `ValidationException`         | Glue rejected the request   | `glue_table` must be in `database.table` form.                |
| `OperationTimeoutException`   | Could not reach Glue        | AWS network is unreachable or Glue is throttling.             |
| `InvalidInputException`       | Glue input rejected         | The catalog ID or table name is malformed.                    |
| `GlueEncryptionException`     | Glue encryption error       | Add `kms:Decrypt` on the catalog's KMS key.                   |
| `InternalServiceException`    | Glue service issue          | AWS Glue itself reported an internal error.                   |
| (other)                       | `Glue error: <code>`        | Falls back to raw message.                                    |

The raw error code + message stay visible in a small monospace footer for
operators who want to copy-paste into AWS support tickets.

#### UI — Copy-as-JSON / DDL / Markdown toolbar on Schema tab

Three small buttons on the Schema tab header copy the declared schema in
three formats:

- **JSON** — pretty-printed `[{"name", "type", ...}, ...]`. Same shape as
  `column_to_dict` produces, suitable for piping through `jq` or pasting
  into a script.
- **DDL** — Glue/Hive `CREATE EXTERNAL TABLE`, mirroring `Asset.to_ddl()`
  output. Single-quote-safe COMMENT escaping. Pastes straight into Athena.
- **Markdown** — pipe-delimited table for READMEs and PRs:

  ```
  | Column      | Type            | Constraints       | Description     |
  |-------------|-----------------|-------------------|-----------------|
  | `order_id`  | `bigint`        | PK, NOT NULL      | Unique order ID |
  | `amount`    | `decimal(10,2)` |                   | USD amount      |
  ```

Click feedback uses a check icon for ~1.5s. Falls back to the legacy
`document.execCommand('copy')` path on browsers without `navigator.clipboard`.

#### Files

**New**

- `tests/sdk/test_asset_helpers.py` — 29 tests
  (`print_schema` — 6, `to_ddl` — 9, `to_jsonschema` — 6, `from_iceberg` — 6, …).
- `tests/sdk/test_validation_schema.py` — 10 tests for
  `validate_schema_consistency`.

**Changed**

- `slsflow/schema.py` —
  - `normalize_schema` rejects duplicates with position-tagged ValueError.
  - New `Column.__repr__` (default-eliding).
  - New `_slsflow_type_to_jsonschema(t, nullable)` for JSON Schema export.
- `slsflow/assets.py` —
  - New methods: `print_schema()`, `to_ddl()`, `to_jsonschema()`.
  - New classmethod: `from_iceberg(iceberg_table, name=None, **kwargs)`.
  - Imports the new module-level JSON-Schema helper from `schema`.
- `slsflow/validation.py` —
  - `DAGInfo` gains `outlet_schemas: Dict[str, List[Dict]]`.
  - `extract_dag_info` populates outlet schemas from real Asset instances.
  - New `validate_schema_consistency(all_dags)`; called from `validate_all`.
- `sam/lambdas/console_api/routes/assets.py` —
  - `_new_asset_entry` adds `schema_conflicts: []`.
  - `_build_assets_from_pipelines` populates `schema_conflicts` on every
    divergent schema seen for an already-declared asset.
- `sam/lambdas/console_api/tests/routes/test_assets_helpers.py` —
  3 new tests for the conflict-tracking field.
- `tests/sdk/test_schema.py` —
  - `TestDuplicateColumnNames` (6 tests).
  - `TestColumnRepr` (5 tests).
  - `TestJsonSchemaConversion` (11 tests).
- `ui/src/types/index.ts` — new `AssetSchemaConflict` type;
  `AssetData.schema_conflicts: AssetSchemaConflict[]`.
- `ui/src/components/AssetDetailPage.tsx` —
  - Schema-conflict banner on Schema tab.
  - Schema summary card on Overview tab (click → jump to Schema tab).
  - `humanizeGlueError` map and structured rendering.
  - `SchemaCopyButtons` component (JSON / DDL / Markdown), with
    `renderDDL` and `renderMarkdown` helpers.
  - `Code` icon import added to `utils/icons.tsx`.
- `ui/src/components/AssetDetailPage.test.tsx` —
  17 new vitest cases (conflict banner, Overview summary, Glue error
  humanization, Copy buttons).
- `ui/src/styles/modules/_assets.css` — styles for the conflict banner,
  schema summary card, copy buttons, and structured Glue error.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.75.0`.

#### Verification

- `pytest tests/`: 654 passed, 62 skipped (was 593 / 62; +61 sdk tests:
  29 asset-helpers, 10 validation-schema, 22 schema additions).
- `pytest sam/lambdas/console_api/tests/`: 113 passed (was 110;
  +3 conflict-tracking tests).
- `vitest run`: 570 passed, 36 files (was 553 / 36; +17 in
  `AssetDetailPage.test.tsx`).
- `tsc --noEmit`: clean.
- End-to-end smoke: `Asset.from_iceberg` round-trips Iceberg→pyarrow→Asset
  with a duck-typed Table; `Asset.print_schema()` aligns 6-column output;
  `Asset.to_ddl()` produces Athena-paste-ready DDL with PARTITIONED BY,
  COMMENT, LOCATION; cross-pipeline schema-consistency validator surfaces
  type conflicts at deploy-time on a 2-pipeline test fixture.

## v74.1 (0.74.1) - 2026-05-04

### Schema feature cleanup — `from_parquet`, `dict_schema_richness`, dead-code & docs

Polish pass on the v0.72–v0.74 schema-feature stack. No new behaviour for
existing users; closes follow-up items surfaced during code review of the
v0.74.0 merge candidate.

#### `Asset.from_parquet(path)` — convenience wrapper, finally implemented

ADR #44 listed `from_parquet` as a planned helper and its docstring/comment
references shipped in v0.74.0, but the method itself did not. v0.74.1
implements it as a thin wrapper over `from_pyarrow`:

```python
from slsflow import Asset

# Local file
orders = Asset.from_parquet("samples/orders.parquet", name="retail/orders")

# S3 URI — uses pyarrow's built-in S3 filesystem; standard AWS credential
# chain (env vars, ~/.aws/config, IAM role)
orders = Asset.from_parquet(
    "s3://bucket/orders/sample.parquet",
    name="retail/orders",
    glue_table="analytics.orders",
)

# No name=  → derived from the file basename without extension.
# Mirrors the ergonomics of `from_pydantic` (model class name) and
# `from_glue_table` (db.table). Convenient for prototypes; production
# code should pass an explicit `name="domain/asset"`.
orders = Asset.from_parquet("samples/orders.parquet")
# orders.name == 'orders'
```

Reads only the Parquet footer via `pq.read_schema(path)` — no row data is
fetched, so it is cheap even for multi-GB files. Same `[pyarrow]` extra
requirement as `from_pyarrow`. All `Asset(...)` keyword arguments accepted
alongside `path`; passing `schema=` raises `TypeError` for parity with the
sibling constructors.

#### `dict_schema_richness` — backend conflict resolution now matches SDK semantics

The console_api `_build_assets_from_pipelines` route previously broke
schema-conflict ties by column count (`len(new_schema) > len(existing_schema)`).
That contradicted `slsflow.schema.schema_richness`, which has scored
constraints (PK, partition, NOT NULL, UNIQUE, description) since v0.72.0
and is unit-tested in the SDK. Concrete miss: a producer pipeline with a
typed schema (`primary_key=True`, `nullable=False`) and a consumer pipeline
with the same column count but no constraints — the consumer's schema
would win because the count tied.

Fix is paired:

- **`slsflow/schema.py`** — new `dict_schema_richness(list_of_dicts)`
  function. Same scoring as `schema_richness` but operates on the
  serialized dict shape (saves a `column_from_dict` round-trip on every
  pipeline build). Tested for parity: round-tripping a Column list through
  `column_to_dict` produces identical scores under both functions.
- **`sam/lambdas/console_api/utils.py`** — wire-format twin of the SDK
  function, inlined because the Lambda does not ship with the SDK package.
  `_SCHEMA_COLUMN_DEFAULTS` mirrors `slsflow.schema._COLUMN_DEFAULTS`;
  divergence between the two would surface as a backend-vs-SDK disagreement
  on conflict winners. CLAUDE.md Principle #1 (single source of truth)
  applies — any future change to `_COLUMN_DEFAULTS` must update both.
- **`routes/assets.py`** — replaces `len(...)` comparison with
  `dict_schema_richness(new_schema) > dict_schema_richness(existing_schema)`
  inside `_build_assets_from_pipelines`. Conflict-warn behaviour and
  field-by-field log payload unchanged.

New behavioural test (`TestSchemaConflictDetection::test_more_constraints_wins_on_tied_column_count`):
two-pipeline setup with equal column counts but only the second pipeline
declares constraints — asserts the constraint-richer schema wins.

**Behavioural note — richness scoring is a linear sum, not lexicographic.**
Each column contributes 1; each non-default constraint on that column
contributes 1 more. This is the existing v0.72.0 SDK contract, propagated
unchanged to the backend. A consequence operators should know about: a
2-column schema with many constraints can outscore a 5-column schema with
none (e.g. 2 cols × 4 constraints each = 10 beats 5 plain cols = 5). In
practice the schemas declared for the same asset across pipelines are
typically either identical or one is a subset; the tied-with-richer-other-side
case is rare. If this trade-off ever bites in production, lift the function
to a lexicographic `(column_count, constraint_count)` comparison in a
follow-up — both `slsflow.schema` and `console_api.utils` would need to
move together (the parity test below catches drift).

#### SDK ↔ Lambda parity test for `dict_schema_richness`

`_COLUMN_DEFAULTS` and `dict_schema_richness` are duplicated by necessity
across `slsflow/schema.py` and `sam/lambdas/console_api/utils.py` (the
Lambda does not ship with the SDK package). The duplication is mitigated
by a new pytest module — `tests/integration/test_sdk_lambda_parity.py` —
which:

- Imports `_COLUMN_DEFAULTS` from the SDK and extracts
  `_SCHEMA_COLUMN_DEFAULTS` from the Lambda's `utils.py` source via regex
  (avoids importing the Lambda's DAL dependencies).
- Asserts the two default dicts are equal.
- Runs both `dict_schema_richness` implementations against a 15-case
  parametrized corpus (empty, plain, PK, redundant `nullable=True`, rich,
  numeric default, falsy default, explicit `None` default, garbage entries,
  full constraint set, mixed schema, …) and asserts identical scores.

If a future change adds a key to one defaults dict and forgets the other,
or if the scoring rule changes on one side only, this test fails the
build with a diff that names both files.

Verified: changing one defaults dict (e.g. adding a `'sneaky': False` key
to the Lambda copy) makes `test_column_defaults_match` fail with a clear
diff; restoring the field makes the test pass again. Drift detection works.

#### Dead-code removal — `from_glue_table` `glue_table=` kwarg guard

The custom `TypeError("Pass glue_table positionally only...")` branch in
`Asset.from_glue_table` was unreachable. Calling `from_glue_table('db.t',
glue_table='other.t')` raises Python's own
`TypeError: ... got multiple values for argument 'glue_table'` before the
guard runs, because `glue_table` is the first positional parameter.
Replaced with a one-line comment that documents why no guard is needed.

#### UI test coverage — `AssetDetailPage` Schema tab, `GlueSyncPanel`, query gating

The v0.73.0 release shipped a 219-line Glue panel with five distinct
render branches (loading / network-error / glue-error / in-sync / drift)
and the v0.72.0 schema rendering with four constraint badges (PK,
Partition, NOT NULL, UNIQUE) — both with no UI-side tests, an asymmetry
versus the 25+ component test files in the suite. v0.74.1 adds 19 vitest
cases:

- Schema tab: empty-state, column rendering, constraint-badge correctness,
  default-nullable handling (backend omit-on-default), declared-in-code
  badge, column-count tab badge.
- GlueSyncPanel visibility: gated on `glue_table`, catalog-id label.
- GlueSyncPanel body: loading row, in-sync banner with column count, all
  three drift sections, Glue API error card, network-error card, refresh
  button → `refetch()`.
- **Query gating** (4 tests): the component calls
  `useAssetGlueSchemaQuery(assetName, activeTab === 'schema' && Boolean(glueTable))`.
  The hook is mocked with `vi.fn(...)` so call args are captured, and the
  tests assert on the `enabled` flag for each gate combination — initial
  Overview-tab render (false), after switching to Schema with `glue_table`
  set (true), Schema tab without `glue_table` (false), and leaving Schema
  back to Overview (false). Without arg-capturing this gating logic was
  invisible to the test — a refactor that hardcoded `enabled=true` would
  silently fire Glue API calls on every Asset Detail page open.

Test layout follows the pattern used by `AssetDetailModal.test.tsx` and
`AssetTriggerModal.test.tsx`: inline icon mocks, configurable hook
returns, scoped `within(panel)` queries to avoid collisions with
identically-named text elsewhere on the page.

#### Documentation

- `docs/features/ASSETS.md` — new "Shortcut: from a Parquet file directly"
  subsection covering `from_parquet`. Adds a "Naming note" paragraph
  documenting the `from_pydantic` fallback to `model_cls.__name__` and
  recommending explicit `name="domain/asset"` for production use (the
  fallback is convenient for prototyping but produces CamelCase asset
  names with no group, which surprises users when assets show up
  ungrouped on the Assets page).
- `slsflow/adapters/pyarrow_.py` — module docstring updated; the
  `from_parquet` line is now accurate, not aspirational.
- `pyproject.toml` — `[pyarrow]` extra comment matches the actual
  shipped helpers.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #44 "deferred work" block
  split: SQL-DDL / Avro / Protobuf / JSON-Schema / Annotated-pydantic
  remain deferred; `from_parquet` moved to a new "Shipped after v0.74.0"
  block.

#### Files

**New**

- `ui/src/components/AssetDetailPage.test.tsx` — 19 vitest cases.
- `tests/integration/test_sdk_lambda_parity.py` — 16 tests
  (`_COLUMN_DEFAULTS` equality + 15 corpus parametrizations).

**Changed**

- `slsflow/assets.py` — `Asset.from_parquet` classmethod added (with
  basename-as-default name fallback); dead `glue_table` kwarg guard removed.
- `slsflow/schema.py` — `dict_schema_richness` added; export updated.
- `slsflow/adapters/pyarrow_.py` — docstring fix.
- `sam/lambdas/console_api/utils.py` — `dict_schema_richness` (Lambda
  twin) + `_SCHEMA_COLUMN_DEFAULTS` constant.
- `sam/lambdas/console_api/routes/assets.py` — uses
  `dict_schema_richness` in conflict resolution; imports from `utils`.
- `tests/sdk/test_adapters_pyarrow.py` — `TestAssetFromParquet`
  (6 tests: temp-file basics, kwargs, schema-conflict guard, name from
  basename, explicit name wins, missing-extra ImportError).
- `tests/sdk/test_schema.py` — `TestDictSchemaRichness` (5 tests).
- `sam/lambdas/console_api/tests/test_utils.py` — `TestDictSchemaRichness`
  (6 tests).
- `sam/lambdas/console_api/tests/routes/test_assets_helpers.py` —
  `test_more_constraints_wins_on_tied_column_count` exercises the new
  richness-aware tie-break.
- `docs/features/ASSETS.md`, `pyproject.toml`, `CHANGELOG.md`,
  `docs/reference/DESIGN_DECISIONS.md`.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json`,
  `ui/package-lock.json` → `0.74.1`.

#### Verification

- `pytest tests/`: 593 passed, 62 skipped (was 556 / 16; +6 from_parquet,
  +6 dict_schema_richness, +16 SDK↔Lambda parity, others unchanged).
- `pytest sam/lambdas/console_api/tests/`: 110 passed (was 103; +1 routes,
  +6 utils).
- `vitest run`: 553 passed, 36 files (was 534 passed, 35 files; +19 in
  the new AssetDetailPage suite).
- `tsc --noEmit`: clean.
- Drift-detection sanity for the parity test: verified that injecting a
  spurious key into `_SCHEMA_COLUMN_DEFAULTS` makes the parity test fail
  with a diff naming both files; reverting makes it pass again.
- End-to-end smoke test of `Asset.from_parquet`: writes a Parquet file
  with `int64`, `decimal128(10,2)`, `list<string>`, `timestamp(us, UTC)`
  columns; `Asset.from_parquet(path, name='retail/orders', owner='data-team')`
  produces the expected typed schema, `nullable=False` carried over from
  pyarrow, group auto-derived as `retail`.

## v74.0 (0.74.0) - 2026-05-03

### Schema Adapters — `Asset.from_pyarrow` / `from_pydantic` / `from_glue_table` (ADR #44)

Three new classmethod constructors on `Asset` that derive the column
schema from an existing source instead of requiring users to type each
column by hand. Closes the most-cited ergonomic gap with Dagster's
ecosystem integrations.

#### Why

Phase 1 (v0.72) gave users typed columns; Phase 2 (v0.73) gave them
on-demand drift detection against Glue. Both required users to write the
schema in `dag.py` first — which is busy work when the schema is already
defined in a Parquet sample, a pydantic model used elsewhere in the
service, or an existing Glue table that is already the source of truth.
The three new constructors close that gap; the bridge pattern via
pyarrow gives access to Iceberg, Parquet, BigQuery, Polars, Pandas, and
DuckDB through a single optional dependency.

#### New API

```python
from slsflow import Asset

# 1. From any pyarrow.Schema — Iceberg, Parquet, BigQuery, Polars, Pandas, DuckDB
import pyarrow.parquet as pq
sample = pq.read_metadata("s3://bucket/orders/sample.parquet")
orders = Asset.from_pyarrow(
    sample.schema.to_arrow_schema(),
    name="retail/orders",
    glue_table="analytics.orders",
)

# 2. From a pydantic v2 BaseModel
from pydantic import BaseModel, Field
class Order(BaseModel):
    order_id: int = Field(description="Primary key")
    amount: Decimal
    tags: list[str] = []

orders = Asset.from_pydantic(Order, name="retail/orders")

# 3. From an existing AWS Glue table (deploy-time fetch)
orders = Asset.from_glue_table(
    "analytics.orders",
    name="retail/orders",
    owner="data-team",
)
```

All three accept the full `Asset(...)` keyword set; the schema is
populated from the source, everything else (name, owner, tags,
freshness_hours, etc.) passes through unchanged. Passing `schema=`
explicitly to a `from_*` constructor is rejected with a clear TypeError.

#### Optional dependencies

```bash
pip install 'slsflow[pyarrow]'   # for from_pyarrow
pip install 'slsflow[pydantic]'  # for from_pydantic
pip install 'slsflow[all]'       # everything, including AI providers
```

`import slsflow` succeeds without either installed. Calling a `from_*`
without its peer dependency raises a clear ImportError that names the
exact extra to install. `from_glue_table` uses the existing required
`boto3` dependency; no extra needed.

#### Type-mapping highlights

  - **pyarrow → slsflow:** unsigned ints collapse to same-width signed
    (uint64 → bigint with overflow at the top of the range);
    `dictionary` and `fixed_size_list` collapse to their underlying
    types; `timestamp(tz=...)` becomes `tz_aware=True`, `timestamp()`
    becomes `tz_aware=False`.
  - **pydantic → slsflow:** `int` maps to `bigint` (Python int is
    unbounded); `Decimal` maps to `decimal(38, 9)` as the safe portable
    landing; `Optional[T]` and fields with defaults become
    `nullable=True`; nested models become `struct(...)`; enums and
    `Literal[...]` become `string`.
  - **Glue → slsflow:** reuses the existing `type_from_string` parser
    (ADR #42) so any type slsflow can emit can be read back from Glue
    without a second parser; `Comment` becomes `description`;
    `PartitionKeys` are merged in with `partition_key=True`.

#### Files

**New**

- `slsflow/adapters/__init__.py` — package marker.
- `slsflow/adapters/pyarrow_.py` — `pyarrow_to_columns` and
  `columns_to_pyarrow` (round-trippable for the lossless types; lossy
  documented). ~270 lines including docstrings.
- `slsflow/adapters/pydantic_.py` — `pydantic_to_columns`. Walks Python
  type annotations including Union, list, dict, nested BaseModel, Enum,
  Literal. ~220 lines.
- `slsflow/adapters/glue.py` — `glue_table_to_columns`. Thin wrapper
  around `boto3.client('glue').get_table()` plus the existing
  `type_from_string` parser. ~110 lines.
- `tests/sdk/test_adapters_pyarrow.py` — 65 tests: leaf types
  (parametrized over 18 pyarrow types), tz-aware vs ntz, nested types,
  nullability, round-trip across all 19 lossless slsflow types,
  documented-lossy round-trip, `Asset.from_pyarrow` integration.
- `tests/sdk/test_adapters_pydantic.py` — 28 tests: leaf types
  (int/float/str/bytes/bool/date/datetime/Decimal/UUID), nullability
  and defaults, field metadata (description), container types
  (list/dict/Optional), nested models, enums, `Asset.from_pydantic`
  integration.
- `tests/sdk/test_adapters_glue.py` — 17 tests: basic shape,
  partition-keys-marked, Comment as description, complex types via
  parser reuse, CatalogId / region pass-through, validation,
  `Asset.from_glue_table` integration.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #44.

**Changed**

- `slsflow/assets.py` — three new classmethods: `Asset.from_pyarrow`,
  `Asset.from_pydantic`, `Asset.from_glue_table`. Each delegates to the
  corresponding adapter. Lazy-imports the adapter so `Asset` itself
  never pulls pyarrow/pydantic at import time.
- `pyproject.toml` — new `[project.optional-dependencies]` groups
  `pyarrow` and `pydantic`; both added to `all`; both added to `dev`
  for CI test runs.
- `docs/features/ASSETS.md` — new "Constructing Assets from Existing
  Schema Sources" subsection with examples for all three constructors.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json` →
  `0.74.0`.

#### Verification

- `pytest tests/sdk/ tests/backend/`: 556 passed (446 prior + 110 new
  adapter tests), 16 skipped (e2e).
- `pytest sam/lambdas/console_api/tests/`: 103 passed.
- All round-trip tests pass for the 19 lossless types; lossy round-trips
  (varchar/char/uuid/json/time) documented and asserted to collapse to
  their pyarrow equivalents.
- Self-caught issue during test bring-up: initial Glue adapter used a
  `_require_boto3()` lazy-import wrapper, which broke `unittest.mock.patch`
  attempts to control the boto3 client (boto3 was not present as a
  module-level attribute). Fixed: boto3 is a base required dependency,
  so the defensive wrapper was unwarranted; replaced with a direct
  module-level `import boto3`.

## v73.0 (0.73.0) - 2026-05-03

### Glue Schema Sync — On-Demand Drift Detection (ADR #43)

The `glue_table` field on `Asset` (declarative since v0.72) now does
something. When a user opens an asset's Schema tab, the UI fetches the
actual schema from AWS Glue Catalog and shows a side-by-side diff against
the schema declared in code.

#### Why on-demand and not scheduled?

We considered two designs: a cron Lambda comparing declared-vs-Glue every
N hours and writing results to DDB; or a single fetch when the user looks
at the asset. We chose on-demand. The cron approach is what Dagster-style
"Asset Checks" do conceptually, but the cost/complexity story does not
hold up for declared-vs-external-catalog comparison: the user is the only
consumer, and they only care when they're looking. On-demand means one
new route, one IAM action, one React Query hook, no DDB table, no
EventBridge rule, no cleanup logic. ADR #43 walks through the trade-offs.

#### What the user sees

Open the Schema tab on an asset that has `glue_table` declared. Below the
declared-schema table, a Glue Sync panel appears with:

- Pill: ✓ In sync (green) / ⚠ Drift (red) / Glue error (orange)
- Last-checked timestamp + refresh button
- If drift detected: three sections by category (declared-but-missing-in-Glue,
  present-in-Glue-but-not-declared, type-mismatches), each with the
  affected column names and types
- If Glue is unreachable: structured error card with Glue's error code +
  message; declared schema still rendered

No polling, no auto-refresh on tab focus. One Glue API call per Schema-tab
open per 5 minutes (browser-side React Query cache). At realistic scale
(50 assets, 3 Glue databases) this is ~100 calls/month — well inside the
1M/month Glue free tier.

#### Backward compatibility

Zero. Existing assets without `glue_table` are unaffected (no panel
shown). Existing assets with `glue_table` get the new panel automatically;
no code changes required.

#### Files

**New**

- `sam/lambdas/console_api/tests/routes/test_assets_glue_schema.py` —
  15 tests covering request validation (404 on unknown asset, 422 on
  missing/malformed glue_table, URL-decoded asset names), Glue API
  successes (in-sync, missing-in-glue, extra-in-glue, type-mismatches,
  partition-keys-merged, comment-as-description, CatalogId pass-through),
  and Glue API failures (EntityNotFoundException, AccessDeniedException,
  EndpointConnectionError) all surfaced as 200 with embedded error.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #43.
- `GlueSyncPanel` + `DriftSection` components in `AssetDetailPage.tsx`.

**Changed**

- `sam/lambdas/console_api/routes/assets.py` — new `get_asset_glue_schema`
  route handler + `_glue_columns_to_schema` and `_diff_schemas` helpers.
  Reuses existing `_build_assets_from_pipelines` (single source of truth);
  no duplication of pipeline-scanning logic.
- `sam/lambdas/console_api/config.py` — lazy `glue` client following the
  existing `_LazyXxx` pattern for sfn/dynamodb/s3.
- `sam/lambdas/console_api/main.py` + `routes/__init__.py` — register
  `GET /api/assets/glue-schema` route.
- `sam/template.yaml` — `ConsoleApiRole` gains `glue:GetTable` permission
  on `Resource: "*"` (read-only, scoped).
- `tests/sdk/test_templates.py` — `test_route_table_completeness` updated
  from 49 to 50 expected routes; `/api/assets/glue-schema` added to the
  critical-routes assertion list.
- `ui/src/hooks/queries/useAssetQueries.ts` — `useAssetGlueSchemaQuery`
  hook (5-min staleTime, no polling, no refetch-on-focus). New types
  `AssetGlueSchema` and `GlueSchemaDiff`. Reuses existing
  `AssetSchemaColumn` from `@/types` (no duplication).
- `ui/src/hooks/queries/index.ts`, `ui/src/lib/queryClient.tsx` —
  re-exports + new query key `assetGlueSchema(name)`.
- `ui/src/components/AssetDetailPage.tsx` — `GlueSyncPanel` component
  rendered in Schema tab; pulls from new hook gated on
  `activeTab === 'schema' && Boolean(glueTable)`. `AlertTriangle` icon
  added.
- `ui/src/styles/modules/_assets.css` — replaces the placeholder
  `.adp-glue-hint` rules (now dead) with the full `.adp-glue-panel-*`,
  `.adp-glue-drift-section--{warn,info,error}`, `.adp-glue-col-*`,
  `.adp-spinning` ruleset for the new panel.
- `docs/features/ASSETS.md` — new "Glue Catalog Sync (on-demand)"
  subsection under Schema Declaration.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json` →
  `0.73.0`.

#### Verification

- `pytest tests/sdk/ tests/backend/`: 446 passed, 16 skipped (e2e).
- `pytest sam/lambdas/console_api/tests/`: 103 passed (88 prior + 15 new
  Glue-schema tests).
- TypeScript types-vs-JSX consistency check: all `.adp-glue-*` and
  `.adp-spinning` classes used in JSX have matching CSS rules; no orphan
  references to removed `.adp-glue-hint*` classes.
- Self-caught duplication: initial draft introduced a `SchemaColumn`
  interface that duplicated existing `AssetSchemaColumn` from `@/types`.
  Fixed before commit; all consumers reuse the central type (CLAUDE.md
  principle #1).

## v72.0 (0.72.0) - 2026-05-03

### Asset Schema 2.0 — Typed `Column` Class with Platform-Agnostic Type System (ADR #42)

Asset schemas now use a typed `Column` class with factory-built type instances
instead of freeform strings. Internal representation is a list of frozen
`Column` dataclasses; on-disk wire format is Glue-compatible. Legacy tuple
and dict declarations continue to work without any change.

#### Why

The previous schema field accepted only `("col", "bigint")` tuples or
`{"name": ..., "type": ..., "description": ...}` dicts with freeform string
types. Three concrete problems: no IDE help (typos surface only at runtime),
parametric types like `decimal(10,2)` had to be re-parsed on every comparison,
and there was no way to express constraints (nullable, primary key, partition
key). All four serious data-typing libraries we surveyed (pyarrow, SQLAlchemy,
Pandera, PyIceberg) use type instances rather than strings — Dagster is the
outlier and has open issues asking for stricter typing.

#### New API

```python
from slsflow import Asset, Column, types as t

orders = Asset(
    name="retail/orders",
    schema=[
        Column("order_id",   t.bigint(),       primary_key=True, nullable=False),
        Column("event_date", t.date(),         partition_key=True),
        Column("amount",     t.decimal(10, 2), description="USD amount"),
        Column("tags",       t.array(t.string())),
    ],
)
```

21 type classes covering Glue/Hive, Iceberg, BigQuery, and Snowflake primitives:
TinyInt, SmallInt, Int, BigInt, Float, Double, Decimal, Boolean, String,
Varchar, Char, Binary, FixedBinary, Date, Time, Timestamp, Uuid, Json, Array,
Struct, Map.

Constraint fields on `Column`: `nullable` (default `True`), `primary_key`,
`partition_key`, `unique`, `description`, `default`.

#### Backward compatibility (zero-change for existing pipelines)

- `schema=[("col", "bigint")]` and `schema=[("col", "bigint", "desc")]` still work.
- `schema=[{"name": "col", "type": "bigint"}]` still works.
- All forms can be mixed in one schema declaration.
- All three forms normalize to `List[Column]` internally via a single
  `slsflow.schema.normalize_schema()` function.
- Wire format on disk: defaults are omitted, so a legacy declaration produces
  byte-identical JSON. All 60 ASL snapshot tests pass without regeneration.

#### Schema conflict detection

When the same asset is declared with different schemas across multiple
pipelines, `_build_assets_from_pipelines` now keeps the richer schema (more
columns) and emits a `log.warn` with asset name, pipeline, and column counts.
Previously this was silent last-writer-wins.

#### Files

**New**

- `slsflow/schema.py` — type classes (21), factory functions, `Column`
  dataclass, `normalize_schema`, `column_to_dict`/`column_from_dict`,
  `to_glue_string`/`type_from_string`, `schema_richness`. ~570 lines including
  docstrings and `__all__`.
- `tests/sdk/test_schema.py` — 123 tests covering equality/hashability/
  immutability, validation rules, Glue string round-trip for all 21 types
  including nested, parser aliases (byte→tinyint, long→bigint, etc.),
  Column class + serialization, `normalize_schema` for all input forms +
  mixed lists, edge cases.
- `docs/reference/DESIGN_DECISIONS.md` — ADR #42.

**Changed**

- `slsflow/assets.py` — `Asset.__init__` calls `normalize_schema(schema)`;
  `Asset.schema` is always `List[Column]` internally; `Asset.to_dict()` uses
  `[column_to_dict(c) for c in self.schema]`. Private `_serialize_schema()`
  method removed (deduplication; logic now lives once in `schema.py`).
  Docstring rewritten with new typed examples and explicit backward-compat note.
- `slsflow/generators.py` — `_serialize_outlet()` uses `column_to_dict`
  instead of the removed `asset._serialize_schema()` method.
- `slsflow/__init__.py` — exports `Column`, `Schema`, `SlsflowType`, and
  re-exports `slsflow.schema` as `slsflow.types` for ergonomic factory access
  (`from slsflow import types as t; t.bigint()`).
- `sam/lambdas/console_api/routes/assets.py` — `_build_assets_from_pipelines`
  splits schema field out of the last-writer-wins enrichment loop and adds
  conflict detection (richer-wins + warning).
- `sam/lambdas/console_api/tests/routes/test_assets_helpers.py` — 6 new
  tests in `TestSchemaConflictDetection` covering same-schema/no-warn,
  richer-wins-second, richer-wins-first, warning-payload, empty-does-not-overwrite,
  equal-length-conflict-keeps-first.
- `ui/src/types/index.ts` — `AssetSchemaColumn` extended with optional
  `nullable`, `primary_key`, `partition_key`, `unique`, `default` fields.
- `ui/src/components/AssetDetailPage.tsx` — Schema tab gains a new
  "Constraints" column rendering 🔑 PK / 📅 Partition / NOT NULL / UNIQUE
  badges using the existing `.adp-badge` styles. `KeyRound` icon added.
- `ui/src/utils/icons.tsx` — `KeyRound` imported and re-exported.
- `ui/src/styles/modules/_assets.css` — one new rule
  (`.adp-schema-constraints`) for badge layout in the new column.
- `docs/features/ASSETS.md` — Schema Declaration section rewritten with the
  new API, type table, constraint table, legacy format note.
- `CLAUDE.md` — principle #6 clarified to state that research and option
  comparison are inputs to alignment (not deviations requiring approval);
  principle #12 extended with a second paragraph covering whole-module
  reuse from the Python ecosystem (pyarrow / pydantic / sqlalchemy / etc.)
  with this release's pyarrow-as-bridge pattern (ADR #42) cited as the
  reference example. Trigger: this session's near-miss where a 570-line
  custom type system was almost built from scratch before checking the
  ecosystem first.
- Version: `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json` →
  `0.72.0`.

#### Verification

- `pytest tests/sdk/ tests/backend/`: 446 passed, 16 skipped (e2e).
- `pytest sam/lambdas/console_api/tests/`: 88 passed.
- All 60 ASL snapshot tests pass without regeneration (proves backward compat
  for the wire format).
- Manual smoke check: tuple, dict, and `Column` declarations all produce
  correct internal representation and serialized output.

## v71.13 (0.71.13) - 2026-05-03

### Fix: 4 lambda tests broken by v71.11 DAL migration

Hotfix for `tests/test_utils.py::TestRecordManualDecision` (4 tests).
v71.11 P2#8b moved `record_manual_decision` off direct
`dynamodb.Table().put_item(...)` to `task_events_repo.put(item)`
(CLAUDE.md Principle #2). The `dynamodb` symbol was no longer imported
into `utils.py`, so the existing tests failed with
`AttributeError: module 'console_api.utils' has no attribute 'dynamodb'`
when `mocker.patch('console_api.utils.dynamodb.Table', ...)` tried to
resolve the path.

The tests were already pinned to the wrong abstraction — they verified
DynamoDB call shape (`put_item(Item={...})`) instead of repo behaviour
(`put({...})`). Fix updates all four tests to mock
`console_api.utils.task_events_repo.put` directly. Fewer mock layers,
matches the DAL pattern, and survives future infrastructure swaps below
the repo line.

#### Changed

- `sam/lambdas/console_api/tests/test_utils.py` — 4 tests in
  `TestRecordManualDecision` now patch `task_events_repo.put` instead of
  `dynamodb.Table`. Assertions check positional args (`call_args[0][0]`)
  instead of `call_args[1]['Item']`. Behaviour coverage unchanged —
  same 2-vs-1 put assertion, same item shape checks, same `#25` < `#30`
  ordering check.

#### Verification

- console_api lambda tests: 82 passed (was 78 passed / 4 failed)
- pytest sdk + backend + integration: 332 passed, 16 skipped
- All other green from v71.12 still green.

## v71.12 (0.71.12) - 2026-05-03

### Audit follow-up — observability hardening for typed silent excepts

Continuation of the v71.11 audit. The previous release tightened typed
exception handling in production-critical code paths; this release
finishes the cleanup by making the remaining typed silent excepts visible
in CloudWatch and tightening four broad `except Exception` sites in
`backfill.py` that masked AWS errors behind a generic `"unknown"` label.
No behavioural changes — purely diagnostics and adherence to CLAUDE.md
Principle #38 (every caught exception must log enough context to
diagnose).

#### Typed silent excepts → `log.warn` (5 sites)

These were already typed (so not Principle #38 violations as written),
but `pass`-on-typed-exception silently dropped diagnostic information
that callers had no other way to recover. Each now emits a structured
warning with the contextual identifiers needed to find the offending
record:

- `sam/lambdas/console_api/routes/pipelines_info.py:218` — malformed DAG
  snapshot in pipeline registry; falls back to building DAG from
  execution data. Logs `pipeline_name`.
- `sam/lambdas/console_api/routes/pipelines_list.py:463` — bad timestamp
  on execution summary; `duration_ms` left null. Logs `execution_id`,
  `earliest_started`, `latest_finished`.
- `sam/lambdas/console_api/routes/executions.py:164` — bad timestamp in
  `get_all_runs`; `duration_ms` left null. Logs `pipeline_execution`,
  `started_at`, `finished_at`.
- `sam/lambdas/console_api/routes/backfill.py:199` — malformed
  `asset_schedule` JSON in pipeline registry; that pipeline is skipped
  for the backfill. Logs `pipeline_name`.
- `sam/lambdas/console_api/routes/tasks.py:300` — bad timestamp in
  `get_all_tasks`; `duration_ms` left null. Logs `execution_name`,
  `actual_start`, `finished_at`.

The single remaining typed `except: pass` in `executions.py:320` is
intentional — it's the idempotency pattern around
`executions_repo.conditional_check_exception` (Principle #3) and stays
silent on purpose. Two CLI paths (`slsflow/deploy.py:360` SystemExit
recovery, `slsflow/ai/cli.py:573` arg parsing) are out of scope.

#### `backfill.py` — Principle #38 cleanup (4 sites)

Three sites used the placeholder `log.error("unknown", ...)` instead of
a real route label, and one retry path swallowed exceptions entirely.
All four now use the correct context label and a tightened exception
type:

- `:255` `backfill_by_asset` — per-DAG trigger failures
  → `(ClientError, BotoCoreError)`, logs `dag`, `date`.
- `:511` `backfill_pipeline` input building → `(KeyError, ValueError, TypeError)`,
  logs `date_str`. (AWS calls don't happen here; previous broad catch
  masked code defects as runtime errors.)
- `:540` `backfill_pipeline` throttle-retry → `(ClientError, BotoCoreError)`
  + `log.error` (was a silent `failed.append`).
- `:547` `backfill_pipeline` start-execution catch-all → `BotoCoreError`,
  logs `execution_name`, `date`. (`ClientError` already handled in the
  preceding `except ClientError`.)

#### AI module — typed catches (7 sites)

`SmartProvider.switch_provider` had five catch-all `except Exception` blocks
around per-provider initialization. Provider constructors only raise
`ImportError` (SDK missing), `ValueError` (key missing), or
`ConnectionError` (Ollama unreachable), so all five now use
`(ImportError, ValueError, ConnectionError)`:

- `slsflow/ai/providers.py:593` (Groq), `:608` (Anthropic), `:621` (OpenAI),
  `:631` (Ollama), `:644` (Gemini).

Two more in `slsflow/ai/core.py`:

- `:469` `save_pipeline` filesystem writes → `(OSError, ValueError)`.
- `:533` `list_pipelines` per-file parse → `(OSError, UnicodeDecodeError)`.

#### New DAL repo: `circuit_breakers_repo`

`health.py::_check_circuit_breakers` did direct `dynamodb.Table(...)` access
(Principle #2 — must use DAL repos) and read the table name straight from
`os.environ` (Principle #6 — env config should live in `config.py`). Both
fixed:

- New `sam/lambdas/console_api/dal/circuit_breakers_repo.py` follows the
  same pattern as the other repos. Has an `enabled` property since the
  feature is optional per deployment — when `CIRCUIT_BREAKER_TABLE` env
  is unset, `enabled=False` and `query_open()` returns `[]` so callers
  can stay agnostic.
- `CIRCUIT_BREAKER_TABLE` added to `config.py` env block.
- Registered in `dal/__init__.py`; exported alongside the existing six
  repos.
- `health.py` now imports `circuit_breakers_repo` from `dal`. Drops now-unused
  `os` and `dynamodb` imports. Adds `BotoCoreError` to the AWS-error
  catch (was `Exception`-only before).

#### Verification

- pytest: 332 passed, 16 skipped (sdk + backend + integration)
- vitest: 534 passed (35 files)
- TypeScript strict: 0 errors
- cfn-lint: clean
- `make lint`, `make sync-constants`, `make smoke-pipelines`,
  `make check-versions`: all green
- Smoke test confirmed `circuit_breakers_repo.enabled` flips correctly
  based on `CIRCUIT_BREAKER_TABLE` env presence.

#### Audit deltas

| Metric                                       | Before v71.12 | After v71.12 |
| -------------------------------------------- | ------------- | ------------ |
| Silent `except` (any kind)                   | 10            | 3            |
| `except Exception` without log/raise         | 11            | 3            |
| `log.error("unknown", ...)` placeholder      | 3             | 0            |
| Direct `dynamodb.Table(...)` in routes       | 1             | 0            |

Remaining 3 silent excepts: idempotency (`executions.py:320`) and two CLI
paths — all intentional. Remaining 3 broad `except Exception`: CLI
validator (`local.py:147,160`) and a debug helper (`generators.py:423`)
where catching widely is the documented intent.

## v71.11 (0.71.11) - 2026-05-03

### CLAUDE.md audit — P0/P1/P2 fixes across SFN, backend, UI, infra

Comprehensive audit against all 12 CLAUDE.md Core Principles. Found and
fixed three production-impacting silent failures (P0), four duplication /
pattern violations (P1), and five hygiene items (P2).

#### P0 — Critical (silent failures in production)

**1. Three Express SFN calls used `startExecution.sync:2`, which fails
silently on Express SFN per CLAUDE.md SFN Pitfall #2.** Migrated to
`aws-sdk:sfn:startSyncExecution` with JSONata `$string({...})` Input
serialization. Impact: PagerDuty alerts/resolves and asset notifications
were dropped without surfacing any error.

- `sam/sfn_templates/dependency_wrapper/sfn.tpl.json:596`
  `Resolve_PagerDuty` → PagerDutyResolverSfn (EXPRESS)
- `sam/sfn_templates/helpers/run_task/sfn.tpl.json:866`
  `Notify_Asset_Consumers_SFN` → NotifyAssetConsumersSfn (EXPRESS)
- `sam/sfn_templates/helpers/run_task/sfn.tpl.json:1324`
  `Send_PagerDuty_Alert` → PagerDutyAlerterSfn (EXPRESS)

Retry `ErrorEquals` updated from `StepFunctions.ExecutionLimitExceeded`
(synchronous-execution-only error) to `StepFunctions.TooManyRequests`
(correct for `startSyncExecution`). IAM already had
`states:StartSyncExecution` permission — no policy change needed.

**2. Two iteration loops over `pipeline-tokens` did not filter `_`
prefixed internal records, violating the CLAUDE.md `_notify_warn_*` rule.**

- `routes/health.py::get_metrics` — `_notify_warn_*` records were counted
  as `failed` tasks, inflating failure count and skewing `success_rate`.
  Also fixed denominator: `total = len(real_items)` (was `len(items)`,
  which mixed internal records into the divisor).
- `routes/pipelines_info.py::get_pipeline_logs` — internal records
  surfaced as task entries in the pipeline logs view.

#### P1 — Pattern violations

**3. Removed duplicate `is_internal_record` definition** in
`sam/lambdas/console_api/utils.py` (Principle #1). Kept the more complete
docstring; second declaration silently shadowed the first.

**4. Deleted 29 dead CSS files** (Principle #1, ~110 KB / 5,322 lines):
- 28 `.module.css` files in `ui/src/components/` — none were imported
  anywhere (every `*.module.css` had zero references in `.ts(x)` files).
- `ui/src/styles/modules/_status.css` — not imported in `index.css`,
  selectors already duplicated in loaded `_assets.css`.

#### P2 — Hygiene

**5. `routes/health.py`** — replaced 6 `print(f"[unknown] ...")` calls
with structured `log.error("<fn_name>", "...", error=str(e))` per
Principle #2 / ADR #38. Now CloudWatch Insights queries by `fn` work
correctly for health checks.

**6. `routes/tasks.py::_reconcile_orphaned_tasks`** — three bare
`except Exception: pass` blocks replaced with
`except (ClientError, BotoCoreError) as e` + `log.warn`/`log.info` per
ADR #28 + ADR #38. Reconciliation failures now visible.

**7. Direct `boto3.client('stepfunctions')` in `routes/assets.py:392`**
replaced with the shared `config.sfn` singleton (Principle #2). Dropped
unused `import boto3`.

**8. Direct `dynamodb.Table(TASK_EVENTS_TABLE)` in `utils.py`** replaced
by extending `task_events_repo` with a `put(item)` method (Principle #12
— extend existing primitives, don't fork). `record_manual_decision` now
uses the repo. Dropped now-unused `dynamodb`/`TASK_EVENTS_TABLE` imports
from `utils.py`.

**9. Duplicated env var** in `template.yaml` — `NotifyAssetSubscribersFunction`
had both `ASSET_SUBSCRIPTIONS_TABLE` and `SUBSCRIPTIONS_TABLE` pointing
at the same table (`AssetSubscriptionsTable`). The Lambda code only reads
`SUBSCRIPTIONS_TABLE` (consistent with `check_assets` and
`query_subscriptions`). Removed the unused `ASSET_SUBSCRIPTIONS_TABLE`.

**10. CLAUDE.md ADR table** — added missing ADR #41 (URL Routing —
CloudFront Function rewrites + `window.history` for per-route deep state),
which had been merged in v0.71.x but not reflected in the agent
instructions table (Principle #9).

**11. `Makefile` lint target** — pre-existing limitation: `make lint` ran
`json.load()` directly on `.tpl.json` files, which broke on numeric
template substitutions like `${pause_heartbeat_seconds}` (CLAUDE.md SFN
Pitfall #1 explicitly notes "CI strips numeric vars with regex"). Added
the same regex strip used by CI so `make lint` now succeeds locally.

### Files changed

**SFN templates:**
- `sam/sfn_templates/dependency_wrapper/sfn.tpl.json`
- `sam/sfn_templates/helpers/run_task/sfn.tpl.json`

**Backend (`sam/lambdas/console_api/`):**
- `utils.py` — removed duplicate function, swapped to repo, dropped imports
- `dal/task_events_repo.py` — added `put()` method
- `routes/health.py` — `_` prefix filter, log.error, success_rate fix
- `routes/pipelines_info.py` — `_` prefix filter
- `routes/tasks.py` — typed excepts + structured logging
- `routes/assets.py` — shared sfn singleton

**Infrastructure:**
- `sam/template.yaml` — removed duplicate env var

**Tests:**
- `tests/backend/test_alerting.py` — adapted 4 tests to new
  `Input` shape (string-based JSONata vs object), preserving intent

**UI:**
- 28 dead `*.module.css` files in `ui/src/components/` deleted
- `ui/src/styles/modules/_status.css` deleted

**Docs / tooling:**
- `CLAUDE.md` — ADR #41 added to Key ADRs table
- `Makefile` — lint target now strips `${var}` substitutions
- `pyproject.toml`, `slsflow/__init__.py`, `ui/package.json` — version bump

### Tests

- ✅ pytest sdk + backend + integration: **332 passed, 16 skipped**
- ✅ vitest: **534 passed** (35 files)
- ✅ TypeScript strict: 0 errors
- ✅ Next.js build: 6 static routes
- ✅ cfn-lint: 0 errors
- ✅ `make check-versions`: 0.71.11
- ✅ `make smoke-pipelines`: 4/4 dag.py
- ✅ `make sync-constants`: in sync
- ✅ `make lint`: passes (Python + JSON templates)

### Deploy

Full release (SFN + Lambda + UI). All three migrated SFN states require
`sam build && sam deploy` — `sam build` re-inlines `.tpl.json` definitions
into `DefinitionString`. No DynamoDB / IAM / table changes.

```bash
cd sam && sam build && sam deploy --profile <profile>
cd ../ui && npm ci && npm run build && ./deploy.sh --profile <profile>
aws cloudfront create-invalidation --distribution-id ID --paths "/*"
```

**Backward compatibility:** All changes are wire-format-compatible.
The three migrated SFN states accept the same `Input` shape (the JSON
the downstream Express SFN sees is identical) — only the upstream call
mechanism changed.

---

## v71.10 (0.71.10) - 2026-05-03

### Cleanup — dead code removed (Principle 1)

Audit against CLAUDE.md found three pieces of dead code left over from the
URL routing refactor (v0.71.0–v0.71.9). Removed.

**Removed:**
- `types/index.ts` — `interface HeaderProps` (had `mainView: MainView`
  field, obsoleted when Header.tsx switched to local interface +
  `usePathname()`)
- `types/index.ts` — `interface BreadcrumbsProps` (same reason)
- `test/factories.ts` — `createHeaderProps()` factory (used the dead
  interfaces, never imported)

**Kept (still used):**
- `MainView` type, `MAIN_VIEWS` constant, `isMainView()` guard — used by
  `App.tsx` to validate CommandPalette navigation targets and by
  `utils/routing.ts:viewFromPathname()`

### Tests

- ✅ vitest: 534 passed
- ✅ TypeScript: 0 errors
- ✅ Next.js build: 6 static routes
- ✅ pytest: 332 + 82 = 414 passed
- ✅ cfn-lint: 0 errors
- ✅ `make check-versions`: 0.71.10

### Deploy

Frontend-only release. CloudFront Function from v0.71.8 unchanged.

```bash
cd ui && npm ci && npm run build && ./deploy.sh
aws cloudfront create-invalidation --distribution-id ID --paths "/*"
```

---

## v71.9 (0.71.9) - 2026-05-03

### Per-route URL deep state — leak fix + filter sync

Fixes a bug from v0.71.8: deep state for `/pipelines/` (selectedPipeline)
was leaking onto other routes (e.g. `/assets/?pipeline=acme-daily` had no
business showing `?pipeline=`), and adds URL sync for the rest of the
deep state across all routes.

### Bug fix — leak

`useStoreInit` was writing `pipeline=` to the URL on every route change
because its effect on `store.selectedPipeline?.name` fired regardless of
which route was active. With store still holding `selectedPipeline` from
a previous `/pipelines/` visit, navigating to `/assets/` immediately
pushed `?pipeline=` to the URL on the new route.

Fix: `useStoreInit` now reads `usePathname()` and gates URL writes by
`isPipelinesRoute(pathname)`. Pipeline state is only mirrored to URL on
`/pipelines/`. Other routes own their own URL state independently.

### Generalized `useUrlSync`

Hook now accepts a generic state shape via TypeScript generic + `keys`
config:

```ts
interface UseUrlSyncOptions<T> {
  keys: ReadonlyArray<keyof T & string>;  // Allowed URL params
  defaults?: Partial<T>;                  // Values omitted from URL
  onChange?: (state: Partial<T>) => void; // Browser back/forward callback
}

const { initialState, updateUrl, replaceUrl } = useUrlSync<MyState>({
  keys: ['asset', 'tab'],
  defaults: { tab: 'lineage' },
});
```

Each route uses its own keys → no cross-route leak by construction.

### URL sync added per route

**`/assets/`:** `?asset=acme/foo&tab=schema&group=acme&view=list`
- `asset` — selected asset name (e.g. `acme/attribute_tags`)
- `tab` — active tab (`lineage` is default, omitted from URL; explicit
  values: `catalog`, `events`)
- `group` — selected group name when drilling into a folder
- `view` — catalog view (`folders` is default; explicit: `list`)

**`/tasks/`:** `?status=failed&date=2026-04-15&pipeline=etl_main&taskName=transform`
- All four `TaskFilter` fields mirrored to URL
- Empty filter values omitted (clean URL on no filter)

**`/runs/`:** `?status=running&pipeline=etl_main`
- Both `RunFilter` fields mirrored to URL
- `date` is intentionally NOT in URL — it's controlled by the global
  header date picker, shared with `/pipelines/`

### What's still NOT in URL (intentional)

- `searchQuery`, `tagFilter` in AssetsView — quick filters, not
  shareable state
- `selectedTaskName` (modal-driven) — modal is transient
- `sort` column/direction in tables — UI preference, not navigational
- `collapsedGroups` in catalog — UI preference

### Tests

- ✅ vitest: **534 passed** (was 532; +2 new for generic useUrlSync)
- ✅ TypeScript: 0 errors
- ✅ Next.js build: 6 static routes
- ✅ pytest: 332 + 82 = 414 passed
- ✅ `make check-versions`: 0.71.9

### URL examples after this release

| URL | Meaning |
|---|---|
| `/pipelines/?pipeline=etl_main&mode=gantt&date=2025-04-15` | Pipeline run view |
| `/assets/?asset=acme/foo&tab=schema` | Asset schema tab |
| `/assets/?group=acme&view=list` | Catalog list view in acme group |
| `/tasks/?status=failed&taskName=transform` | Failed `transform` tasks |
| `/runs/?status=running` | Running runs |

### Verification

After deploy, navigate from `/pipelines/?pipeline=acme-daily` to `/assets/`
— URL should change to `/assets/` (no leftover `?pipeline=`).

Click into asset detail — URL becomes `/assets/?asset=acme/foo`.
Switch tab — URL becomes `/assets/?asset=acme/foo&tab=schema`.
Refresh — same view restored.

Apply filter on `/tasks/` — URL reflects filter. Refresh — filter
applied. Share URL — recipient sees same filter.

### No infrastructure changes

Same CloudFront Function from v0.71.8. Frontend-only release. Deploy:

```bash
cd ui && npm ci && npm run build && ./deploy.sh
aws cloudfront create-invalidation --distribution-id ID --paths "/*"
```

---

## v71.8 (0.71.8) - 2026-05-03

### Path-based URL routing — CloudFront Function approach

Adds path-based URLs for top-level views (`/pipelines/`, `/assets/`,
`/tasks/`, `/runs/`) backed by a CloudFront Function that rewrites SPA
paths to the corresponding pre-rendered `index.html`. Deep state
(selected pipeline, view mode, date, execution) stays in URL search
params and is mirrored via `window.history` directly — no Next router,
no sync hooks, no feedback loops.

Seven previous releases (v0.71.0–v0.71.7) attempted this without the
infrastructure change and each broke production differently. The root
cause was identified in this release and documented in ADR #41: with
S3 OAC origin (REST endpoint, not website endpoint) CloudFront cannot
auto-resolve `index.html` inside folders, so any path-based URL fell
back to root index.html and looped. CloudFront Function fixes this at
the edge.

### Infrastructure changes

**`sam/template.yaml`:**
- New resource `ConsoleUiUrlRewriteFunction` (`AWS::CloudFront::Function`)
  - Runtime: `cloudfront-js-2.0`
  - Auto-publish on deploy
  - Inline JS function rewrites `/pipelines/anything` → `/pipelines/index.html`
    (same for `assets`, `tasks`, `runs`)
  - Only matches paths without file extensions, so `/_next/...` assets
    pass through unchanged
- `ConsoleUiDistribution.DefaultCacheBehavior.FunctionAssociations` —
  associates the function as `viewer-request` event handler
- `CustomErrorResponses` (404 → /index.html) — kept as backstop for
  genuinely missing paths that don't match SPA route prefixes

### Frontend changes

**Removed:**
- `mainView`, `setMainView`, `switchView` from Zustand store (pathname is
  the source of truth)
- `view` parameter from `useUrlSync` URL state

**New:**
- `app/page.tsx` — root redirect to `/pipelines/` with `useRef` guard,
  preserves legacy `?pipeline=&mode=&date=&execution=` params on redirect
- `app/pipelines/page.tsx`, `app/assets/page.tsx`, `app/tasks/page.tsx`,
  `app/runs/page.tsx` — each renders `<App />`. App reads `usePathname()`
  to choose which view to render

**Updated:**
- `App.tsx` — derives `mainView` from `usePathname()`; keyboard shortcuts
  `1`/`2`/`3`/`4` and CommandPalette navigation use `router.push('/{view}/')`;
  ErrorBoundary fallback uses `router.push('/pipelines/')`
- `Header.tsx` — same pathname-based view detection; tab clicks call
  `router.push('/{view}/')`; Breadcrumbs read from pathname
- `useStoreInit.ts` — uses `useRouter()` internally; no longer touches
  `mainView`; `navigateToExecution` ends with `router.push('/pipelines/')`
- `useUrlSync.ts` — removed `view` param; `buildUrl()` preserves current
  `window.location.pathname` so search params live alongside any pathname

### Architecture rationale

**Why CloudFront Function (not in-app routing alone):**
- S3 with OAC uses the REST endpoint, not the website endpoint. REST
  doesn't resolve `index.html` inside folders. Without a rewrite, a
  request for `/pipelines/etl_main` returns S3 404, falls back to root
  `/index.html`, and the SPA never sees the deep path.
- CloudFront Function handles this at the edge in <1ms, costs ~$0.10
  per million requests, and requires no Lambda or extra infrastructure.

**Why `window.history` for deep state (not `router.push`):**
- `router.push` to a same-pathname URL with different search params
  triggers RSC prefetch (`?_rsc=...`), which doesn't exist as a static
  file → CloudFront 404 → fallback → loop. We hit this in v0.71.0–v0.71.6.
- `window.history.pushState/replaceState` is silent — it updates the
  URL bar without involving Next router, RSC, or any network request.
  The app reads URL params on mount via `parseUrl()`. That's the entire
  mechanism.

**Why `mainView` removed from store:**
- Two sources of truth (store + pathname) caused drift bugs in earlier
  versions. Pathname is now the only source for top-level view; store
  holds only deep state (selectedPipeline, viewMode, date, etc.).

### Tests

- ✅ vitest: **532 passed**
- ✅ TypeScript: 0 errors
- ✅ Next.js build: clean, 6 static routes (`/`, `/_not-found`,
  `/pipelines`, `/assets`, `/tasks`, `/runs`)
- ✅ pytest: 332 + 82 = 414 passed
- ✅ `make check-versions`: clean at 0.71.8

### Deploy procedure (CRITICAL — order matters)

```bash
# 1. Deploy infra FIRST so CloudFront Function is active before
#    any frontend code expects path-based routing to work
cd sam && sam deploy

# Wait for CloudFormation status = UPDATE_COMPLETE (~3-5 minutes)
aws cloudformation describe-stacks --stack-name slsflow-dev \
  --query 'Stacks[0].StackStatus'

# 2. Deploy frontend with path-based routes
cd ../ui && npm ci && npm run build && ./deploy.sh

# 3. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"

# Wait for invalidation Status = Completed (~3-5 minutes)
aws cloudfront list-invalidations --distribution-id YOUR_DIST_ID
```

**If you deploy frontend BEFORE the infra**, path-based URLs will 404
and CloudFront will fall back to root `/index.html` until the Function
is active. Same loop as v0.71.0–v0.71.6.

### Verification (after deploy)

Hard refresh (Cmd+Shift+R) in incognito:

1. Open `/pipelines/` directly — Pipelines view loads, no console errors,
   no loop in DevTools console
2. Click a pipeline in sidebar — URL becomes `/pipelines/?pipeline=...`,
   pipeline data loads, executions list visible
3. F5 — pipeline persists, executions list still loads
4. Click Assets tab — URL changes to `/assets/`
5. Click an asset — URL stays `/assets/` but asset detail loads (deep
   state in component, not URL — known limitation, may add later)
6. Browser back — returns to previous state
7. Direct visit to `/assets/?pipeline=foo` — Assets view loads, store
   `selectedPipeline` set to foo (deep state restored across routes)
8. Old bookmark `/?view=assets&pipeline=foo` — redirects once to
   `/assets/?pipeline=foo`

### Rollback procedure

If anything breaks in production:

**Option A — disassociate function (fastest, ~1 minute):**
1. AWS Console → CloudFront → distribution → Behaviors → Edit Default
2. Remove Function association
3. Save → automatic deploy (~5 min for edge propagation)
4. Redeploy `slsflow_baseline_v70_18.tar.gz`

**Option B — redeploy v0.70.18 (~10 minutes):**
1. Extract `slsflow_baseline_v70_18.tar.gz`
2. `cd sam && sam deploy` (will remove Function from template)
3. Wait UPDATE_COMPLETE
4. `cd ui && npm ci && npm run build && ./deploy.sh`
5. CloudFront invalidation
6. Hard refresh

### Cost impact

- CloudFront Function: ~$0.10 per 1M requests
  - At 100 daily requests: ~$0.0003/month — effectively free
  - At 100k daily requests: ~$0.30/month
- No new Lambda, no new IAM role, no new CloudWatch logs
- Total cost change: < $1/month

---

## v70.18 (0.70.18) - 2026-05-03

### Bug fixes — orphan-detection correctness + delete completeness

External code review (see analysis report) identified two latent correctness
bugs in `dal/assets_repo.py` that were silently truncating asset operations.
Both fixed by reusing the existing `scan_all` / `query_all` helpers from
`utils.py` (Principle #12 — maximize reuse), so we get free pagination,
safety-cap warnings, and a single tested code path.

**1. `delete_by_asset` — silent truncation at 1000 events**

Previous implementation:
```python
items = self.query_by_asset(asset_name, limit=1000, descending=False)
```
For an asset with >1000 events, only the first 1000 were deleted; the
docstring claimed "Delete all events". On the next `delete_orphaned_assets`
run, the asset re-appeared in the orphan list (it still had events) and
got partially deleted again. Eventually consistent, misleading metrics.

**Fix:** route through `query_all(table, max_items=Limits.MAX_SCAN_ITEMS, ...)`
which paginates fully and logs a warning if the 50000-row safety cap is hit.

**2. `list_asset_names` — incorrect early-exit on `len(names) >= max_items`**

Previous implementation conflated *page size* and *total names limit* using
the same parameter:
```python
params = {'ProjectionExpression': 'asset_name', 'Limit': max_items}
...
if 'LastEvaluatedKey' not in response or len(names) >= max_items:
    break
```
With default `max_items=500`:
- If the table had >500 unique assets, the scan stopped at 500 → orphan
  detection silently missed assets 501..N. **Determinism risk:** which
  assets get missed depends on DDB scan order.
- If the table had ≤500 unique but many duplicate events, the per-page
  `Limit` was already 500 so cost was fine, but the early-exit never
  fired, so we paid for a full scan anyway.

**Fix:** route through `scan_all(table, max_items=Limits.MAX_SCAN_ITEMS,
ProjectionExpression='asset_name')`, then dedupe in memory. Default cap
raised from 500 → `Limits.MAX_SCAN_ITEMS` (50000) so production tables
with >500 unique assets are no longer silently truncated.

### Observability — `_build_assets_from_pipelines` warning logs

Two `except (json.JSONDecodeError, TypeError): pass` blocks replaced with
`log.warn` calls including `pipeline=<name>` and `error=<message>`:

- Malformed `asset_schedule` JSON in pipeline_registry → previously vanished
  silently, causing the pipeline's trigger config to be invisible in UI.
- Malformed `tasks` JSON → previously vanished silently, hiding all the
  pipeline's outlets/inlets from orphan-detection. **This was a real
  amplifier for bug #1 above:** a pipeline with corrupt `tasks` would
  cause its valid assets to be flagged as orphaned and have their event
  history deleted.

Now operators see warnings in CloudWatch and can fix the pipeline before
running orphan cleanup.

### Audit logging — `delete_orphaned_assets` per-asset trail

Each actual deletion now emits two `log.info` entries: one announcing
intent (`Deleting events for orphaned asset`, `asset_name=…`) and one
recording the result (`Deleted events`, `asset_name=…`, `events_deleted=N`).

Rationale: a stray large delete (e.g. 50000 events for what looked like a
small asset) is now visible in CloudWatch immediately, not buried in the
aggregate response. This complements the warning logs above — together
they form a paper trail when something goes wrong.

### Tests added (37 new)

- **`tests/dal/test_assets_repo.py`** (10 tests)
  - `delete_by_asset`: empty / single-page / 3-page-1800-event pagination /
    correct KeyConditionExpression
  - `list_asset_names`: empty / dedupe / multi-page / discard empty / uses
    ProjectionExpression / respects safety cap
- **`tests/routes/test_assets_helpers.py`** (19 tests)
  - Basic shape: empty input, missing tasks, single outlet→producer, single inlet→consumer
  - Enrichment: owner/schema/tags/glue_table/glue_catalog/freshness_hours from
    dict outlets; string-shape outlets as legacy fallback; freshness_hours=0 preserved
  - `wait_for`: dict-with-`name` and string shapes both create consumers
  - Dependency-derived consumer: task B depends on task A → A's outlet has B as consumer
  - Group derivation from `prefix/name`
  - `asset_schedule` populates dag_triggers; empty schedule skipped
  - **Malformed data resilience:** bad tasks JSON / bad asset_schedule JSON →
    warning emitted, helper continues, other pipelines fully processed
  - Multi-pipeline: outlet in P1 + inlet in P2 → producer/consumer linked across
- **`tests/routes/test_delete_orphaned.py`** (8 tests)
  - Dry-run default + explicit; no `delete_by_asset` calls in dry-run
  - Actual deletion: orphans only, never referenced assets; `events_deleted` aggregated
  - Partial failure (one orphan's delete raises ClientError) → others still proceed
  - Audit log per orphan: each delete produces info-level entry with `asset_name` + `events_deleted`
  - Orphan-detection contract: inlet-only assets NOT orphans, wait_for-only NOT orphans,
    in-events + never-referenced ARE orphans

### Compliance

- ✅ Principle #1 (No duplication) — both fixes reuse `scan_all`/`query_all` instead of
  inventing pagination
- ✅ Principle #4 (Stability) — 414 pytest pass (323 → 360 unit + 54 unchanged
  in test_utils; SDK 169, backend 163, console_api 82); cfn-lint clean
- ✅ Principle #11 (No stubs) — silent excepts now produce real warnings; no
  TODOs or skipped logic
- ✅ Principle #12 (Maximize reuse) — `scan_all`/`query_all` were already there,
  used directly instead of forking a new pagination loop
- ✅ ADR #28 (Version sync) — pyproject 0.70.18 / `__init__.py` 0.70.18 /
  `package.json` 0.70.18

### Verification

- 414 pytest pass (was 323 → +37 new + already-extant test_utils 54)
  - SDK: 169 passed, 16 skipped
  - Backend + Integration: 163 passed
  - Console API: 82 passed (10 new DAL + 19 new helper + 8 new orphan + 45 existing utils)
- `make check-versions` clean
- `python -m py_compile` clean across slsflow/, sam/lambdas/, pipelines/

### Migration notes

**No schema changes. No infra changes. No API changes.** Drop-in patch.

**Behavior change visible to operators on first prod deploy:**
After deploying, the next `POST /api/assets/orphaned` (with `dry_run=true`)
may return a longer `would_delete` list than before — these are pre-existing
orphans that the old `list_asset_names` silently truncated past. They are
not new orphans; they were always there. Review the list before flipping
`dry_run=false`.

If `_build_assets_from_pipelines` warnings appear in CloudWatch, fix the
referenced pipeline (re-deploy with valid `tasks`/`asset_schedule` JSON)
**before** running cleanup with `dry_run=false`.

---

## v70.17 (0.70.17) - 2026-05-02

### CLAUDE.md compliance audit + fixes for self-introduced violations

Per Mike's request, ran a full audit against all 12 Core Principles and ADR #40.

**Audit results — passing:**
- ✅ #2 Follow patterns — 0 `unittest.mock` in tests/ (only allowed exceptions)
- ✅ #4 Stability — 323 pytest pass, cfn-lint clean, tsc 0 errors, 531 vitest pass
- ✅ #7 Finish what you start — every version v70.7..v70.16 has CHANGELOG entry
- ✅ #10 English only — 0 Cyrillic violations
- ✅ #11 No stubs — 0 TODO/FIXME/silent except in production code; only `placeholder=` HTML attributes (legitimate)
- ✅ ADR #40 #1 No magic numbers — 0 `calc(100v[hw] - Npx)` occurrences
- ✅ ADR #40 #6 `.app { height: 100vh; overflow: hidden }` confirmed in `_base.css`

**Audit results — violations found and FIXED:**

**1. Principle #1 (No duplication) — `_status.css` was 312 lines of dead code**
- File NOT imported in `index.css` — confirmed
- Contained 34 selectors, ALL duplicated from `_navigation.css`, `_utilities.css`, `_assets.css`, `_dag.css`, `_layout.css`, `_modals.css`, `_enhanced-ui.css`
- 0 unique selectors
- **Action:** deleted `ui/src/styles/modules/_status.css` entirely

**2. Principle #12 (Maximize reuse) — 8 copies of card-surface**
Self-introduced in v0.70.13–0.70.14 — I copy-pasted the same 3 properties
(`background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px`)
into 8 separate rules instead of unifying. This violates the very principle I added
to CLAUDE.md in v0.70.16.

Affected selectors:
- `.dag-container` (`_dag.css`) — pre-existing
- `.cp-command-palette` (`_enhanced-ui.css`) — pre-existing
- `.ntf-notification-dropdown`, `.ntf-notification-toast` (`_layout.css`) — pre-existing
- `.adp-page`, `.av-catalog`, `.av-recent-events-panel`, `.alf-lineage-flow-container`
  (`_assets.css`) — added by me in v70.13–14

**Action:** unified all 8 into a single group selector in `_utilities.css`:
```css
.dag-container, .cp-command-palette, .ntf-notification-dropdown,
.ntf-notification-toast, .adp-page, .av-catalog,
.av-recent-events-panel, .alf-lineage-flow-container {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
}
```
Each individual rule retains only its UNIQUE properties (height, margin, layout).

**Visual outcome:** identical — same card look across all panels. No TSX changes needed.

**Code reduction:** ~24 lines removed from `_dag.css`/`_enhanced-ui.css`/`_layout.css`/`_assets.css`,
+12 lines added to `_utilities.css` = **net −12 lines, −7 duplications**.

**Audit findings — minor, NOT addressed (filed for future reference):**
- `.card` defined in both `_utilities.css` (with body) and `_enhanced-ui.css` (just `transition`) — split rule, not a true duplicate
- `.alf-animated-edge-path` defined in `_assets.css` (`pointer-events: none`) and `_enhanced-ui.css` (`animation`) — split rule, not a true duplicate
- These are pre-existing, low-risk; logging them rather than touching working CSS

**Verification:**
- 323 pytest pass
- 531 vitest pass
- cfn-lint clean
- tsc 0 errors
- 0 Cyrillic
- 0 magic numbers
- 0 duplicate selectors within `@media` blocks
- 1 card-surface rule (was 8)

---

## v70.16 (0.70.16) - 2026-05-02

### CLAUDE.md: New Core Principle #12 — Maximize reuse, check before going custom

Added Principle #12 to mandate active search for existing primitives before creating
new custom code. Complements #1 (no duplication) and #2 (follow existing patterns)
but prescribes an explicit workflow: `grep`/check before writing new components,
helpers, CSS classes, constants, or utilities.

Concrete examples documented:
- Reuse: `cors_response()`, `BaseModal`, `.dag-container` card style (now applied to
  `.alf-lineage-flow-container`, `.adp-page`, `.av-catalog`, `.av-recent-events-panel`),
  DAL repository pattern, `task_variables.py` single schema
- Forbidden: inline duplication of flex utilities, second warning banner when one exists,
  inline date-format in 3 places, parallel CSS classes for the same visual effect

When existing primitive doesn't fit → extend/generalize, don't fork. Custom is last resort.

**No code/test changes** — documentation only.

**Compliance:**
- ✅ #4 Stability — 323 pytest pass, cfn-lint clean
- ✅ #10 English only — Cyrillic 0
- ✅ #11 No stubs

---

## v70.15 (0.70.15) - 2026-05-02

### UI: aggressively shrink Lineage Search panel on tablet/mobile

Mike feedback: at ~700px viewport (tablet portrait or zoomed-out browser), the Lineage Search panel was still too large (~280px wide).

**Stricter mobile rules at ≤768px:**
- `.alf-lineage-panel` — `max-width: 180px` (was unbounded), padding 6px (was 8px), font 0.7rem (was 0.75rem), gap 4px
- `.alf-lineage-panel__search` — font 11px, padding 4px 6px (was 12px / default padding)
- `.alf-lineage-panel__prefixes` — gap 3px (tighter All/ACME pills)
- `.alf-lineage-panel__filters` — `flex-direction: row` with `flex-wrap` (was column) — lays out 3 checkboxes inline, saves vertical space
- `.alf-lineage-panel__filter input[type="checkbox"]` — 12×12px (smaller boxes)
- `.alf-lineage-panel__filter-label` — font 0.65rem, gap 3px
- `.alf-prefix-btn` — padding 2px 5px, font 0.65rem

Net effect: panel ~180×80px on a ~700px viewport (was ~280×140px).

**Compliance:**
- ✅ #1 No duplication — verified 0 duplicate selectors within @media
- ✅ #4 Stability — 323 pytest pass, cfn-lint clean
- ✅ #11 No stubs — real CSS rules
- ✅ ADR #40 #1 — 0 magic numbers

---

## v70.14 (0.70.14) - 2026-05-02

### UI: Card styling for all Asset views + View in Catalog in tabs row + mobile MiniMap

Per Mike feedback (screenshots):

**1. View in Catalog moved to tabs row**
Previously placed in modal header (next to close button) — too small/unobvious. Moved to right of Actions tab, with `margin-left: auto` to push to right edge of tabs bar. More prominent, no extra clicks needed.

- `AssetDetailModal.tsx` — removed header-actions wrapper, added button as last child of `.nav-tabs`
- `_modals.css` — new `.nav-tabs .adm-view-in-catalog-btn` selector with `margin-left: auto`
- `_navigation.css` — `.nav-tabs` got `align-items: center` for proper button alignment

**2. Card-style applied to ALL Asset pages (not just Lineage)**
Previously only `.alf-lineage-flow-container` had card style — but card border wasn't visible because `.av-lineage-wrapper` had no padding (border touched viewport edge). Mike confirmed all Asset views should have card look.

- `.adp-page` — `background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; overflow: hidden`
- `.av-main-content > .adp-page` — `margin: 16px` (border visible from screen edges)
- `.av-catalog` — same card treatment + margin: 16px (used for asset catalog list/folder views)
- `.av-recent-events-panel` — same card treatment + margin: 16px
- `.av-lineage-wrapper` — `padding: 16px` so the inner `.alf-lineage-flow-container` border is visible

**3. Mobile: hide MiniMap, smaller card margins**
Mike feedback: "MiniMap drifts off-screen / hides somewhere" on narrow viewports.

- `≤768px` — MiniMap completely hidden (was: shrunk to 100×70px). Both `.alf-lineage-flow-container` and `.dag-container` minimaps.
- `≤768px` — Card margins reduced from `16px` to `8px` to save horizontal space on phones
- `≤768px` — `.av-lineage-wrapper` padding reduced from `16px` to `8px`

**Compliance per CLAUDE.md:**
- ✅ #1 No duplication — verified no duplicate selectors within any `@media` block
- ✅ #2 Follow existing patterns — reused `.dag-container` card style for Asset views
- ✅ #4 Stability — 323 pytest pass, cfn-lint clean, all CSS balanced
- ✅ #11 No stubs — real CSS rules, no placeholders
- ✅ ADR #40 #1 No magic numbers (0 occurrences)
- ✅ ADR #40 #7 — verified `AssetDetailModal.module.css` is dead code, edits go to `_modals.css` and `_navigation.css`

---

## v70.13 (0.70.13) - 2026-05-02

### UI: UX feedback from screenshots — Lineage card style + quick navigation + responsive panels

**1. Quick "View in Catalog" link on AssetDetailModal header**
Per user feedback (Image 1, 2): the "View in Catalog" action lived only on the Actions tab, requiring an extra click. Now also available as a button on the modal header (next to close), available immediately on any tab.

- `AssetDetailModal.tsx` — added header-action container with `View in Catalog` button next to close
- `_modals.css` — new `.adm-asset-modal-header-actions` flex container, `.adm-view-in-catalog-btn` style (border + accent on hover)

**2. Card styling for Asset Lineage Graph (matches Pipelines DAG visual)**
Per user feedback (Image 3): user prefers DAG's rounded-card look. Applied same treatment to Asset Lineage everywhere it appears.

- `.alf-lineage-flow-container` — `background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px` (was: bg-primary, 8px, no border)
- Affects: Asset Lineage tab in catalog (`AssetsView`) AND Lineage tab inside Asset Detail Page

**3. Responsive ReactFlow panels (≤768px and ≤480px)**
Per user feedback (Image 4-7): Search/filter panel and MiniMap floated awkwardly at smaller viewports.

- `≤768px`:
  - `.alf-lineage-panel` — compact padding 8px, smaller font
  - `.alf-lineage-panel__search` — width 100%, font 12px
  - `.alf-prefix-btn` — compact padding/font for All/ACME pills
  - `.alf-lineage-panel__filter-label` — font 0.7rem
  - MiniMap shrunk to 100×70px (both `.alf-` and `.dag-container .react-flow__minimap`)
- `≤480px`:
  - MiniMap fully hidden — too much real estate on tiny screens
  - Lineage panel padding reduced to 6px
  - Search input capped at max-width 140px

**Compliance:**
- ✅ Principle #1 (No duplication) — no duplicate selectors within any `@media` block (verified)
- ✅ Principle #7 (Verify CSS Module imports per ADR #40) — `AssetDetailModal.module.css` not imported, edits go to global `_modals.css` instead
- ✅ Principle #11 (No stubs) — real implementations, no placeholders/TODOs
- ✅ Rule #1 (No magic numbers) — 0 occurrences of `calc(100v[hw] - Npx)`

**Verification:**
- 323 pytest pass
- cfn-lint clean (0 errors)
- 0 Cyrillic violations
- CSS balance OK (140 braces matched)
- 5 `@media` blocks, no internal duplicates

---

## v70.12 (0.70.12) - 2026-05-02

### Core Principles: New Principle #11 (no stubs/workarounds)

Added Principle #11 to `CLAUDE.md`: **No stubs, mocks, or "make it pass" workarounds in production code.**

Explicitly forbids:
- Returning empty/dummy values when real logic is hard
- Skipping validation, auth, or error handling "for now"
- Disabling/weakening failing test assertions instead of fixing root cause
- Hardcoding values that should come from config/state
- `TODO: implement` next to fake return values shipping to production
- Catching and ignoring exceptions to mask bugs

If something can't be done properly right now — document the gap in the backlog and discuss before shipping. Test mocks (`pytest-mock`, `vi.fn()`) belong in test files only.

### UI: Complete mobile coverage for previously uncovered components (per ADR #40)

Per ADR #40 audit, identified remaining components without mobile rules and added coverage. Followed Rule #7 (verify CSS Module imports before editing) — confirmed 4 components have unimported `.module.css` files (dead code), so all rules went into global `_mobile.css` where actual classes live.

**Components covered (≤768px):**
- `ErrorBoundary` (`eb-*` in `_enhanced-ui.css`) — compact padding, vertical action buttons, smaller title
- `PipelineDetail` error fallback (`pd-error-fallback`) — compact padding, full-width retry button
- `ActionModal` (`am-*` in `_tasks.css`) — smaller textarea font, max-height for run details
- `AllTasksView` / `AllRunsView` filter-bar — title takes full row, controls expand to full width
- `AssetDetailModal` (`adm-*`) — compact body and header padding (was only `max-width: 95vw`)

**Tap targets per ADR #40 rule 4:**
- `.av-nav-item`, `.adp-tab`, `.nav-pill` — `min-height: 36px` on mobile

**Small mobile (≤480px) additions:**
- AssetDetailPage — minimal padding, smaller fonts, smaller tabs
- Filter controls — stack vertically when no horizontal space
- ErrorBoundary — even more compact

**No CSS Module edits made** — all 4 candidate components (`ActionModal`, `ErrorBoundary`, `Notifications`, `AssetDetailModal`) have `.module.css` files but TSX uses plain string class names from global CSS. Per ADR #40 rule 7, those `.module.css` files are dead code and were not touched.

**Verification:**
- `_mobile.css` brace balance OK (132/132), 5 `@media` blocks
- 0 viewport magic numbers
- 0 Cyrillic violations
- 323 pytest pass, cfn-lint clean
- 531/531 vitest expected (no TSX changes — only global CSS)

---

## v70.11 (0.70.11) - 2026-05-02

### UI: Cosmetic fix + ADR completeness

- **`AssetsView.tsx`** — fixed nav label "Lineage Graph Graph" → "Lineage Graph" (typo with duplicated word visible in left sidebar)
- **ADR #40** — extended with rules 6 (definite viewport height at root) and 7 (TSX className strings vs CSS Module imports), plus v0.70.9 + v0.70.10 narrative. Future Claude Code sessions and reviewers now have full context on the responsive layout fixes lineage and the dead-code-edit pitfall to avoid.

No code logic changes beyond the label. All tests pass: 531/531 vitest, 323/16 pytest, tsc 0 errors, cfn-lint 0 errors, 0 Cyrillic violations.

---

## v70.10 (0.70.10) - 2026-05-02

### UI: Complete responsive layout fixes (residual issues from v0.70.8/v0.70.9)

After v0.70.9 fixed root viewport (`.app { height: 100vh }`), several inner containers still didn't propagate height because they lacked `min-height: 0` or used wrong CSS class names. This release walks the entire layout tree systematically.

**AssetDetailPage flex chain (affects ALL 6 tabs):**
- `.adp-body` — added `min-height: 0` (required for flex children with overflow)
- `.adp-main` — added `display: flex; flex-direction: column; min-height: 0` (was static block, children couldn't stretch vertically)
- `.adp-content--lineage` — replaced `height: 100%; min-height: 400px` with `flex: 1; min-height: 400px; display: flex; flex-direction: column` (proper flex behavior, fills available height)

**AssetLineageFlow CSS class mismatch (was silently broken):**
- Discovered `AssetLineageFlow.tsx` uses `className="alf-lineage-flow-container h-full w-full"` (plain string, not CSS Module export). The class is defined globally in `_assets.css`.
- Previous v0.70.8 edit added `width/height/min-height` to `.lineage-flow-container` in `AssetLineageFlow.module.css` — but that class was never used. Dead code edit, no runtime effect.
- Now applied to the actual class `.alf-lineage-flow-container` in `_assets.css`: `width: 100%; height: 100%; min-height: 400px; flex: 1`.

**panel-section (used by AllTasksView, AllRunsView):**
- `.panel-section` had only `grid-column: 1 / -1` — assumed grid parent, but `<main class="main">` is flex column. As flex item without `flex: 1`, panel didn't stretch.
- Added `flex: 1; min-height: 0` to both `_utilities.css` and `shared.module.css` definitions (duplicated in two files).

**Verification:**
- 531/531 vitest tests pass
- 323/16 pytest pass
- 0 TypeScript errors, 0 cfn-lint errors, 0 Cyrillic violations

**Affected views:**
- ✅ AssetsView Catalog tab — Detail Page fills viewport
- ✅ AssetsView Lineage tab — graph fills viewport
- ✅ AssetDetailPage — all 6 tabs (Overview/Schema/Partitions/Events/Checks/Lineage) fill viewport
- ✅ AllTasksView, AllRunsView — content stretches via panel-section
- ✅ PipelineDetail (DAG/Gantt/Calendar) — already correct, verified

---

## v70.9 (0.70.9) - 2026-05-02

### UI: Fix root height chain (resolves residual layout bugs from v0.70.8)

**Root cause:** v0.70.8 fixed downstream symptoms but missed the actual root: `.app { min-height: 100vh }` instead of `height: 100vh`. With `min-height` the viewport has no definite height, so descendant `flex: 1` and `height: 100%` resolve to content size — causing ReactFlow lineage graph to collapse to ~100×100px and AssetDetailPage tabs to clip vertically.

**Changes:**
- `_base.css` — `.app { min-height: 100vh }` → `height: 100vh; overflow: hidden`. The `<body>` keeps `min-height: 100vh` so document scroll still works for non-app content.
- `_layout.css` — `.main { flex: 1; ... }` got `min-height: 0` added so flex children can shrink properly.
- `_assets.css` — removed `grid-template-columns: 330px 1fr` from `.av-assets-view` (was conflicting with `.av-assets-layout: 200px 1fr` since both classes are always applied to the same `<div>`). Now `.av-assets-view` defines only `display: grid; height: 100%`, and column structure comes solely from `.av-assets-layout`.

**Why v0.70.8 fixes alone weren't enough:**
- `.av-catalog flex: 1` correctly requested available height — but parent `.av-main-content` couldn't provide it because `<main>` itself didn't have a definite height to share.
- `.av-lineage-wrapper flex: 1` had the same issue.
- The `.av-main-content > .adp-page` rule was correct but useless until parent height resolved.

**Verification:**
- 531/531 vitest tests pass
- 323/16 pytest pass
- 0 TypeScript errors
- 0 cfn-lint errors
- 0 Cyrillic violations

---

## v70.8 (0.70.8) - 2026-05-02

### UI: Responsive layout fixes (ADR #40)

**Critical layout bugs fixed:**
- `AssetDetailPage` was clipped vertically inside `.av-catalog` scroll container with `max-height: calc(100vh - 180px)` — Detail Page now renders directly in `.av-main-content` flex column, inherits full available height
- Asset Lineage tab graph was confined to a small box due to viewport magic number — replaced with `.av-lineage-wrapper` flex chain
- `BackfillModal` body had `max-height: calc(90vh - 130px)` — replaced with `flex: 1; min-height: 0`

**Eliminated viewport magic numbers (3 sites):**
- `_assets.css` — `.av-catalog`
- `_modals.css` + `BackfillModal.module.css` — modal body
- `AssetsView.tsx` — lineage tab inline Tailwind class

**Mobile coverage added:**
- `AssetDetailPage` — full `adp-*` mobile rules in `_mobile.css` (sidebar collapsed below content, scrollable tabs, compact header/padding, events split → vertical)
- `CommandPalette` — full-width on mobile, hide keyboard shortcuts
- `BackfillModal` — 95vw width, dates 1 column on mobile
- `CalendarView` — compact gaps and font sizes for ≤768px and ≤480px
- `AssetLineageFlow` — desktop baseline `min-height: 400px` (was mobile-only)

**CSS architecture:**
- `.av-main-content > .adp-page` — Detail Page inherits parent height via flex
- `.av-lineage-wrapper` — replaces inline `h-[calc(100vh-180px)]` with proper flex chain
- Per-component `@media` queries used for CSS-Module-scoped components (cannot reach from global `_mobile.css`)

**Documentation:**
- ADR #40: Responsive Layout — codifies flex chain pattern and forbids viewport magic numbers
- `CLAUDE.md` UI Patterns extended with responsive checklist (5 rules + 3 breakpoints)

**Testing:**
- All 323 backend/SDK tests pass
- `cfn-lint sam/template.yaml` — 0 errors
- Version consistency: `pyproject.toml` = `slsflow/__init__.py` = `ui/package.json` = 0.70.8
- UI tests (`vitest`) — must be run by maintainer after pull (CI skips when no SLSFLOW_API_URL)

---

## v70.7 (0.70.7) - 2026-05-02

### CLAUDE.md compliance: Documentation, exceptions, cleanup

**Documentation (Rule #10 — English only):**
- All ADRs translated to English. Files affected: `docs/reference/DESIGN_DECISIONS.md`
- ADR numbering normalized: `## ADR #N` format → `### N.` format (matches existing 1-29 style)
- Resolved duplicate ADR #30 — Asset Enrichment renumbered to #39
- ADRs #32, #33 marked as superseded by ADR #34 (AWS SAM)
- `CHANGELOG.md` v70.5/v70.4/v70.3/v70.2 entries translated to English
- Single Ukrainian line in `docs/reference/BACKLOG.md` translated

**Exception handling (ADR #28):**
- `routes/assets.py` — broad `except Exception` narrowed to `(ClientError, BotoCoreError)` for inner DDB calls (3 sites)
- Top-level catch-all `except Exception` retained (1 per route handler — matches `pipelines_list.py` pattern)
- Silent exception swallowing fixed in `get_queued_events` — now logs `log.warning()` with context
- Import added: `from botocore.exceptions import ClientError, BotoCoreError`

**Cleanup (Rule #1 — No duplication, Rule #7 — Finish what you start):**
- `ASSET_REGISTRY_TABLE` env var removed from `sam/lambdas/console_api/tests/conftest.py` (table was removed in v70.6 per ADR #39)
- Build artifacts excluded from archive: `slsflow.egg-info/`, `ui/next-env.d.ts`, `ui/tsconfig.tsbuildinfo`

**CLAUDE.md (Rule #9 — Docs up to date):**
- Key ADRs table updated: corrected ADR numbers, added #28, #35, #38
- ADR #30 reference replaced with #39 (asset_registry removal)

**Testing:**
- All 323 tests pass (169 SDK + 154 backend)
- `cfn-lint sam/template.yaml` — 0 errors
- Version consistency: `pyproject.toml` = `slsflow/__init__.py` = `ui/package.json` = 0.70.7

---

## v70.6 (0.70.6) - 2026-04-17

### Asset Enrichment: Schema Declaration + Asset Detail Page (ADR #29)

**DSL:**
- `Asset` class: new fields `owner`, `schema`, `glue_table`, `glue_catalog`
- `schema` accepts tuples `(name, type, description)` or dicts, serializes to JSON
- `glue_table`/`glue_catalog` stored as hints for future Glue integration (no API calls)
- `_serialize_schema()` method normalizes both tuple and dict formats
- Full backward compatibility — all new fields optional with empty defaults

**Backend:**
- `list_assets()` API returns new fields: owner, schema, glue_table, glue_catalog
- `get_asset_lineage()` enriched with new fields from pipeline registry and asset registry
- No new endpoints, no new IAM permissions, no new DDB tables

**UI:**
- New `AssetDetailPage` component — full page view with 6 tabs:
  - **Overview**: status, description, tags, lineage summary, latest execution
  - **Schema**: column table (name, type, description), Glue hint badge
  - **Partitions**: timeline bar, date list, per-partition details
  - **Events**: event timeline with metadata, SFN execution info
  - **Checks**: placeholder for future asset checks
  - **Lineage**: embedded AssetLineageFlow with asset focus
- Definition sidebar: group, owner, compute kind, freshness, Glue ref, jobs, actions
- Navigation: click asset in list → detail page, back button returns to list
- New icons: Shield, Table2, Folder, ArrowUpRight, ArrowDownRight, List
- **Catalog tab** on Assets page — table view of all assets (name, group, description, owner, status), replaces Lineage Graph as default tab
- **Focused lineage with depth control** — AssetDetailPage Lineage tab shows only the selected asset's graph with:
  - Scope buttons: Nearest Neighbors / Upstream / Downstream
  - Depth control: +/− buttons and "All" to adjust traversal depth
- 511 lines of CSS (adp-* prefix, CSS variables, light/dark theme support)

**Types:**
- New `AssetSchemaColumn` interface
- `AssetData` extended with owner, description, schema, glue_table, glue_catalog, freshness_hours
- `AssetEvent` extended with metadata field

**Bug fixes — asset_registry table never written to (3 bugs):**
- `list_assets()` returned empty list — now builds from `pipeline_registry` via shared helper
- `delete_asset()` deleted from empty table, asset remained — now deletes `asset_events` data
- `delete_orphaned_assets()` always found 0 orphans — now compares `asset_events` vs `pipeline_registry`
- Extracted `_build_assets_from_pipelines()` shared helper (eliminates ~150 lines duplication)
- `get_asset_lineage()` simplified to use shared helper (removed dead `asset_registry` enrichment)
- `asset_registry` DynamoDB table removed from template.yaml (was never written to)
- `AssetRegistryRepo` class removed from DAL
- `ASSET_REGISTRY_TABLE` config + env vars + IAM removed (8→7 DynamoDB tables)

**Docs:**
- `docs/features/ASSETS.md` — schema declaration, Glue reference, ownership sections
- ADR #29 document

## v70.5 (0.70.5) - 2026-04-10

### Breaking: Pulumi removed — migration to slsflow-deploy

- `slsflow/pulumi.py` — removed
- `docs/deployment/PULUMI.md` — removed
- `tests/sdk/test_registration_provider.py` — removed
- `Pulumi.yaml` removed from all `pipelines/`
- All 6 demo pipelines updated — no `import pulumi`, no `deploy(dag, infra)`
- `slsflow-init` — now generates a CFN-ready template (without Pulumi)
- `slsflow-ai` — generates code without Pulumi boilerplate
- `slsflow/deploy.py` — Pulumi mocking removed (no longer needed)
- `slsflow/validation.py` — Pulumi mocking removed
- Docs — all `pulumi up` replaced with `slsflow-deploy`

**Migration:** replace `pulumi up` with `slsflow-deploy` in pipelines.
Remove from `__main__.py`: `import pulumi`, `from slsflow.pulumi import...`, `deploy(dag, infra)`.

---

## v70.4 (0.70.4) - 2026-04-10

### New: `slsflow-deploy` — CloudFormation pipeline deployment

- `slsflow/deploy.py` — new module, parallel alternative to Pulumi
- `slsflow-deploy` CLI command (entry point in pyproject.toml)
- Generates a CFN template from the DAG (SFN + LogGroup + EventBridge)
- Deploys via `aws cloudformation deploy`
- After deploy, registers the pipeline via SFN (register_only=true)
- Reads config from SSM `/slsflow/{stage}/` — the same source as Pulumi
- Pulumi remains fully functional — both options supported
- `docs/deployment/DEPLOY.md` — documentation

---

## v70.3 (0.70.3) - 2026-04-10

### Tier 1 & Tier 2 deployment polish

- `ui/deploy.sh` now generates `config.js` with real values from CFN outputs
  (API Gateway URL, Cognito User Pool ID, Client ID) — no env vars needed at build time
- Cognito chicken-and-egg fixed — CloudFront URL added to callbacks automatically
- `layout.tsx` loads `config.js` before React (`<script src="/config.js" />`)
- `public/config.js` updated for local dev
- `samconfig.toml.example` simplified — `resolve_s3 = true`, all optional parameters commented out
- Breaking change documented: `NEXT_PUBLIC_API_URL` is no longer needed at build time

---

## v70.2 (0.70.2) - 2026-04-10

### UI: Vercel → S3 + CloudFront

- `next export` static output — UI is now pure static
- S3 + CloudFront in `sam/template.yaml` — deployed together with shared infra
- Removed server-side proxy `app/api/[...path]/route.ts`
- Removed `src/lib/api-server.ts`
- Removed `vercel.json`
- `NEXT_PUBLIC_API_URL` — now points directly to API Gateway (not through a proxy)
- `ui/deploy.sh` — script for uploading UI to S3 + invalidating CloudFront
- Breaking change: `NEXT_PUBLIC_API_URL` now requires a full URL (not `/api`)

---

## v70.1 (0.70.1) - 2026-04-10

### Infrastructure: OpenTofu → AWS SAM + CloudFormation

- Replaced `terraform/` with `sam/template.yaml` — full shared infrastructure as SAM template
- `sam build && sam deploy` replaces `tofu init && tofu apply`
- AWS CloudFormation manages state natively — no S3 backend config needed for infra
- SAM handles Lambda packaging and S3 artifact upload automatically
- `samconfig.toml` replaces `terraform.tfvars` — one file for all parameters
- SSM parameters still written after deploy — Pulumi `from_ssm()` works unchanged
- Removed OpenTofu dependency for shared infra (Pulumi still used for pipelines)

---

## v70.0 (0.70.0) - 2026-04-09

### Infrastructure
- Replaced `from_terraform_state()` with `from_ssm()` — infrastructure ARNs now written to SSM Parameter Store by Terraform automatically after `tofu apply`
- Switched to OpenTofu (`tofu`) — S3 native locking via `use_lockfile = true`, no DynamoDB needed
- Single S3 bucket for both Terraform and Pulumi state
- Added `terraform/modules/slsflow/vercel.tf` — Vercel project and env variables managed by Terraform (optional)
- Terraform `shared/` now structured as a reusable module

### Configuration
- Removed `[tool.slsflow.terraform_state]` section from `pyproject.toml`
- Removed `[tool.slsflow.accounts]` section — use full ARN strings with `STAGE` directly
- Removed `config.arn()` and `config.accounts` — explicit ARNs are more transparent
- Removed `state_bucket` property from `config.py`
- Minimal `pyproject.toml`: only `namespace`, `region`, `roles`

### Breaking Changes
- `from_terraform_state()` removed — replace with `from_ssm(stage=STAGE)`
- `config.arn()` removed — use `f"arn:aws:states:{region}:{account}:stateMachine:myorg-{STAGE}-{name}"`
- `config.accounts` removed — account IDs now hardcoded in ARNs or managed via Terraform

---

## v69.5 (0.69.5) - 2026-02-24

### generators.py: DRY Refactoring + Step Snapshot Coverage (ADR #29)

**Dispatch dict for step state generation:**
`_generate_step_state` (238 lines, 43 if-blocks, 15 returns) → `_STEP_STATE_BUILDERS` dispatch dict + 14 isolated builder functions (5-24 lines each). New step types only need one function + one dict entry.

**Shared wrapper input builder:**
`_build_wrapper_input()` extracts the 15 common fields between `_build_task_branch` and `_build_step_branch`. Task-specific extras (alerts, outlets, wait_for, trigger_rule, etc.) are added by caller. Wrapper protocol changes now require editing one place.

**Asset serialization helpers:**
7 inline patterns (3 different styles) → `_serialize_outlet(asset)` and `_serialize_inlet(asset)`. Consistent `{"name": ..., "uri": ...}` format everywhere.

**Asset iteration helper:**
`_iter_dag_assets(dag)` — shared iteration for `generate_assets_json` (single DAG) and `generate_all_assets` (multi-DAG). Eliminates duplicated `for task in dag.tasks: for asset in task.outlets/inlets` loops.

**Module-level constants:**
- `WRAPPER_STEP_TYPES = frozenset({'lambda', 'glue', 'ecs', 'athena'})` — was defined inline 2x
- `TRACKED_STEP_TYPES = frozenset({'glue', 'ecs', 'athena'})` — was defined inline 2x
- 8 `JSONATA_*` constants (`JSONATA_TOKEN`, `JSONATA_EXECUTION_NAME`, `JSONATA_EXEC_SHORT`, `JSONATA_SKIP_TASKS`, `JSONATA_VARIABLES`, `JSONATA_SFN_ARN`, `JSONATA_NOW`, `JSONATA_PASS_INPUT`) — were scattered as inline strings 2-5x each

**Cleanup:**
- `_find_reachable` and `_iter_dag_assets` — added missing return type annotations (100% type coverage)
- Removed 2 redundant `from .assets import Asset` local imports (already at module level)

### Step-based ASL Snapshot Tests

**27 new tests**, 11 golden files — closes the zero-coverage gap for `_build_step_branch` and `_generate_step_state`:
- Direct steps: Wait, Pass, SNS+SQS, S3, EventBridge+Bedrock, HTTP, DynamoDB (7 golden files)
- Wrapper steps via Step API: LambdaTask, GlueTask, ECSTask+AthenaTask (3 golden files)
- Mixed DAG: 3 Tasks + Wait + SNS + LambdaTask wrapper (1 golden file)
- Structural validation: 8 tests verifying inline vs wrapper execution, dependencies, task_config fields
- Validation errors: 3 tests for direct-step-with-deps, wrapper-depends-on-direct, task-depends-on-direct

Total snapshot tests: 60 (33 Task + 27 Step), 28 golden files.

405 tests collected, 343 passed, 62 skipped.

## v69.4 (0.69.4) - 2026-02-24

### Version Sync

Unified versioning across all packages. `pyproject.toml`, `slsflow/__init__.py`, and `ui/package.json` now share the same version string. CI enforces consistency — version mismatch fails the build.

Previous state: backend at 0.68.1, UI at 47.1.0, CHANGELOG at v69.3.

### CI: Integration Tests + Version Check

- **Integration tests** added to CI pipeline (9 tests, mocked AWS — no credentials needed)
- **Version consistency check** validates `pyproject.toml` = `__init__.py` = `package.json` on every push/PR
- **Makefile**: `make check` now includes `check-versions` target; `make test` includes `test-integration`

### pipelines_list.py: Exception Handling Cleanup

**13 `except Exception` → 1** (route-level catch-all only).

Replaced broad exception catches with specific types:
- **12 → `except (ClientError, BotoCoreError)`** — DynamoDB and Step Functions API calls now catch AWS service errors AND network errors (timeouts, connection refused) but NOT programming bugs (TypeError, AttributeError)
- **1 kept as `except Exception`** — `get_pipeline_executions` top-level handler (correct: route-level catch-all returns 500)

Silent exception swallowing fixed:
- `_reconcile_running`: `except Exception:` (no `as e`, no logging) → `except ClientError as e:` with `log.warning()`
- `get_pipeline_status` reconciliation: added inline comments explaining why `pass` is correct behavior

Import added: `from botocore.exceptions import ClientError, BotoCoreError` (matches existing pattern in `tasks.py`).

All 448 tests pass (45 console_api + 153 SDK + 154 backend + 9 integration + 56 evaluate_deps + 12 notify + 19 check_assets).

### generators.py: Decomposition (520 → 88 lines)

Extracted 4 private functions from `generate_step_function_json`:

- **`_build_task_branch(task, dag, wrapper_arn)`** (174 lines) — builds a single parallel branch for a Task (wrapper-based execution with dependency resolution, alerts, task_config per type)
- **`_build_step_branch(step, dag, wrapper_arn)`** (117 lines) — builds a single parallel branch for a Step (wrapper or direct mode)
- **`_build_pipeline_metadata(dag)`** (59 lines) — pure data transformation producing tasks_metadata, dag_metadata, asset_schedule
- **`_build_registration_chain(dag, ...)`** (143 lines) — builds Define_Inputs → Register_Pipeline → Save_DAG_Snapshot → Register_Asset_Subscriptions → Check_Register_Only state chain

`generate_step_function_json` is now an 88-line orchestrator (62 lines body + 26 lines docstring) with 5 clear steps: build branches → build metadata → build registration → add parallel execution → assemble definition.

33/33 ASL snapshot tests pass without `SNAPSHOT_UPDATE` — zero diff in generated JSON.

## v69.3 (0.69.3) - 2026-02-24

### Console API: Complete DAL Migration (ADR #25)

**55 direct DynamoDB bypasses → 0** across all 10 route files. Every `table.get_item()`, `table.query()`, `table.update_item()`, `table.put_item()`, `table.delete_item()` replaced with repository methods.

- **notifications.py** (1) — paginated failure query → `executions_repo.query_by_date_raw()`
- **health.py** (2) — `_check_recent_failures` + `get_metrics` → `query_by_date_raw()`, `query_by_date()`
- **slack.py** (4) — all 4 Slack action handlers → `executions_repo.get()` + `update()`
- **tasks.py** (6) — `resolve_task_item()` signature changed (removed `table` param), all callers updated
- **backfill.py** (6) — `pipelines_repo.get()`, `queued_events_repo.put()`, `asset_subscriptions_repo.query_by_asset()`
- **executions.py** (8) — `_mark_pending_tasks_stopped` → `query_by_pipeline_execution()` + `update()`, pause/resume flows
- **pipelines_list.py** (5) — `_query_pipeline_by_date_range` + `_reconcile_running` signatures cleaned (removed `tokens_table`)
- **pipelines_actions.py** (4) — `register_pipeline` → `pipelines_repo.put()`
- **pipelines_info.py** (4) — confirmed clean
- **assets.py** (15) — `get_consecutive_progress` → `asset_events_repo.query_by_asset()`

**DAL fix:** `asset_registry_repo.list_all()` now accepts `**kwargs` for `FilterExpression` passthrough.

**Cleanup:** Removed unused `scan_all`, `query_all`, `Key` imports from all migrated files.

**Docs updated:** `CLAUDE.md`, `console_api/README.md`, `DESIGN_DECISIONS.md` (ADR #25), `CHANGELOG.md`.

Exception: `health.py` circuit_breaker table — separate monitoring table, no repo needed.

**Removed:** `decorators.py` (152 lines, 0 imports). `with_dynamodb_retry`, `with_error_context`, `log_execution_time` — never used. boto3 legacy mode already provides 5 retries with exponential backoff for all DDB throttling errors; all tables are on-demand (PAY_PER_REQUEST). If stronger retry needed in future, use `botocore.Config(retries=...)` in `config.py`.

**Removed:** `asset_watcher` Lambda + Terraform resources (5 AWS resources: Lambda, IAM role, IAM policy, CloudWatch log group, archive). Never activated — no SQS queue, no event source mapping, no EventBridge rule. External systems can trigger assets via existing `POST /api/asset/{name}/trigger` endpoint which flows through the same `notify_asset_consumers` SFN. Lambda count: 7 → 5 (asset_trigger removed in v55, asset_watcher removed now).

### Backend Tests: Fix + Expand (Improvement Plan Step 5)

**Migrated all tests to pytest-mock** (`mocker` fixture). Project-wide standard: `pytest-mock>=3.0.0` (ADR #26). 12 test files migrated from `unittest.mock` → `mocker.patch()`, `mocker.MagicMock()`. Benefits: auto-cleanup via fixture lifecycle, no `with` blocks or decorator stacks, consistent style across all 448 tests.

Exceptions: `slsflow/validation.py` (runtime Pulumi module spoofing), `test_registration_provider.py` (`sys.modules` bootstrap).

**Fixed 30 broken tests** caused by DAL migration (v69.3) and pipelines split (v69.2):

- `test_api_routes.py` (24 tests) — replaced `MockTable`+`MockRepo` with unified `MockRepo` supporting all DAL methods (`list_all`, `scan_raw`, `query_by_date`, `query_by_pipeline_execution`), updated patch targets from `routes.pipelines.` to `routes.pipelines_list.`/`routes.pipelines_info.`
- `test_idempotency.py` (6 tests) — fixed mock targets: `repo.table.update_item()` → `repo.update()`, proper `ClientError` propagation through DAL layer. Added 2 new happy-path tests (fail_task).
- `test_smoke.py` (2 tests) — updated file path `routes/pipelines.py` → `routes/pipelines_list.py`

**Added 21 new tests** for previously untested critical functions:

- `test_resolve_task.py` (6 tests) — `resolve_task_item()`: direct primary key hit, GSI fallback on miss, most recent selection, pipeline_execution filter, not-found, GSI pagination across empty pages
- `test_stop_restart.py` (8 tests) — `stop_task()`: running→stopped, waiting→aborted with callback+notify, terminal→409, not-found→404. `restart_task()`: terminal+helper→SFN start, non-terminal→409, not-found→404, fallback status reset
- `test_query_subscriptions.py` (7 tests) — `query_subscriptions` Lambda: happy path, missing fields (graceful), no subscribers, DDB pagination, DDB error handling. Fixed module-level `boto3.resource` caching via `patch.object()`

**Test count:** 316 passed, 0 failed (was: 286 passed, 30 failed)

Files changed: `dal/assets_repo.py`, `routes/notifications.py`, `routes/health.py`, `routes/slack.py`, `routes/tasks.py`, `routes/backfill.py`, `routes/executions.py`, `routes/pipelines_list.py`, `routes/pipelines_actions.py`, `routes/pipelines_info.py`, `routes/assets.py`, `CLAUDE.md`, `console_api/README.md`, `docs/reference/DESIGN_DECISIONS.md`, `CHANGELOG.md`, `terraform/shared/main.tf`, `terraform/shared/outputs.tf`, `docs/architecture/BACKEND.md`, `docs/reference/BACKLOG.md`, `docs/deployment/TERRAFORM.md`, `docs/operations/TROUBLESHOOTING.md`, `README.md`

Files removed: `decorators.py`, `lambdas/asset_watcher/index.py`

## v69.2 (0.69.2) - 2026-02-24

### Console API: Split pipelines.py into focused modules

`pipelines.py` (1,246 lines) → 3 files:
- `pipelines_list.py` (630 lines) — `list_pipelines`, `get_pipeline_status`, `get_pipeline_executions` + helpers
- `pipelines_actions.py` (295 lines) — `register_pipeline`, `run_pipeline`, `toggle_pipeline_pause`, `restart_pipeline`
- `pipelines_info.py` (349 lines) — `get_pipeline_metrics`, `get_pipeline_dag`, `get_pipeline_logs`

Updated: `routes/__init__.py`, `test_api_routes.py` (19 patch targets), `console_api/README.md`.
No functional changes. 133/133 backend tests pass.

Files changed: `routes/pipelines_list.py`, `routes/pipelines_actions.py`, `routes/pipelines_info.py`, `routes/__init__.py`, `tests/backend/test_api_routes.py`, `console_api/README.md`, `CHANGELOG.md`

Files removed: `routes/pipelines.py`

## v69.1 (0.69.1) - 2026-02-20

### Remove Legacy Deployment Providers

**EventBridge auto-registration removed:**
- `auto_registration.tf` (319 lines, 14 AWS resources)
- `lambdas/extract_sfn_metadata/` (110 lines)
- `sfn_templates/helpers/register_on_create/` (213 lines)

**Terraform/CloudFormation pipeline providers removed:**
- `slsflow/terraform.py` (495 lines) — `generate()` for full TF project
- `slsflow/cloudformation.py` (239 lines) — `generate()` for CFN/SAM templates
- `generators.py`: `generate_terraform()` (276 lines), `generate_cloudformation()` (249 lines), `generate_terraform_vars()` (43 lines)
- CLI flags: `--terraform`, `--cloudformation`, `--cfn`, `--sam`, `--vars`
- `slsflow-init`: `--terraform`, `--cfn` scaffolding templates
- AI assistant: `/iac` command, `--iac` flag (now Pulumi-only)

**Total removed:** ~1,900 lines code, 14 AWS resources. All pipelines deploy via Pulumi.

## v69 (0.69.0) - 2026-02-20

### DAG Snapshot Versioning

Each execution now snapshots its DAG structure to DynamoDB (`tokens_table`) at start time. When viewing old executions in the UI, the correct graph is shown — even after the pipeline definition changed in a later deploy.

- New `Save_DAG_Snapshot` state in generated ASL, chained after `Register_Pipeline`
- Snapshot key: `dag_snapshot::{execution_name}`, TTL: 120 days (matches AWS SFN history retention + buffer)
- API lookup priority: snapshot → registry → inferred from task data
- Response includes `dag_source` field: `'snapshot'` | `'registry'` | `'inferred'`
- New `generate_dag_hash()` utility — deterministic 8-char SHA256 of DAG structure

Files changed: `slsflow/generators.py`, `terraform/shared/lambdas/console_api/routes/pipelines.py`, `terraform/shared/outputs.tf`

### Pulumi Dynamic Provider for Pipeline Registration

Replaced implicit EventBridge-based registration with explicit Pulumi lifecycle management via `PipelineRegistration` dynamic resource:

- **Create**: `pulumi up` (new pipeline) → runs `StartExecution(register_only=true)` immediately (0 latency vs 1-15 min CloudTrail delay)
- **Diff**: compares `dag_hash` — skips re-registration when DAG unchanged
- **Update**: `pulumi up` (changed DAG) → re-registers with new structure
- **Delete**: `pulumi destroy` → cleans `pipeline_registry` + `asset_subscriptions` from DynamoDB (no more zombie pipelines in UI)

New Pulumi exports after `pulumi up`: `{dag_id}_registered`, `{dag_id}_dag_hash`, `{dag_id}_tasks`, `{dag_id}_assets`, `{dag_id}_group`

Files changed: `slsflow/pulumi.py`

### UI: "Stop Task" Terminology Fix

Renamed "Pause Task" → "Stop Task" to distinguish from pipeline-level "Pause Pipeline". Task stop kills the execution; pipeline pause holds the queue. Previously both used "Pause" terminology which caused confusion.

- Button: StopCircle icon + "Stop Task" label
- Confirmation dialog: "Stop Task" title with amber icon

Files changed: `ui/src/components/TaskDetailModal.jsx`, `ui/src/hooks/usePipelineActions.jsx`

### Tests

- 11 new tests for Dynamic Provider (create, diff, update, delete edge cases)
- 6 new tests for DAG snapshots (TTL, hash determinism, API lookup priority)
- 17 ASL snapshot files regenerated (include Save_DAG_Snapshot state)
- Total: 640 tests passing (291 SDK+backend, 349 UI)

## v68.1 (0.68.1) - 2026-02-19

### Idempotency Hardening

Three categories of fixes to prevent duplicate operations from retries, double-clicks, and race conditions:

- **`name=` on all `start_execution` calls**: Pipeline start/restart, task restart (UI+Slack), notify_dependents helper, PagerDuty resolver, CLI local run, and CLI register now use named executions. Duplicate calls return 409 instead of creating parallel executions.
- **Claim-before-side-effects ordering**: All 7 manual action handlers (4 UI + 3 Slack: skip, fail, mark_success, stop) now acquire the DynamoDB conditional update *before* stopping executions or recording events. If the claim fails (race condition), no side-effects execute.
- **Deterministic timeline event keys**: `record_manual_decision()` now uses `hashlib.md5(execution_name+decision)` suffix instead of `uuid4()`, so retries overwrite the same event item instead of creating duplicates.
- **UI action debounce**: Modal confirm button shows "Working…" and disables during API calls. Cancel and close also blocked while pending. Prevents double-click on Run Pipeline, Restart, Skip, Fail, Mark Success, Stop.

Files changed: `routes/pipelines.py`, `routes/tasks.py`, `routes/slack.py`, `task_actions.py`, `utils.py`, `slsflow/local.py`, `slsflow/register.py`, `ui/src/hooks/usePipelineActions.jsx`, `ui/src/components/Modal.jsx`, `ui/src/App.jsx`, `ui/src/contexts/AppContext.jsx`

## v68 (0.68.0) - 2026-02-19

### Asset.consecutive() — Cross-Pipeline Date Dependencies

New `consecutive(days=N)` method on Asset for wait_for dependencies.
Checks that asset has events for N consecutive dates ending at the pipeline's current_date.

```python
# Weekly waits for 7 daily completions
wait_for=[daily_complete.consecutive(days=7)]
```

Supports full operator set: `|` (OR), `&` (AND), list (AND).

### Reliability Fixes

- **date field revert**: `date` in task input now uses `current_date` fallback chain instead of `$now()`, preventing midnight crossing issues with dependency keys
- **Dynamic wrapper TTL**: subscription TTL now `max(orchestration_timeout, 30d) + 1d` instead of hardcoded 30d, supporting monthly/yearly pipelines
- **Asset events TTL**: 90 days → 365 days for historical event retention
- **Manual event TTL**: 30 days → 365 days
- **IAM fix**: `notify_asset_subscribers` lambda now has `dynamodb:Query` permission on `asset_events` table (required for consecutive re-check)

### Infrastructure

- `current_date` passthrough: dependency_wrapper → registration → check_assets lambda
- New `_check_asset_consecutive()` in check_assets lambda
- New `_check_consecutive_ready()` in notify_asset_subscribers lambda

## v67 (0.67.0) - 2026-02-19

### Sidebar: Schedule Display

Pipeline cards in the sidebar now show the cron/rate schedule after the status.
Human-readable formatting converts AWS expressions to concise labels:
- `cron(0 8 * * ? *)` → `daily @ 08:00`
- `cron(0 10 ? * MON *)` → `Mon @ 10:00`
- `rate(6 hours)` → `every 6h`

**Backend:** `schedule` field added to `Register_Pipeline` DynamoDB putItem in generators.py.
`list_pipelines` now reads and returns `schedule` from the pipeline registry.

> **Note:** Schedule appears in sidebar only after pipelines are re-deployed (so the registry
> gets the new `schedule` field). Existing pipelines show no schedule until next deploy/run.

### Sidebar: Run Sparkline

Pipeline cards show a mini bar chart of the last 10 runs (green = success,
red = failed, blue pulsing = running). Oldest on the left, newest on the right.
In-progress runs are included so the sparkline is never empty while a pipeline runs.

**Backend:** `list_pipelines` now returns `recent_runs` array (last 10 runs
with date + status). Built from the same SLA data — zero additional DynamoDB queries.

### Removed Dead Progress Bar

The `pipeline-progress` bar in sidebar cards was never populated (backend returned
`progress: null` for the sidebar endpoint). Replaced with the sparkline above.

### Deleted Legacy main.css (4,903 lines)

`main.css` was the original monolithic stylesheet before the modular CSS migration.
It was not imported anywhere — all styles load through `index.css → modules/`. Deleted.

During audit, discovered 7 `api-*` classes used by HelpModal (expandable endpoint details,
copy block, response preview) were lost during the original migration to modules. These have
been restored in `_tasks.css` alongside the existing API documentation styles.

Stale comment in `globals.css` referencing `main.css` updated to point to `_base.css`.

### CSS Deduplication (18 → 3 duplicates)

Deduplicated class definitions across CSS modules, merging properties before removing.
Remaining 3 are intentionally complementary (`.card`, `.animated-edge-path`, `.sidebar`).
Key merges: `.empty-state` → `_utilities`, `.skeleton` → `_enhanced-ui`,
`.metadata-*` → `_assets`, `.error-boundary-*` → `_enhanced-ui`,
`.lineage-legend` → `_enhanced-ui`, `.duration-stats` → `_utilities`.

### Defined `--font-mono` CSS Variable

`var(--font-mono)` was used in 10+ places but never declared (silently fell back to
browser default `monospace`). Added `--font-mono: 'JetBrains Mono', monospace` to
`:root` in `_base.css` and normalized all 11 hardcoded `'JetBrains Mono', monospace`
references to use the variable.

## v66 (0.66.0) - 2026-02-18

### Backfill Failure Handling: Wait for Decision Instead of Auto-Fail

**Change:** When a task fails during backfill, the system now waits for user decision via UI
(skip/fail/restart) instead of immediately auto-failing. Slack and PagerDuty notifications
remain suppressed during backfill to avoid noise.

**Before:** `Check_Is_Backfill → Save_Failed` (task auto-failed, no way to restart from UI)
**After:** `Check_Is_Backfill → Wait_For_Decision` (5h window, user can act via UI)

### Canonical Output Fix: Missing Fields

**Bug fix:** `Save_Canonical_Output` was missing `task_name` and `status` fields.
`Read_Upstream_Outputs` reads these fields, so downstream tasks received `status: 'unknown'`
instead of `status: 'success'` for upstream outputs.

### Upstream Output Payload Protection

**Safety:** Added per-dependency output truncation at read time (25KB limit per dep) in
`Read_Upstream_Outputs`. Canonical record keeps full output (up to 200KB), but when reading
for downstream, each dep is capped to prevent exceeding Step Functions' 256KB payload limit.
Even with 10 dependencies, total stays under 250KB + overhead = safe.

### Fix: Upstream Outputs Not Passed to Child Tasks

**Bug fix:** `Read_Upstream_Outputs` correctly read dependency outputs into `upstream` map,
but `Run_Task_SFN` and `Run_Task_Lambda` never included `upstream` in the child task input.
Child tasks received only `current_date`, `PARTITION_ARG`, and `variables` — never upstream data.

**Fix:** Added `upstream` to `$merge()` in both `Run_Task_SFN.Input` and `Run_Task_Lambda.Payload`.
Only included when non-empty (`$count($keys(...)) > 0`) to avoid noise for tasks without deps.

### Computed Date Variables for All Runs

**Improvement:** `Prepare_Task_Input` now computes the full set of date variables from `current_date`
for every run — not just backfill. Child tasks now always receive: `date_compact`, `date_slash`,
`year`, `month`, `day`, `day_of_week`, `previous_date`, `next_date`, `minus_7_days`, `minus_14_days`,
`minus_30_days`, and `ALLOW_UNSUCCESSFUL_SPIDER_RUN`.

Previously these were only available during backfill (computed in Python). Now JSONata computes them
in the run_task helper so normal scheduled runs get the same variables. Backfill values take priority
via merge order (`$merge([$dateVars, $vars])` — user/backfill vars override computed).

**Note:** `minus_1_month`, `minus_3_months`, `day_of_year`, `week_of_year` require complex calendar
math and are only available during backfill (Python). For normal runs, use `minus_30_days` as approximation.

**Single source of truth:** Date variables are computed once by JSONata in `Prepare_Task_Input`.
Backfill.py only provides `current_date` (to drive JSONata) plus what JSONata cannot compute:
`minus_1_month`, `minus_3_months`, `day_of_year`, `week_of_year`, and flags (`is_backfill`, `is_reprocess`).
No duplication between Python and JSONata.

**Files changed:**
- `terraform/shared/sfn_templates/helpers/run_task/sfn.tpl.json`
- `tests/test_alerting.py` (7 new/updated tests)
- `docs/architecture/ARCHITECTURE.md`
- `docs/operations/UI.md`
- `docs/reference/AIRFLOW_MIGRATION.md`

## v65 (0.65.0) - 2026-02-18

### PagerDuty Auto-Resolve on Human Decisions

**Bug fix:** When a user clicked Skip/Fail in Slack or UI, the PagerDuty incident stayed open
and continued escalating — waking up the next person in the on-call chain even though a human
had already acknowledged the issue and made a decision.

**Root cause:** PD resolve only existed in the wrapper SUCCESS path (task recovered). The failure
path (Skip/Fail/timeout) never resolved PD. We initially tried adding resolve to failure_handler
SFN template, but discovered that Slack/UI actions kill the wrapper via `stop_execution()` —
failure_handler never runs for human decisions. It only runs on 5h timeout (nobody responded),
where resolve is explicitly NOT wanted.

**Fix:** Added `resolve_pagerduty()` utility in Lambda API handlers where decisions are made:
- `slack.py`: slack_action_skip, slack_action_fail, slack_action_success
- `tasks.py`: skip_task, fail_task, mark_success
- Non-blocking (try/except) — if PD is unreachable, Skip/Fail still works
- Checks `alerts_json` in DDB to skip pipelines without PD configured

**PD resolve behavior by scenario:**
| Scenario | Who resolves | PD result |
|---|---|---|
| Skip/Fail/Success (Slack or UI) | Lambda API | ✅ Resolved |
| Restart → task succeeds | Wrapper SFN | ✅ Resolved |
| 5h timeout (nobody responded) | Nobody | ✅ Open → escalation continues |
| Restart → task fails again | Nobody | ✅ Open → new alert (same dedup_key) |

### PagerDuty Alerter — Clickable Links

PD incidents now include direct links to AWS Step Functions console:
- Task SFN execution link (the actual task that failed)
- Wrapper SFN execution link (the orchestration wrapper)
- Links appear as clickable buttons in PagerDuty incident view
- Empty ARNs handled gracefully (links omitted)

### Notify Dependents Date Bug Fix

**Root cause**: When a task from a cross-date pipeline (e.g., weekly→daily where daily runs on a different day),
UI actions (Skip/Fail/Mark_Success) passed the UI date picker date to `notify_dependents_via_sfn` instead of
the DDB record date. The SFN helper then built the wrong DDB key (`task-2026-02-18-...` vs `task-2026-02-16-...`),
found no record, and silently skipped the notification → downstream tasks hung forever.

**Fix**: All 4 task action handlers in `tasks.py` now use `item.get('date', date)` — the DDB record date (source of truth).
Slack handlers (`slack.py`) already used `item.get('date')` and were not affected.
Files: `terraform/shared/lambdas/console_api/routes/tasks.py` (4 lines changed)

### Cross-Pipeline Navigation

When a task runs a child pipeline (e.g., weekly→daily), the task modal now shows:
- **"Child Pipeline"** field with clickable link → navigates directly to that pipeline with correct date
- Detection: matches `task_arn` in DDB against registered pipeline ARNs
- Backend: `task_arn` and `task_type` now stored in DDB via `Update_Status_Running`
- Files: `run_task/sfn.tpl.json`, `ui/src/App.jsx`, `ui/src/components/TaskDetailModal.jsx`

### Dependency Status Visibility in Task Modal

When a task is in `waiting` state, the Dependencies section now shows:
- Status of each dependency (success ✓, failed ✗, waiting ⏳)
- Color-coded left border (green=ready, red=blocked, gray=waiting)
- Summary: "3/12 ready" or "⚠ Blocked: 1 dep incompatible with all_success"
- Trigger rule explanation when deps are blocked
- Files: `ui/src/components/TaskDetailModal.jsx`, `ui/src/App.jsx`
- Zero backend changes

### PagerDuty Clickable Links — Fix

Links were empty because ARNs weren't available on failure path:
- **wrapper_execution_arn**: Added to Wrapper `Prepare_Inputs` (passes `$states.context.Execution.Id` through to run_task)
- **task_execution_arn**: All 7 task runner Catch outputs now extract `ExecutionArn` from `error.Cause` JSON (sync:2 format)
- **UI console link**: Added `SLSFlow Console` link to PD alerts (uses `console_url_override` / Vercel URL)
  - URL format: `{ui_url}/?pipeline={name}&task={name}&date={date}`
  - Conditional: omitted if `console_url_override` not set
- Zero additional state transitions — all changes in existing Pass/Catch outputs

### Cost Optimization

Converted `sf_pagerduty_alerter` and `sf_pagerduty_resolver` from Standard to Express SFN.
Both are simple HTTP POST workflows (~5 states) — Express pricing is ~10x cheaper.

### Files Changed
- `terraform/shared/lambdas/console_api/utils.py` — `resolve_pagerduty()` function
- `terraform/shared/lambdas/console_api/routes/slack.py` — 3 resolve calls
- `terraform/shared/lambdas/console_api/routes/tasks.py` — 3 resolve calls
- `terraform/shared/console.tf` — PAGERDUTY_RESOLVER_ARN env var
- `terraform/shared/sfn_templates/helpers/pagerduty_alerter/sfn.tpl.json` — links in payload
- `terraform/shared/sfn_templates/helpers/run_task/sfn.tpl.json` — ARNs to alerter + Catch extracts task_execution_arn
- `terraform/shared/sfn_templates/dependency_wrapper/sfn.tpl.json` — wrapper_execution_arn in Prepare_Inputs
- `terraform/shared/main.tf` — Express type for alerter+resolver, aws_region + ui_url for alerter
- `tests/test_alerting.py` — updated test class for failure_handler
- `docs/architecture/ARCHITECTURE.md` — PD resolve docs
- `docs/architecture/BACKEND.md` — sf_pagerduty_resolver updated

## v64 (0.64.0) - 2026-02-17

### Alerting Architecture Redesign

**PagerDuty moved to first line (run_task helper):**
- PagerDuty alert fires immediately when task fails, not after 5h timeout
- On-call engineer can act during the 5h decision window (Skip/Restart/Fail via Slack or UI)
- PagerDuty removed from failure_handler (no duplicate alert)
- Auto-resolve on success path still works via wrapper's Resolve_PagerDuty

**Backfill alert suppression:**
- Backfill runs (`variables.is_backfill=true`) skip Interactive Slack, PagerDuty, and 5h wait
- Tasks auto-fail immediately — results visible in UI calendar view
- Eliminates alert storms (was: 30 dates × N failures = hundreds of alerts)

**Conditional Slack in run_task:**
- `Check_Has_Slack` gate before Interactive Slack — only fires if `alerts.slack` configured
- Previously: Interactive Slack always fired, failed through error handling when unconfigured

**upstream_failed alert suppression:**
- failure_handler checks `error.Error = 'UpstreamFailed'` — skips Slack for cascade failures
- Only root cause task sends alerts; downstream tasks fail silently
- Eliminates N×alerts per cascade (was: 1 root + N downstream alerts)

**No buttons on dead tasks:**
- failure_handler sends empty token to Interactive Slack → "Restart Only" message
- Previously: second Slack message had Skip/Fail buttons that returned "Already Terminal"

**alerts config persistence for restart:**
- `alerts_json` field stored in DynamoDB during Update_Status_Running
- restart_task helper reads `alerts_json` from DDB and passes to new wrapper
- Previously: restarted tasks had no alerts config → failure_handler was silent

**Terraform wiring:**
- `pagerduty_alerter_arn` added to sf_run_task_helper module
- `pagerduty_alerter_arn` removed from sf_failure_handler module

### Files Changed
- `terraform/shared/sfn_templates/helpers/run_task/sfn.tpl.json` — +4 states, slack_mentions passthrough
- `terraform/shared/sfn_templates/helpers/failure_handler/sfn.tpl.json` — -2 states, slack_mentions passthrough
- `terraform/shared/sfn_templates/helpers/restart_task/sfn.tpl.json` — +1 input field
- `terraform/shared/sfn_templates/helpers/interactive_choice_slack/sfn.tpl.json` — dynamic CC mentions
- `terraform/shared/main.tf` — module wiring, default_slack_mentions
- `terraform/shared/variables.tf` — default_slack_mentions variable
- `slsflow/dag.py` — slack_mentions validation
- `slsflow/generators.py` — slack_mentions formatting at compile time
- `tests/test_alerting.py` — 74 tests
- `docs/architecture/ARCHITECTURE.md` — updated failure flow diagrams
- `docs/features/DSL.md` — slack_mentions documentation
- `CHANGELOG.md` — v64 entry

### Test Coverage
- 235 passed, 18 skipped (was 161 passed)
- 74 alerting-specific tests covering flow structure, DDB persistence,
  cross-template consistency, path tracing, and slack_mentions

### Slack Mentions

**Per-pipeline mention tagging in alerts:**
```python
alerts={
    "slack": "#data-alerts",
    "slack_mentions": ["YOUR_SLACK_USER_ID", "S04ABCDEF", "here"]
}
```

- User IDs (`U...`), user group IDs (`S...`), `here`, `channel` supported
- Converted to Slack format at compile time: `<@U...>`, `<!subteam^S...>`, `<!here>`
- Fallback to `default_slack_mentions` Terraform variable if not specified
- Replaces hardcoded `responsible_for_data_pipeline_ops` with configurable per-pipeline + default
- Flows through: generators.py → wrapper → run_task → Interactive Slack CC line
- Also flows through: wrapper → failure_handler → Send_Slack_Alert CC line

## v55.2 (0.55.2) - 2026-02-16

### Changed
- **notify_dependents helper → Express workflow**
  - Switched from Standard to Express Step Functions type
  - No logic changes — same ASL, same Lambda/DynamoDB calls
  - Added CloudWatch Logs logging (level: ALL, include_execution_data: true)
  - Callers keep `startExecution.sync:2` (AWS handles Express target automatically)
  - Cost: ~$1.50/mo vs $12/mo Standard for 60K tasks/mo (M=1)

- **notify_asset_consumers helper → Express workflow**
  - Same migration as above — DynamoDB ops + fire-and-forget startExecution
  - Added CloudWatch Logs logging for execution history visibility

- **step-function module: logging_configuration support**
  - New optional `logging_configuration` variable (log_group_arn, level, include_execution_data)
  - Dynamic block — only added when configured, no impact on existing Standard SFNs

- **IAM: added `logs:DeleteLogDelivery`**
  - Required for clean `terraform destroy` of Express SFN log delivery
  - Previously missing (comment said "NO Delete*")

### Not Changed
- **failure_handler stays Standard** — calls slack_alerter, pagerduty_alerter, notify_dependents via `.sync:2` (Express can't use `.sync` pattern)
- **dependency_wrapper stays Standard** — uses `waitForTaskToken` for dependency waiting
- **registration, run_task, pause_waiter stay Standard** — use `.sync` or `waitForTaskToken`

### Cost Impact
- 60K tasks/mo (D=1, M=1): ~$10.50/mo savings on notify_dependents
- Scales linearly: M=3 → ~$35/mo savings
- notify_asset_consumers: additional savings proportional to asset-triggered pipelines

## v55.1 (0.55.1) - 2026-02-10

### Added
- **Configurable orchestration_timeout** for dependency wait time
  - New `orchestration_timeout` param on `@task.sfn()`, `@task.lambda_()`, etc.
  - Default: same as `execution_timeout` (24h)
  - Wrapper template uses dynamic Timeout from input (was hardcoded 7 days)
  - Usage: `@task.sfn(orchestration_timeout=timedelta(days=3))`

- **Backfill max_parallel with staggered start**
  - When `max_parallel > 0`, starts are staggered in batches with 2s pause
  - Throttling errors retried once with backoff
  - ExecutionAlreadyExists handled gracefully
  - Protects downstream service limits (Glue concurrency, Lambda throttling)

- **Slack notification failure visibility**
  - When Slack alert fails (invalid channel, webhook error), records `notification_failed` on task
  - DAG view shows ⚠️ icon on affected tasks
  - Task detail modal shows warning banner with guidance to use UI actions
  - Failure handler continues gracefully to PagerDuty and orchestration token

### Fixed (Resilience)
- **Handle_Failure in dependency_wrapper now has Catch clause**
  - If failure_handler SFN itself fails, wrapper gracefully proceeds to Fail_State
  - Previously: wrapper would fail, pipeline waits until TimeoutSeconds (24h)

- **All dependency_wrapper Task states now have Catch**
  - Emit_Wrapper_Started, Emit_Deps_Ready, Emit_Deps_Blocked: continue on EventBridge failure
  - Auto_Skip_Register, Update_Status_Waiting_Delay: continue on DDB failure
  - Previously: any observability emit failure would crash the entire wrapper

- **Update_Status_Failed in failure_handler has Catch**
  - If DDB status update fails, notifications still proceed

- **Read_Upstream_Outputs Map in run_task has Catch**
  - If reading upstream outputs fails, task execution continues

- **Query_Subscriptions in notify_asset_consumers has Retry + Catch**
  - DDB query retries on throttling (3 attempts, exponential backoff)
  - On persistent failure: treats as no subscribers, continues gracefully

- **restart_task: race condition protection**
  - Added terminal status validation (only terminal tasks can restart)
  - Fallback path uses ConditionExpression to prevent double-restart
  - Returns 409 Conflict on invalid state transitions

- **notify_dependents_via_sfn: return value checked**
  - All 7 callers (4 in tasks.py, 3 in slack.py) now log warnings on failure
  - Previously: silent failures could orphan dependent tasks

- **Bounded all DynamoDB scans** (16 unbounded → 0)
  - All scan_all() calls now have max_items limits
  - Registry/asset tables: MAX_SCAN_ITEMS (50K)
  - Tokens table: MAX_FETCH_ITEMS (10K)
  - Health checks: Limit=100

### Fixed (Code Quality)
- **local.py dependency validation handles Step objects**
  - Uses getattr for task_id/step_id to handle both Task and Step types
  - Previously: AttributeError when Step (Wait, Pass, Choice) in dependency chain

- **Version sync**: `__init__.py` matched to `pyproject.toml` (0.36.78)

### Improved (CI/DX)
- **Makefile**: `make test` includes test-ui; `smoke-pipelines` + `sync-constants` added; `lint` validates JSON templates
- **CI**: trigger rules sync test, pipeline import check, Lambda unit tests, constants sync, deeper Lambda syntax checking
- **Standardization**: Replaced manual pagination loop in pipelines.py list_pipelines with scan_all()

### Refactored (Code Quality)
- **main.py route dispatch**: if/elif chain (320 lines) → route table (153 lines, 48 routes)
- **api.js**: 4 duplicate HTTP methods → shared `_request()` base (299 → 223 lines)
- **run_task SFN**: Added Catch to all 8 DDB states (best-effort status updates don't block execution)
- **run_task SFN**: Added Retry to Send_Pipeline_Success/Failure callbacks

### Removed
- **pipelines/acme/**: Broken example pipelines (pulumi import, bare @task(), missing alerts)
- **pipelines/acme-full/**: Same issues

### Remaining
- ~~`@with_dynamodb_retry` decorator~~ — Removed in v69.3. boto3 legacy mode already provides 5 retries with backoff; on-demand tables don't throttle at current load.

## v55 - 2026-01-29

### Changed (Architecture)
- **EventBridge → Step Functions migration for asset triggers**
  - Replaced `asset_trigger` Lambda + EventBridge rule with `notify_asset_consumers` SFN helper
  - All asset trigger logic now visible in Step Functions console (transparent orchestration)
  - Removed 774 lines of Lambda code, replaced with ~250 lines SFN definition
  - No more "black box" EventBridge flows - easier debugging

- **Cross-account roles now single source of truth**
  - Roles defined in `pyproject.toml` only (no Terraform duplication)
  - `generators.py` resolves role names to ARNs from config
  - Simplified `run_task` SFN template (no more JSONata role mapping)
  
### Removed
- `aws_lambda_function.asset_trigger` — Lambda that handled asset trigger routing
- `aws_cloudwatch_event_rule.asset_materialized` — EventBridge rule for asset events  
- `aws_sqs_queue.asset_trigger_dlq` — Dead letter queue for failed events
- `aws_iam_role.asset_trigger_role` — IAM role for Lambda
- CloudWatch alarms and dashboard metrics for removed resources
- Terraform `cross_account_roles` variable (now from pyproject.toml)

### Added
- **`notify_asset_consumers` SFN helper** — Pure Step Functions implementation
  - OR logic: Trigger immediately on any asset
  - AND logic: Atomic counter + distributed lock for race-safe triggers
  - Self-trigger cycle prevention
  - Uses subscription data directly (no extra DynamoDB GetItem)
  
- **`slsflow-validate` CLI command** — Cross-pipeline validation
  ```bash
  slsflow-validate --dir ./pipelines
  # Checks for asset cycles between DAGs
  ```
  
- **DAG class extensions** for compatibility
  - `default_timeout` — Default timeout for all tasks (seconds)
  - `trigger_assets` — Alternative to `schedule` for asset triggers
  - `trigger_mode` — "all" (AND) or "any" (OR)
  
- **Asset class** — `metadata` parameter as alias for `extra`

- **Documentation** — [Cross-Account Roles Guide](docs/deployment/CROSS_ACCOUNT_ROLES.md)
  - Complete IAM setup: trust policies, permissions
  - Troubleshooting common errors
  - Security best practices
  - Multi-account example

### Fixed
- **DynamoDB pagination** in `query_subscriptions` and `notify_asset_subscribers` Lambdas
  - Previously only first page (1MB) was returned
  - Now paginates through all results (with 10K safety limit)
  
- **Timeout error message** in `dependency_wrapper` — changed "24 hours" to "7 days" (actual timeout)

- **Notify reliability** — removed fire-and-forget pattern
  - `Notify_Dependents`, `Notify_Dependents_Failed`: now sync (`startExecution.sync:2`)
  - `Notify_Asset_Consumers_SFN`: now sync
  - `Emit_Asset_Events` Map: added error handling
  - `Notify_Asset_Subscribers`: added error handling
  - If notify fails after 5 retries → task fails with proper callback to pipeline
  - Alerts (Slack, PagerDuty) triggered on failure as expected
  - No more silent hanging of downstream tasks

- **Asset lineage now shows `wait_for` dependencies**
  - Tasks using `wait_for=[asset.within(...)]` appear as consumers on lineage graph
  - Cross-pipeline dependencies (pull-based) now visible in UI

- **Pipeline name duplication bug**
  - Fixed: `pipeline_name` now uses `dag_id` instead of `StateMachine.Name`
  - Previously: `myorg-dev-slsflow-acme-daily` (full SFN name with namespace)
  - Now: `acme-daily` (clean dag_id)
  - Requires re-deploy of all pipelines to fix existing duplicates

- **List dependencies bug**
  - Fixed: `task_final([task_a, task_b, task_c])` now correctly sets dependencies
  - Previously: lists of TaskInstances were ignored in `_extract_dependencies()`
  - Now: lists are unpacked and each TaskInstance is registered as upstream dependency

- **`wait_for` now shown in Task Detail Modal**
  - API now returns `wait_for` field in task responses
  - UI displays "Asset Dependencies" section with asset name and freshness constraint

### Fixed (UI)
- `MAX_EVENTS_DISPLAY` increased from 20 to 100 (fixes "No data" for assets with many producers)
- `PARTITION_ARG` variable now shown in BackfillModal and documented in HelpModal

---

## v51.24 - 2026-01-29

### Fixed (Code Review)
- **Fixed failing test** `test_notify_dependents_deps_blocked`
  - Test now correctly checks `constants.py` for `UPSTREAM_FAILED` status
  - Previously looked in `index.py` where it's imported, not defined
- **Added date validation** in backfill API endpoints
  - `backfill_by_asset()` now validates `start_date` and `end_date` format
  - `backfill_pipeline()` now validates `start_date` and `end_date` format
  - Returns 400 with clear error message for invalid dates
- **Fixed documentation inaccuracies**
  - DynamoDB tables: 7 → 8 (added `asset_subscriptions`)
  - Table name: `task_subscriptions` → `dependency_subscriptions`
  - `Pipeline` → `DAG` in ASSET_PULL_FEATURE.md

### Added
- **Developer onboarding**
  - `CONTRIBUTING.md` — Setup, testing, PR checklist, dependency versions
  - `Makefile` — Common commands: `make test`, `make check`, `make lint`, `make sync-constants`
- **Documentation improvements**
  - `docs/getting-started/SETUP_FROM_SCRATCH.md` — Complete setup from blank AWS account
  - `docs/operations/TROUBLESHOOTING.md` — Consolidated troubleshooting guide
  - `docs/tools/DEVELOPMENT.md` — Lambda sync, validation, testing
  - Rewritten `QUICKSTART.md` — Minimal 5-minute copy-paste guide
  - Updated `TUTORIAL.md` — Clear 30-minute walkthrough for beginners

### Changed
- `auto_registration` Lambda runtime: 3.11 → 3.12 (all Lambdas now 3.12)
- Python version requirement: 3.9 → 3.11+ (docs and pyproject.toml)
- Node.js version requirement: 18+ → 22+ (LTS until 2027)
- Updated `docs/README.md` with TROUBLESHOOTING.md link
- Updated `docs/architecture/ARCHITECTURE.md` with correct table list

---

## v51.10 - 2026-01-28

### Added (Vercel Deployment Support)
- **Vercel deployment option** for Console UI
  - `vercel.json` — Rewrites `/api/*` to API Gateway
  - Automatic deployments on git push
  - Preview deployments for PRs
  - Simplified CI/CD workflow
- **`enable_console_cloudfront` variable** — Make CloudFront/S3 optional
  - Default: `false` (Vercel mode)
  - Set `true` to enable CloudFront deployment
- New `docs/features/vercel-deployment.md` — Vercel setup guide

### Changed
- `ui/public/config.js` — Updated for Vercel (relative `/api` URL)
- `terraform/shared/console.tf` — S3/CloudFront resources now conditional
- `terraform/shared/outputs.tf` — Console outputs return `null` when CloudFront disabled

### Migration
To switch from CloudFront to Vercel:
1. Set `enable_console_cloudfront = false` in terraform.tfvars
2. Run `terraform apply`
3. Update `vercel.json` with your API Gateway URL
4. Deploy to Vercel: `cd ui && vercel`

---

## v51.9 - 2026-01-28

### Added (Cognito Authentication)
- **AWS Cognito User Pool** authentication for Console API
  - Admin-only user creation (no self-registration)
  - JWT-based API authorization via API Gateway
  - Automatic token refresh with seamless UX
  - MFA support (TOTP) - configurable as OFF/OPTIONAL/ON
  - Strong password policies (12+ chars, mixed case, numbers, symbols)
- **Login Page** (`LoginPage.jsx`)
  - Clean UI matching slsflow design system
  - Email/password sign in
  - New password setup flow (first login)
  - MFA verification
  - Password reset with email verification
- **UserMenu component** — User dropdown in header with sign out
- **AuthProvider & useAuth hook** — Authentication state management
  - `signIn()`, `signOut()`, `forgotPassword()`, `confirmForgotPassword()`
  - Automatic token refresh before expiry
  - Session persistence in localStorage
- **API client auth integration** — Automatic Authorization header injection
- **Terraform module** (`cognito.tf`)
  - `enable_cognito_auth` variable to toggle feature
  - User Pool with admin-only signup
  - App Client for SPA (no secret)
  - JWT Authorizer for API Gateway
  - Admin/Viewer user groups

### Documentation
- New `docs/features/authentication.md` — Complete auth guide
  - Enabling authentication step-by-step
  - User management CLI commands
  - First login experience
  - Security features explained
  - Troubleshooting guide

### Changed
- `ui/src/utils/api.js` — Added auth header injection and 401 handling
- `ui/src/main.jsx` — Wrapped app with AuthProvider
- `ui/src/components/Header.jsx` — Added UserMenu component
- `ui/public/config.js` — Added AUTH configuration section

---

## v51.8 - 2026-01-27

### Added (AI Assistant)
- **slsflow-ai CLI** — AI-powered pipeline generation from natural language (FREE!)
  - Smart provider: Groq (cloud) → Ollama (local) fallback
  - Interactive mode with `/generate`, `/debug`, `/help` commands
  - **NEW: `/example [name]`** — Show production-ready examples (basic, parallel, cleanup, asset, wait_for, glue)
  - **NEW: `/validate`** — Validate generated code before saving
  - **NEW: `/save <path>`** — Save code directly to `pipelines/<path>/` with Pulumi.yaml
  - IaC output selection: Pulumi, Terraform, CloudFormation
  - Auto-setup on first run (downloads model, prompts for Groq key)
  - Comprehensive knowledge base (~300 lines of DSL documentation)
  - 6 production-ready examples built-in
- **Local testing module** (`slsflow.local`)
  - `validate(dag)` — Check DAG structure and ASL validity
  - `dry_run(dag)` — Preview execution plan without running
  - `run(dag, mock=True)` — Simulate execution locally
  - `run(dag, localstack=True)` — Run against LocalStack
- **Multi-IaC deployment modules**
  - `slsflow.terraform` — Generate Terraform configuration
  - `slsflow.cloudformation` — Generate CloudFormation/SAM templates

### Documentation
- Complete rewrite of AI_ASSISTANT.md
- New LOCAL_TESTING.md with examples
- Updated README with AI and local testing sections
- Added AI and local testing to documentation index

### Changed
- pyproject.toml: Version bump to 0.36.78
- pyproject.toml: New `ai` optional dependency (ollama, groq)
- pyproject.toml: Separate `ai-paid` for Anthropic/OpenAI
- scripts/setup-ai.sh: One-command AI setup

---

## v51.7 - 2026-01-26

### Added (Asset Pull / wait_for)
- **wait_for parameter** — Tasks can wait for assets to be fresh before executing
  - `@task.sfn(..., wait_for=[asset])` — Wait for latest asset
  - `@task.sfn(..., wait_for=[asset.within(hours=6)])` — Wait for fresh asset
  - `AssetAll(a, b)` / `AssetAny(a, b)` — Combine conditions
- **Asset freshness checking** — `check_asset_freshness` Lambda validates asset timestamps
- **Complete documentation** — ASSET_PULL_FEATURE.md with examples

---

## v51.6 - 2026-01-20

### Fixed (Audit fixes)
- **topological_sort()** — Now filters out Step dependencies, only considers Task objects. Fixes CLI `--tasks` crash when using `step >> task()` pattern.
- **roots()/leaves()** — Also filter Step dependencies for consistency.

### Updated (Test modernization)
- **test_smoke.py** — Updated all tests for v51+ architecture:
  - `test_notify_dependents_deps_blocked` → checks `evaluate_deps` instead of removed Lambda
  - `test_trigger_rule_sync` → checks `evaluate_deps` instead of `notify_dependents` Lambda
  - `test_no_dead_code` → removed check for non-existent `notify_dependents/index.py`
  - `test_task_completed_contract` → checks DynamoDB + SFN helpers instead of removed EventBridge patterns
- **test_trigger_rules.py** — Updated docstrings to reference `evaluate_deps` as source of truth

### Test Results
- test_smoke.py: 20 passed ✅
- test_trigger_rules.py: 2838 combinations + 31 edge cases ✅
- test_integration.py: 9 passed ✅

---

## v51.5 - 2026-01-20

### Improved
- **Relaxed execution_name regex** — Changed `EXECUTION_NAME_PATTERN` from `.{8,}` to `.+` for short_id suffix. Now accepts any length short_id (was minimum 8 chars), making it more tolerant to test/dev data.

---

## v51.4 - 2026-01-20

### Improved (Code consistency)
- **restart_task** — Now uses `resolve_task_item()` like all other action endpoints for consistent task lookup with pagination and GSI fallback

---

## v51.3 - 2026-01-20

### Fixed (Code review round 2 by Myroslav)
- **Query pagination** — `resolve_task_item()` helper now paginates through GSI results to handle large datasets (>1MB). Previously single `query()` call could miss tasks on busy days.
- **Unified task resolver** — All action endpoints (`skip_task`, `fail_task`, `mark_success`, `stop_task`) now use `resolve_task_item()` with proper GSI lookup instead of legacy `f"{task_name}-{date}"` fallback which doesn't match v51+ execution_name format.
- **GSI fallback for direct lookup** — If `is_execution_name()` returns true but `get_item()` fails, resolver now falls back to GSI search instead of returning 404.
- **Wrapper sanitization** — JSONata in `dependency_wrapper` now ALWAYS sanitizes `pipeline_execution_short` (removes `.` and `:`) even when `length <= 20` or when value is passed directly.

### Improved
- **Lazy AWS client initialization** — `config.py` now uses lazy initialization pattern (like `evaluate_deps`) for all boto3 clients. This fixes pytest import failures and improves testability.
- **Task config API clarity** — `get_task_config()` now returns separate `config` and `runtime` sections. `retry_attempts` moved to `runtime` (read-only) since it's a counter, not a config field.
- **Removed unused imports** — Cleaned up `boto3` and `scan_all` imports from tasks.py
- **Updated comments** — Replaced outdated "Emit task.completed" comments with "Notify dependents"

### Technical
- `resolve_task_item(table, task_name, date, pipeline_execution)` — New unified helper for task lookup with pagination and fallback
- All action endpoints now accept optional `pipeline_execution` in request body for disambiguation
- Lazy proxy classes (`_LazyDynamoDB`, `_LazySFN`, etc.) maintain same interface as direct boto3 clients

---

## v51.2 - 2026-01-20

### Fixed (Code review findings by Myroslav)
- **get_task_config / update_task_config** — Fixed execution_name lookup to use GSI-based item search (like `restart_task`) instead of legacy `{task_name}-{date}` format which doesn't match v51+ execution names (`{task_name}-{date}-{pipeline_execution_short}`)
- **pipeline_execution_short fallback** — Unified fallback logic with new `compute_pipeline_execution_short()` function that mirrors wrapper JSONata: takes last 20 chars and removes `.` and `:` characters. Previously `utils.py` took last 20 chars without sanitizing, while `task_actions.py` incorrectly took first 20 chars.
- **stop_task orchestration callback** — Added `send_task_failure()` callback when stopping waiting tasks (→ aborted). This prevents pipeline orchestration from hanging when it uses `waitForTaskToken` pattern.

### Improved
- **Test coverage** — Updated `test_integration.py` trigger rules test to include `aborted` in terminal failure statuses, matching production `evaluate_deps/index.py`

### Technical
- `compute_pipeline_execution_short()` — New utility function for consistent short ID generation
- `ensure_pipeline_execution_short()` — Now delegates to `compute_pipeline_execution_short()` for fallback
- `extract_pipeline_execution_short()` — Uses `compute_pipeline_execution_short()` instead of hardcoded `[:20]`

---

## v51.1 - 2026-01-19

### Fixed (Post-audit bugfixes)
- **BUG #8** (CRITICAL): Fixed Slack actions still using EventBridge — `slack_action_skip`, `slack_action_fail`, `slack_action_success` now use `notify_dependents_via_sfn()` instead of `events.put_events('task.completed')`. Without this fix, Slack button actions would NOT wake up dependent tasks.
- **BUG #9**: Fixed terminal statuses inconsistency — All manual task actions now use `TaskStatus.TERMINAL` which includes ALL terminal statuses (`success`, `failed`, `skipped`, `aborted`, `upstream_failed`). Previously some actions only checked `{'success', 'failed', 'skipped'}`, allowing overwrites of `upstream_failed`/`aborted` states.
- **BUG #10**: Removed unused `signal='skipped'` callback — `skip_task` no longer sends `send_task_success(wait_token, signal='skipped')` as this signal was not handled by dependency_wrapper and could cause undefined behavior. The wrapper is already stopped by `stop_task_executions()`.
- **BUG #11**: Fixed `retry_task` dead code — Now delegates to `restart_task` for actual functionality instead of just setting `decision='restart'` which nothing read.

### Improved
- **Code deduplication** — Created `task_actions.py` module with shared utilities:
  - `notify_dependents_via_sfn()` — Single implementation used by both tasks.py and slack.py
  - `is_terminal_status()` — Consistent terminal status checking
  - `build_condition_expression_values()` — Standard ConditionExpression values
  - `TERMINAL_CONDITION_EXPRESSION` — Reusable condition expression string
- **Documentation updated** — BACKEND.md now reflects SFN-based notify_dependents architecture

### Technical
- Removed EventBridge client from slack.py (no longer needed)
- All ConditionExpression now include `:aborted` and `:upstream_failed`
- `retry_task` marked as DEPRECATED, forwards to `restart_task`

---

## v51 - 2026-01-19

### Changed (Breaking)
- **notify_dependents architecture refactored** — Replaced EventBridge + Lambda approach with SFN-based helper:
  - **REMOVED**: `notify_dependents` Lambda (565 lines)
  - **REMOVED**: `task_completed` EventBridge rule
  - **REMOVED**: `notify_dependents_dlq` SQS queue
  - **ADDED**: `notify_dependents_helper` Step Function (orchestrates subscriber notification)
  - **ADDED**: `evaluate_deps` Lambda (minimal, ~330 lines) for BatchGetItem + trigger_rule evaluation
  
- **Console API uses SFN instead of EventBridge** — `skip_task`, `fail_task`, `mark_success`, `stop_task` now invoke `notify_dependents_helper` SFN directly instead of emitting EventBridge events

### Improved
- **Better observability** — All notify_dependents operations now visible in Step Functions execution history (no more "black hole" for debugging)
- **Reduced Lambda complexity** — evaluate_deps Lambda is 80% smaller than old notify_dependents Lambda
- **Explicit dependency tracking** — Each subscriber processing step visible in SFN Map state

### Fixed (during code review)
- **BUG #1**: Fixed `completed_task` reference in Map state — was using `$states.context.Execution.Input.completed_task` (undefined), changed to `$states.input.completed_task`
- **BUG #2**: Fixed `Mark_Waiting_Paused` — now saves `wait_token` and `pending_dependency_keys` for proper resume functionality
- **BUG #3**: Fixed pause routing logic — added `deps_satisfied` field to distinguish "deps ready but paused" from "deps not ready and paused"
- **BUG #4**: Fixed `wait_token` cleanup — `Update_Status_Ready` and `Update_Status_Blocked` now properly REMOVE `wait_token` after signaling
- **BUG #5** (CRITICAL): Fixed Map state Arguments — `$states.input` in Map Arguments refers to current item, not Map input. Changed to use `$states.context.Execution.Input` for `completed_task`
- **BUG #6**: Added `pipeline_execution` parameter to console_api `_notify_dependents` calls for proper pause check support
- **BUG #7**: Added Catch block to `Get_Subscriber_Record` — prevents one bad subscriber from breaking entire Map state processing

### UX Impact
- **No changes to user experience** — All API responses remain identical, UI unchanged
- Same task skip/fail/mark_success behavior from user perspective
- Same trigger_rule semantics (all 11 rules supported)

### Known Limitations
- **Orphan subscriptions**: When task has multiple deps and first dep completes (rule not satisfied), its subscription is not deleted. Cleaned up by TTL (30 days). Not a functional issue.
- **Query pagination**: DynamoDB Query returns max 1MB (~3400 subscriptions). For extreme fan-out scenarios, pagination may be needed in future.

### Technical
- New environment variable: `NOTIFY_DEPENDENTS_HELPER_ARN` (replaces `NOTIFY_DEPENDENTS_LAMBDA`)
- IAM permissions updated: `states:StartExecution` instead of `lambda:InvokeFunction`
- Monitoring: CloudWatch alarm renamed from `notify_dependents_errors` to `evaluate_deps_errors`
- Dashboard metrics updated to show `evaluate_deps` Lambda
- New field in evaluate_deps response: `deps_satisfied` (boolean)
- `_notify_dependents` now accepts optional `pipeline_execution` parameter

### Tests
- 56 tests for evaluate_deps Lambda (all trigger_rules + pause scenarios covered)
- 28 tests for console_api utilities
- Total: 84 tests passing

---

## v36.96 - 2025-01-15
### Changed
- **Removed pause button from sidebar**: Removed pipeline pause/resume functionality from sidebar (can be re-added later if needed)

### Fixed
- **Pipeline name tooltip**: Added title attribute to pipeline name in sidebar for showing full name on hover when truncated

All notable changes to slsflow are documented in this file.

## [v36.95] - 2026-01-15

### Fixed
- **AssetsView crash** — Fixed `STALE_THRESHOLD_HOURS is not defined` error that prevented Assets view from loading. Updated to use `STALENESS.STALE_HOURS` and `STALENESS.WARNING_HOURS` from centralized constants.
- **Dark mode backfill disclaimer** — Fixed backfill modal "How backfill works" info box being barely visible in dark mode. Added proper `--info-bg`, `--info-border`, `--info-text` CSS variables for both light and dark themes.
- **npm dependency warnings** — Downgraded dev dependencies to versions compatible with Node 20.12: vite@5.4.21, vitest@2.1.8, jsdom@24.1.3. Removed EBADENGINE warnings.
- **Vite build warnings** — Fixed "dynamically imported but also statically imported" warnings by removing lazy-loaded components (AssetsView, AllTasksView, AllRunsView) from components/index.js static exports. Now properly code-split into separate chunks.

### Improved
- **Help Modal icons consistency** — Updated Task Statuses section to show actual Lucide icons matching DAG and Gantt views (CheckCircle2, Loader2, XCircle, Clock, etc.) instead of generic colored squares. Added documentation for additional statuses: Deps Ready, Waiting Delay, Paused, Stopped, Aborted.
- **Pipeline sidebar** — Improved layout for long pipeline names:
  - Pause/resume button now absolutely positioned, appears only on hover (doesn't take layout space)
  - Native tooltip (title attribute) shows full name on hover
  - Improved text truncation with `overflow: hidden` on container
  - Smaller SLA badge that doesn't squish

### Technical
- New CSS variables: `--info-bg`, `--info-border`, `--info-text` (light and dark variants)
- `.pipeline-pause-btn` now uses `position: absolute` with `right: 8px`
- HelpModal imports additional status icons: XCircle, Loader2, SkipForward, PlayCircle, Ban, StopCircle, Pause
- Lazy-loaded components now create proper separate chunks for better caching

---

## [v36.93] - 2026-01-15

### Improved
- **CSS refactoring** — Moved inline styles from `AssetLineageFlow.jsx` to CSS classes. Reduced component size by ~100 lines and improved maintainability.
- **Centralized constants** — Extended `constants.js` with `POLLING`, `API`, `UI`, `STALENESS`, `GRAPH`, and `KEYS` configuration objects. All magic numbers now have named constants.
- **Enhanced API client** — Added Result pattern (`ok`/`error`), timeout support, retry logic with exponential backoff, and helper functions `isOk()`, `getData()`.
- **Lazy loading** — `AssetsView`, `AllTasksView`, `AllRunsView` are now lazy-loaded with Suspense for faster initial load.
- **Default filter state** — Asset Lineage graph now shows only Assets by default (Tasks and DAG Triggers unchecked).

### Code Quality
- Unified staleness thresholds using `STALENESS` constants
- Replaced hardcoded polling intervals with `POLLING.TICK`, `POLLING.ASSETS`
- Added proper CSS classes for lineage nodes: `.lineage-node--asset`, `.lineage-node--task`, `.lineage-node--trigger`
- New `.view-loader` component for Suspense fallback

### Technical
- API backward compatible: both `result.ok` and `!result.error` patterns work
- Build passes with no errors, only benign warnings about mixed static/dynamic imports

---

## [v36.91] - 2026-01-15

### Fixed
- **JSX file extension bug** — Fixed `usePipelineActions.js` containing JSX syntax but having `.js` extension, causing Vite build to fail. Renamed to `.jsx`.

### Improved
- **Extracted DAG helpers** — Created `utils/dagHelpers.js` with `getUpstreamTasks`, `getDownstreamTasks`, `getUpstreamCount`, `getDownstreamCount` functions. Removed duplicate implementations from `usePipelineActions.jsx` and `TaskDetailModal.jsx`.
- **Unified duration formatting** — Replaced inline duration formatting in `TaskDetailModal.jsx` and `DAGGraphFlow.jsx` with shared `formatDuration()` utility.
- **Centralized icon imports** — Migrated direct `lucide-react` imports to centralized `utils/icons.jsx` in: `App.jsx`, `CalendarView.jsx`, `PipelineDetail.jsx`. Added missing icon exports: `ChevronLeft`, `ArrowLeft`, `Square`, `Keyboard`, `Link2`, `GitBranch`, `GitMerge`, `Network`.
- **Consistent async patterns** — Replaced `.then()` with `async/await` in `AssetsView.jsx` for consistency.

### Code Quality
- Reduced code duplication in DAG traversal logic (~60 lines removed)
- All icon imports now go through single source of truth
- Build passes successfully with no warnings

---

## [v36.85] - 2026-01-15

### Added
- **Command Palette (⌘K)** — Spotlight-style search for pipelines and commands. Keyboard navigation with ↑↓, Enter to select, Esc to close.
- **ErrorBoundary wrappers** — DAGGraph, GanttChart, CalendarView, and AssetsView are now wrapped in error boundaries with fallback UI.

### Improved
- **ToastProvider integration** — Replaced `useState` toast with context-based `useToast` hook. Toast notifications are now managed globally via `ToastProvider` in main.jsx.
- **useTaskEvents hook integration** — Extracted task events fetching logic from App.jsx into dedicated hook. Reduces App.jsx complexity.
- **Console cleanup** — Removed all `console.log` statements. Only `console.error` and `console.warn` remain for legitimate error handling.

### Stats
- App.jsx: 1423 → 1419 lines
- useState: 32 → 29 hooks  
- useEffect: 16 → 15 hooks
- console.log: 11 → 0 statements

---

## [v36.77] - 2026-01-14

### Added
- **Skip source tasks in Backfill by Assets** — New checkbox (enabled by default) that skips tasks without inlets (scrapers). This allows backfilling ETL transformations without re-running data scrapers.
- **Asset Lineage filter checkboxes** — Replaced dropdown with checkboxes: Assets (always), Tasks, DAG Triggers. Allows flexible combinations.
- **Pause callback mechanism** — New `sf_pause_waiter` helper SFN for callback-based pause (instead of polling).
- **Extend Pause button** — "+12h" button in UI to extend pause timeout without resuming.

### Fixed
- **Restart task now finds tasks correctly** — Was trying to lookup by `task_name-date` but key is `task_name-date-shortId`. Now scans by task_name + date to find correct record.
- **React Flow DAG dragging** — Now uses standard React Flow Controls lock button (same as lineage view).
- **Pipeline pause now works** — Tasks wait for Resume callback instead of polling.
- **Stop Pipeline shows correct status** — Fixed order of operations: now stops tasks FIRST (→ stopped status), then stops orchestration.

### Improved
- **Pause uses callback** — Reduced from 5 states to 3. Instant resume, zero cost while waiting. 12-hour timeout with "Extend +12h" button to prevent stuck tasks.
- **Asset Lineage layout** — Improved spacing and container height for better visualization.

---

## [v36.76] - 2026-01-13

### Fixed
- **Register_Pipeline now uses StateMachine.Name** — Was using `dag.dag_id` ("acme") instead of full name ("myorg-dev-acme"), causing API to not find DAG with outlets in registry
- **Fixed Source Assets logic in Backfill** — Now correctly identifies external assets (consumed but not produced in pipeline), not leaf assets
- **Fixed backfill 500 error** — `dag` field from DynamoDB is JSON string, now properly parsed before accessing `.get()`

---

## [v36.75] - 2026-01-13

### Fixed
- **Modal close button (×) now on the right** — Added `margin-left: auto` to `.modal-close`
- **Package version updated to 0.36.75** — Was stuck at 0.18.0 (old PyPI version)

### Clarifications
- **Assets not showing in backfill**: DAG metadata with outlets is written to DynamoDB only when pipeline RUNS (Register_Pipeline state). After redeploy, you must **run the pipeline once** to update the registry.
- **Incremental works for both Tasks and Assets** — It checks DynamoDB for successful tasks per date, regardless of selection mode.

---

## [v36.74] - 2026-01-13

### Fixed
- **Pipeline trigger now shows new execution immediately** — Added new execution to list right after trigger (before API refresh)
- **Stop button missing color** — Removed duplicate `.btn-danger` that used undefined `--danger` variable, now uses `--error` correctly
- Replaced all `var(--danger)` with `var(--error)` in CSS

---

## [v36.73] - 2026-01-13

### Changed
- **Moved monitoring variables to variables.tf** — `enable_infra_monitoring`, `infra_alarm_sns_topic_arn`
- **Monitoring disabled by default** — `enable_infra_monitoring = false`

---

## [v36.72] - 2026-01-13

### Changed
- **Removed logging from step-function module** — No CloudWatch Log Group, no logging_configuration
- Removed `log_level` parameter from module

---

## [v36.71] - 2026-01-13

### Fixed
- **PagerDuty alerter JSONata error** — Changed `$states.error` to `$states.errorOutput` in Catch block

---

## [v36.70] - 2026-01-13

### Changed
- Module default namespace = `"slsflow"` (for standalone use)
- All module calls in `main.tf` now explicitly pass `namespace = var.namespace`

---

## [v36.69] - 2026-01-13

### Changed
- Moved `modules/` directory to `terraform/modules/` (sibling to `shared/`)
- Updated module source paths: `./modules/step-function` → `../modules/step-function`

### Structure
```
terraform/
├── modules/
│   └── step-function/
├── shared/
│   ├── main.tf
│   ├── dynamodb.tf
│   └── ...
```

---

## [v36.68] - 2026-01-13

### Changed
- Removed `data "aws_region" "current" {}` from monitoring.tf — now uses `var.aws_region` directly

### Not Changed (by design)
After analysis, decided NOT to modularize Lambda and DynamoDB resources because:
- Each resource has unique schema/permissions (8 different DynamoDB schemas, 5 different IAM policies)
- Modules would add complexity without benefit
- Current inline code is more explicit and easier to debug

---

## [v36.67] - 2026-01-13

### Changed
- **Step Function module moved to local** — Replaced remote Terraform Cloud registry module with local `./modules/step-function`
- Updated module tags: `Stack = "Data Orchestration"`, added `ManagedBy = "terraform"`
- Removed `Retailer`, `Provider`, `Channel` null tags from module

### Structure
```
terraform/
├── modules/
│   └── step-function/
│       ├── main.tf
│       ├── variables.tf
│       ├── output.tf
│       ├── versions.tf
│       └── README.md
└── shared/
    └── ...
```

---

## [v36.66] - 2026-01-13

### Changed
- **Unified tags across all Terraform resources:**
  - `Stack = "Data Orchestration"` (was "Data Pipeline" or "Monitoring")
  - `Stage = local.stage`
  - `Namespace = var.namespace`
  - `Name = "${var.namespace}-${local.stage}-{resource}"` (where applicable)
  - `ManagedBy = "terraform"`
- Added `local.common_tags` in `locals.tf` for consistent tagging
- CloudWatch alarms use `local.common_tags` directly

---

## [v36.65] - 2026-01-13

### Fixed
- **Terraform monitoring.tf errors** — Added missing `locals.common_tags` block and fixed DynamoDB table reference (`task_subscriptions` → `dependency_subscriptions`)

---

## [v36.64] - 2026-01-13

### Added
- **Backfill disclaimer in modal** — Info box explaining how backfill works (By Tasks vs By Assets)
- **Backfill help tab** — New "⏮️ Backfill" tab in Help modal with:
  - What is backfill
  - Selection modes explained
  - Incremental vs Full reprocess
  - Auto variables reference
  - Example scenarios (bug fix, new data, failed run, missing dates)

---

## [v36.63] - 2026-01-13

### Added
- **Incremental backfill option** — Checkbox in Backfill modal to skip tasks that already succeeded for each date
  - Backend queries `pipeline_tokens` for existing successful tasks
  - Per-date skip_tasks list (different dates may skip different tasks)
  - Default: OFF (full reprocess, same as before)

### Usage
```
☐ Incremental (skip already-successful tasks)
   → Runs full pipeline for each date (default)

☑️ Incremental (skip already-successful tasks)  
   → Skips tasks that already have status=success for that date
```

---

## [v36.62] - 2026-01-13

### Fixed
- **Backfill By Assets now includes upstream dependencies** — Previously only ran the task that produces the selected asset, causing it to wait forever for skipped dependencies. Now automatically includes all upstream tasks in the execution.

Example:
```
DAG: task_a → task_b → task_c (produces: final_asset)

Before (broken):
  Select [final_asset] → runs only task_c → waits forever for task_b

After (fixed):
  Select [final_asset] → runs task_a, task_b, task_c → completes!
```

---

## [v36.61] - 2026-01-13

### Changed
- **Renamed `terraforms/` → `terraform/`** — Standard naming convention

---

## [v36.60] - 2026-01-13

### Fixed
- **Backfill "By Assets" was empty** — Fixed TWO places:
  1. `generate_dag_json()` — used by CLI (was already fixed)
  2. `dag_metadata` in ASL — this is what gets written to DynamoDB when pipeline runs!

### How it works
When pipeline executes, the `Register_Pipeline` Step Function state writes DAG metadata to DynamoDB `pipeline_registry` table. This metadata now includes `outlets`/`inlets` for each task.

### Note
Requires running the pipeline once after re-deploy to update registry.

---

## [v36.59] - 2026-01-13

### Changed
- **Est. Cost calculation** — Now dynamic based on task_type (was hardcoded 10 transitions)
  - sfn/glue/ecs/athena/emr/batch: ~22 transitions (~$0.00055)
  - lambda: ~18 transitions (~$0.00045)
- **API returns task_type** — Added task_type to pipeline status response
- **UI shows Task Type** — Task modal now displays task type badge

---

## [v36.58] - 2026-01-13

### Added
- **Infrastructure monitoring** — CloudWatch Alarms for Lambdas, DynamoDB, Step Functions (terraform/shared/monitoring.tf)
- **CloudWatch Dashboard** — Visual overview of Lambda errors, invocations, DynamoDB throttles
- **Integration tests** — 8 new tests for trigger rules, asset logic, backfill, etc.
- **Tutorial documentation** — Step-by-step "From zero to production" guide

### New Alarms
- Lambda errors (console_api, notify_dependents, asset_trigger)
- Lambda duration (approaching timeout)
- Lambda throttling
- DynamoDB throttling
- Step Function failures (wrapper)

---

## [v36.57] - 2026-01-13

### Fixed
- **config.js comment** — Fixed misleading comment (API_URL MUST include /api suffix)
- **Wrapper step validation** — Added check that wrapper steps (lambda/glue/ecs/athena) can't depend on direct steps (wait/pass/sns/etc) - would cause infinite wait

---

## [v36.56] - 2026-01-13

### Fixed
- **Slack error handling** — Now accepts string error (from failure_handler) or object error (from SFN Catch)
- **Invalid severity example** — Changed "high" to "error" in docs/examples (valid: critical, error, warning, info)

---

## [v36.54] - 2026-01-13

### Added
- **Alerts wiring** — failure_handler now calls Slack and PagerDuty helpers
- **Code splitting** — UI bundle split into vendor chunks for better caching
- **Comprehensive documentation** — All docs updated

### Changed
- failure_handler calls sf_slack_interactive and sf_pagerduty_alerter on failure
- UI bundle: index.js (125KB), vendor-react.js (141KB), vendor-flow.js (238KB)

---

## [v36.53] - 2026-01-13

### Added
- **Required alerts parameter** — DAG must have `alerts` configured
- Alert validation (Slack channel format, PagerDuty severity)
- Error message with examples when alerts missing

### Changed
- All pipelines updated with alerts configuration
- test-pipeline: `alerts=None` (explicitly disabled)
- acme pipelines: `alerts={"slack": "#acme-alerts"}`

---

## [v36.52] - 2026-01-13

### Added
- **PagerDuty Alerter** — New Step Function helper
- HTTP Task to PagerDuty Events API v2
- Configurable via `pagerduty_routing_key` variable
- Dedup key using execution_name
- Custom severity levels (critical, error, warning, info)

---

## [v36.51] - 2026-01-12

### Fixed
- Backfill modal scrolling issues
- Empty state handling for backfill selection
- Variables preview formatting

---

## [v36.50] - 2026-01-12

### Added
- **Backfill auto variables** — Automatic date-based variables
- Variables preview in backfill modal
- Support for: current_date, date_compact, year, month, day, day_of_week, etc.

---

## [v36.49] - 2026-01-12

### Added
- **Asset-based backfill** — Select assets to materialize
- Toggle between tasks and assets mode
- Smart defaults (derived assets ON, source assets OFF)

---

## [v36.48] - 2026-01-12

### Added
- **Task selection in backfill** — Choose specific tasks to run
- Checkboxes for individual tasks
- Select All / Deselect All

---

## [v36.47] - 2026-01-12

### Added
- **Backfill modal** — Run pipeline for date range
- Date range picker
- Confirmation dialog

---

## [v36.46] - 2026-01-12

### Added
- **Help modal** — Icons legend and API reference
- Accessible via ? button or keyboard shortcut

---

## [v36.45] - 2026-01-12

### Added
- **Backend filtering** — Filter tasks and runs server-side
- Pagination support for large datasets

---

## [v36.40] - 2026-01-12

### Added
- **Runs view** — All pipeline executions with filtering
- Duration, status, triggered_by columns

---

## [v36.35] - 2026-01-12

### Added
- **Tasks view** — All task instances across pipelines
- Filtering by pipeline, status, date

---

## [v36.30] - 2026-01-12

### Added
- **Real-time updates** — WebSocket replaces polling
- Instant task status updates
- Connection status indicator

---

## [v36.25] - 2026-01-11

### Added
- **Asset lineage graph** — React Flow visualization
- Producer → Asset → Consumer relationships
- DAG triggers visualization
- Search and filter

---

## [v36.20] - 2026-01-11

### Added
- **Calendar view** — Historical executions by date
- Quick date navigation
- Status indicators

---

## [v36.15] - 2026-01-11

### Added
- **Gantt chart** — Timeline visualization
- Task duration bars
- Parallel execution visibility

---

## [v36.10] - 2026-01-10

### Added
- **Task events history** — DynamoDB table for task events
- Events timeline in task modal
- STARTED, TASK_FINISHED, MANUAL_DECISION events

---

## [v36.00] - 2026-01-10

### Added
- **Asset-based orchestration** — Airflow 3.0-style triggers
- AND logic (all assets required)
- OR logic (any asset triggers)
- Asset events and queue management

---

## [v35.00] - 2026-01-08

### Added
- Initial release
- Python DSL (DAG, @task decorators)
- 6 task types (sfn, lambda, glue, ecs, athena, emr, batch)
- Dependency management
- Slack notifications
- Web Console (DAG view)
- Pulumi deployment
- Terraform shared infrastructure
