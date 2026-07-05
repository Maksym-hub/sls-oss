# ADR #109 — Unified common parameters for `@task.<type>` decorators (`CommonTaskKwargs`)

> **Status:** ACCEPTED — implemented. Caller-visible behavior is unchanged for
> every documented usage; typo handling is preserved (ADR #106 D5) with a
> clearer error message.

## Context

All seven `@task` variant decorators (`sfn`, `lambda_`, `glue`, `ecs`,
`athena`, `emr`, `batch`) shared **13 common parameters** (`task_id`, `role`,
`wait_before`, `retries`, `retry_delay`, `retry_exponential_backoff`,
`retry_jitter`, `max_retry_delay`, `execution_timeout`,
`orchestration_timeout`, `trigger_rule`, `slack_channel`,
`skip_on_backfill`), each duplicated in every signature *and* in every
passthrough to `_create_task` — e.g. the `retry_delay` signature line existed
16×. Adding one common parameter meant ~14–16 identical edits (measured three
times during the retry work), which is precisely the fan-out CLAUDE.md #14
warns about, and the direct cause of signature drift risk between variants.

All 13 parameters were already keyword-only in every variant (each signature
has a bare `*` after `_func`), and all 13 defaults were byte-identical to the
defaults on `_create_task`.

## Decision

1. **One declaration:** `CommonTaskKwargs(TypedDict, total=False)` in
   `task.py` declares the 13 common parameters with their real types
   (`Optional[...]` where `None` is a default).
2. **Variant signatures collapse:** each variant keeps only its type-specific
   parameters plus `**common: Unpack[CommonTaskKwargs]` (PEP 692;
   `typing.Unpack` is native on the project floor, Python ≥ 3.11). Type
   checkers and PEP 692-aware IDEs still see and check every common kwarg.
3. **Single source of defaults:** an omitted common kwarg is simply not
   forwarded, so the default comes from `_create_task` — the one place that
   already owned the `default_args` fallback logic.
4. **Strict-kwargs preserved (D5):** `_validate_common_kwargs(name, common)`
   runs before every `_create_task` call and raises
   `TypeError: task.glue() got an unexpected keyword argument 'retrys'` —
   same exception class the pre-unification explicit signatures raised, now
   naming the decorator the user actually called instead of `_create_task`.
5. **Base `@task` (`__call__`) untouched:** it keeps its documented generic
   `**kwargs` catch-all; only the seven typed variants were unified.

`task.py` shrank from 1068 to 946 lines; the 7× passthrough blocks are gone.

## Consequences

- Adding a common task parameter = add it to `CommonTaskKwargs` + to
  `_create_task` (+ the `Task` field). Every variant picks it up
  automatically; the per-variant edit step no longer exists.
- Common parameters are no longer individually listed in
  `inspect.signature()` of the variants. No test or tool in the repo
  introspected those signatures (verified before the change); runtime callers
  are unaffected because the parameters were already keyword-only.
- The D5 typo tests (`tests/sdk/test_task_core.py`) pass unchanged and now
  exercise the shared validator, keeping its raise path covered.
