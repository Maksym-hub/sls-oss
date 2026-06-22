"""
Regression tests for code-review findings v0.78.0(3).

These exist because the external reviewer found three real issues that
unit tests had missed:
  1. CI runs console_api tests without slsflow installed → ImportError
  2. Inline Map history-event budget can't fit 5000 partitions
  3. Duplicate dict key in generators.py (Python silently keeps last)

These tests catch the regressions if anyone re-introduces them.
"""

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
GENERATORS_PY = REPO_ROOT / "slsflow" / "generators.py"
CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SDK_PARTITIONS = REPO_ROOT / "slsflow" / "partitions.py"
LAMBDA_CONSTANTS = REPO_ROOT / "sam" / "lambdas" / "console_api" / "constants.py"
BULK_BACKFILL_TPL = REPO_ROOT / "sam" / "sfn_templates" / "bulk_backfill" / "sfn.tpl.json"


# ───────────────────────────────────────────────────────────────────────────
# Duplicate dict keys — Python's silent footgun
# ───────────────────────────────────────────────────────────────────────────


def _find_duplicate_dict_keys(file_path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, key_name) for any dict literal that
    has a duplicate string-literal key. Python keeps only the last value
    silently, masking bugs."""
    tree = ast.parse(file_path.read_text())
    dupes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            seen = {}
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    if k.value in seen:
                        dupes.append((k.lineno, k.value))
                    seen[k.value] = k.lineno
    return dupes


def test_no_duplicate_dict_keys_in_generators():
    """generators.py had `"date": JSONATA_DATE` listed twice (commit
    pre-v0.78). Python silently kept the last entry; reviewer caught it.
    This test would have surfaced it in CI."""
    dupes = _find_duplicate_dict_keys(GENERATORS_PY)
    assert not dupes, (
        f"Duplicate dict keys in generators.py: {dupes}. "
        "Python keeps last value silently — likely a copy-paste bug."
    )


def test_no_duplicate_keys_in_critical_python_files():
    """Sweep critical files for the same class of bug."""
    critical = [
        REPO_ROOT / "slsflow" / "generators.py",
        REPO_ROOT / "slsflow" / "partitions.py",
        REPO_ROOT / "slsflow" / "granularity.py",
        REPO_ROOT / "sam" / "lambdas" / "console_api" / "routes" / "backfill.py",
        REPO_ROOT / "sam" / "lambdas" / "console_api" / "constants.py",
    ]
    all_dupes = {}
    for f in critical:
        if f.exists():
            dupes = _find_duplicate_dict_keys(f)
            if dupes:
                all_dupes[f.name] = dupes
    assert not all_dupes, f"Duplicate dict keys found: {all_dupes}"


# ───────────────────────────────────────────────────────────────────────────
# Partition hard limit ↔ Inline Map history budget
# ───────────────────────────────────────────────────────────────────────────


def _get_partition_hard_limit_from_constants() -> int:
    """Parse BackfillLimits.PARTITION_HARD_LIMIT from Lambda constants."""
    text = LAMBDA_CONSTANTS.read_text()
    m = re.search(r"PARTITION_HARD_LIMIT\s*=\s*(\d+)", text)
    assert m, "Could not find PARTITION_HARD_LIMIT in constants.py"
    return int(m.group(1))


def _get_partition_hard_limit_from_sdk() -> int:
    """Parse _PARTITION_HARD_LIMIT from SDK."""
    text = SDK_PARTITIONS.read_text()
    m = re.search(r"_PARTITION_HARD_LIMIT\s*=\s*(\d+)", text)
    assert m, "Could not find _PARTITION_HARD_LIMIT in slsflow/partitions.py"
    return int(m.group(1))


def test_partition_hard_limit_synced_between_sdk_and_lambda():
    """SDK and Lambda must share the same hard limit. They derive it for
    different reasons (Lambda: AWS Map history events; SDK: API safety),
    but the contract surfaced to users must match."""
    lambda_limit = _get_partition_hard_limit_from_constants()
    sdk_limit = _get_partition_hard_limit_from_sdk()
    assert lambda_limit == sdk_limit, (
        f"PARTITION_HARD_LIMIT mismatch: Lambda={lambda_limit}, SDK={sdk_limit}. "
        "Users see one as 400 range_too_large, the other as SDK validation. "
        "Sync them or document the divergence explicitly."
    )


def test_partition_hard_limit_fits_inline_map_history_budget():
    """AWS Step Functions Standard executions have a hard limit of 25,000
    history events per execution. The bulk-backfill SFN uses Inline Map,
    whose iterations contribute events to the parent execution's history.

    Per-iteration events (worst case happy path):
      - ItemProcessor states (7): ~2 each = 14
      - startExecution.sync:2 child SFN: ~4
      - Map iteration overhead: ~2
      = ~20 events per partition

    Safe ceiling: 25000 / 20 = 1250. We require limit <= 1500 for some
    headroom (retries, error paths add events).
    """
    EVENTS_PER_PARTITION = 20
    AWS_HISTORY_LIMIT = 25_000
    SAFETY_MARGIN = 1.2  # 20% headroom

    safe_max = int(AWS_HISTORY_LIMIT / EVENTS_PER_PARTITION / SAFETY_MARGIN)
    actual = _get_partition_hard_limit_from_constants()
    assert actual <= safe_max, (
        f"PARTITION_HARD_LIMIT={actual} exceeds Inline Map safe budget "
        f"(safe max ~{safe_max} = {AWS_HISTORY_LIMIT}/{EVENTS_PER_PARTITION}/"
        f"{SAFETY_MARGIN}). Either: (a) lower the limit, (b) migrate "
        f"bulk-backfill SFN to Distributed Map, or (c) chunk client-side."
    )


# ───────────────────────────────────────────────────────────────────────────
# CI sanity — slsflow must be importable for console_api tests
# ───────────────────────────────────────────────────────────────────────────


def test_ci_installs_slsflow_for_lambda_tests_job():
    """The `lambdas` CI job runs console_api tests. routes/backfill.py
    imports slsflow.partitions and slsflow.granularity. Without
    `pip install -e .`, the import fails and the job dies with
    ModuleNotFoundError. Reviewer caught this; pin the fix.
    """
    ci = CI_YAML.read_text()
    # Locate the `lambdas:` job (different indentation than top-level keys)
    lambdas_match = re.search(
        r"^\s+lambdas:\s*\n.*?(?=^\s{2}[a-z][\w-]*:\s*$|\Z)",
        ci, re.MULTILINE | re.DOTALL,
    )
    assert lambdas_match, "Could not locate `lambdas:` job in ci.yml"
    job_text = lambdas_match.group(0)
    # The job must install slsflow before running console_api tests
    assert re.search(r"pip install -e \.", job_text), (
        "Lambda CI job does not `pip install -e .` — console_api tests will "
        "fail on `from slsflow.partitions import ...` with ModuleNotFoundError. "
        "Add `pip install -e .` to the Install dependencies step."
    )


# ───────────────────────────────────────────────────────────────────────────
# Bulk-backfill SFN sanity — Inline Map matches what we model above
# ───────────────────────────────────────────────────────────────────────────


def test_bulk_backfill_uses_inline_map():
    """If someone migrates bulk-backfill to Distributed Map, the history
    budget math above no longer applies — Distributed Map iterations run
    in child executions with their own histories. Detect the change so
    we can re-evaluate PARTITION_HARD_LIMIT.

    ADR #90: the structure is now nested INLINE Maps — an outer TierMap
    (sequential over tiers) wrapping an inner PartitionMap (parallel over a
    tier's items). Both must stay INLINE. The per-item history is unchanged
    from the pre-Phase-3 flat Map; the outer Map only adds a tier-gate
    getItem + Choice per tier, and tiers are few (dependency depth), so the
    PARTITION_HARD_LIMIT budget still holds.
    """
    import json
    text = BULK_BACKFILL_TPL.read_text()
    text = re.sub(r'\$\{[a-zA-Z_]+\}', '0', text)
    t = json.loads(text)
    tier_map = t["States"]["TierMap"]
    outer_mode = tier_map["ItemProcessor"]["ProcessorConfig"]["Mode"]
    inner_mode = (tier_map["ItemProcessor"]["States"]["PartitionMap"]
                  ["ItemProcessor"]["ProcessorConfig"]["Mode"])
    for name, mode in (("TierMap", outer_mode), ("PartitionMap", inner_mode)):
        assert mode == "INLINE", (
            f"{name} mode changed to {mode}. Re-evaluate "
            f"PARTITION_HARD_LIMIT in constants.py — Distributed Map has "
            f"different limits (own execution per iteration, 10k iterations max)."
        )


# ───────────────────────────────────────────────────────────────────────────
# sfn_arn / arn fallback parity — backward compat with legacy registry rows
# ───────────────────────────────────────────────────────────────────────────


def test_sfn_template_has_arn_fallback_parity_with_python():
    """7 places in Python read pipeline_registry with the fallback
    `item.get('sfn_arn') or item.get('arn')` for backward compatibility
    with pre-rename registry rows. The bulk-backfill SFN template reads
    the same row at runtime — it must use the same fallback, otherwise
    legacy rows produce empty ARN → StartExecution fails."""
    text = BULK_BACKFILL_TPL.read_text()
    # Find the Output expression for target_pipeline_sfn_arn
    m = re.search(r"target_pipeline_sfn_arn'?\s*:\s*([^,}]+)", text)
    assert m, "Could not locate target_pipeline_sfn_arn extraction"
    expr = m.group(1)
    assert "sfn_arn" in expr
    assert "arn.S" in expr or "Item.arn" in expr, (
        f"SFN template missing `arn` fallback for legacy rows: {expr}. "
        f"Python code has it in 7 places (dal/pipelines_repo.py + 6 routes). "
        f"Without parity, legacy registry rows yield empty ARN at runtime."
    )


# ───────────────────────────────────────────────────────────────────────────
# Lambda packaging via committed symlink
#
# Live smoke (Mike, 2026-05-22) showed that:
#   1. Lambda-local Makefile with `cp ../../../slsflow` fails — SAM
#      CustomMakeBuilder runs make from a scratch dir, so the relative
#      path can't reach the repo root.
#   2. Top-level `make sam-build` vendor pattern works but introduces an
#      extra build step that surprises users running plain `sam build`.
#
# Final fix: commit a symlink `sam/lambdas/console_api/slsflow → ../../../slsflow`.
# SAM's default Python builder follows the symlink, packaging the SDK
# inline. Zero setup; plain `sam build && sam deploy` just works.
# ───────────────────────────────────────────────────────────────────────────


def test_lambda_has_slsflow_symlink():
    """The symlink is the packaging contract. Removing it breaks runtime
    import of slsflow.partitions / slsflow.granularity in the deployed
    Lambda. Pin its existence."""
    link = REPO_ROOT / "sam" / "lambdas" / "console_api" / "slsflow"
    assert link.is_symlink(), (
        f"{link} must be a symlink to ../../../slsflow. "
        f"Without it, `sam build` packages a Lambda that 500s on /api/backfill "
        f"with ImportError on slsflow.partitions."
    )
    target = link.readlink()
    assert str(target) == "../../../slsflow", (
        f"Symlink target wrong: expected ../../../slsflow, got {target}"
    )
    # And the symlink must resolve to a real directory
    resolved = link.resolve()
    assert resolved.is_dir(), f"Symlink target doesn't exist: {resolved}"
    assert (resolved / "__init__.py").is_file(), (
        f"Symlink points to wrong directory (no __init__.py): {resolved}"
    )


def test_lambda_local_makefile_not_reintroduced():
    """The abandoned Lambda-local Makefile pattern was the source of the
    failed live smoke. It MUST NOT come back."""
    lambda_makefile = REPO_ROOT / "sam" / "lambdas" / "console_api" / "Makefile"
    assert not lambda_makefile.exists(), (
        "Lambda-local Makefile is back. SAM CustomMakeBuilder runs from a "
        "scratch dir, so relative paths can't reach the repo root. The "
        "current packaging contract is the symlink — see "
        "sam/lambdas/console_api/slsflow."
    )


def test_template_has_no_buildmethod_makefile_for_console_api():
    """If BuildMethod: makefile reappears, it implies the broken
    Lambda-local Makefile is being invoked again."""
    template = REPO_ROOT / "sam" / "template.yaml"
    text = template.read_text()
    m = re.search(
        r"ConsoleApiFunction:\s*\n.*?(?=\n  [A-Z][\w]+:\s*\n|\Z)",
        text, re.DOTALL,
    )
    assert m, "Could not locate ConsoleApiFunction block"
    block = m.group(0)
    assert "BuildMethod: makefile" not in block, (
        "ConsoleApiFunction has BuildMethod: makefile — that pattern was "
        "abandoned after the live-smoke failure. Use the symlink instead."
    )
