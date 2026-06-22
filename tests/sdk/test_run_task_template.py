"""
Contract tests for the shared run_task helper SFN template.

This helper is invoked **per task** by every user pipeline ASL. The
external reviewer correctly identified that several backfill options
were silently ignored by the child template because the API plumbed
them through bulk_backfill SFN but run_task didn't read them.

These tests pin the contract so future edits can't silently strip the
skip_tasks Choice or the _suppress_asset_event guard. They are the
sibling of tests/sdk/test_bulk_backfill_template.py.
"""

import json
import re
from pathlib import Path

import pytest

TEMPLATE_PATH = Path(__file__).parent.parent.parent / "sam" / "sfn_templates" / "helpers" / "run_task" / "sfn.tpl.json"


@pytest.fixture(scope="module")
def template() -> dict:
    """Load run_task template (with SAM placeholders normalized for JSON parse)."""
    raw = TEMPLATE_PATH.read_text()
    clean = re.sub(r'\$\{[^}]+\}', '0', raw)
    return json.loads(clean)


def test_jsonata_mode(template):
    """All expression-based contracts below assume JSONata mode."""
    assert template.get("QueryLanguage") == "JSONata"


def test_start_state_is_skip_check(template):
    """The very first state must be the skip_tasks check — otherwise
    skipped tasks would still write status=running, fetch dependencies,
    etc., before being noped out. Regression for ADR #51 task_subset."""
    assert template["StartAt"] == "Check_Should_Skip_Task", (
        f"StartAt must be Check_Should_Skip_Task; got: {template['StartAt']}"
    )


def test_skip_tasks_choice_exists(template):
    """run_task must have a Choice state at the start that compares
    task_name against the skip_tasks list."""
    states = template["States"]
    assert "Check_Should_Skip_Task" in states, (
        "Check_Should_Skip_Task missing — task_subset backfill ignored."
    )
    choice = states["Check_Should_Skip_Task"]
    assert choice["Type"] == "Choice"
    cond = choice["Choices"][0]["Condition"]
    assert "skip_tasks" in cond, f"Condition must reference skip_tasks: {cond}"
    assert "task_name" in cond, f"Condition must reference task_name: {cond}"
    # Must guard against missing field (no NPE for scheduled runs)
    assert "$exists" in cond, (
        f"Condition must use $exists to guard missing skip_tasks: {cond}"
    )


def test_task_skipped_terminal_state(template):
    """Skipped task must reach a terminal state (End: true) emitting
    a synthetic 'skipped' status. Downstream tasks with trigger_rule
    handling skipped (e.g. 'none_failed_or_skipped') rely on this."""
    states = template["States"]
    assert "Task_Skipped" in states
    skipped = states["Task_Skipped"]
    assert skipped["Type"] == "Pass"
    assert skipped.get("End") is True
    output_expr = skipped["Output"]
    assert "'skipped'" in output_expr, (
        f"Skipped output must include status='skipped': {output_expr}"
    )
    assert "task_name" in output_expr


def test_skip_check_default_preserves_existing_flow(template):
    """Critical for backward compat: when skip_tasks empty/missing,
    Default branch must continue to the existing entry point. Otherwise
    every scheduled pipeline run would break."""
    choice = template["States"]["Check_Should_Skip_Task"]
    assert choice["Default"] == "Check_Execution_Paused", (
        f"Default branch must preserve existing flow; got: {choice['Default']}"
    )


def test_emit_asset_events_honors_suppress_flag(template):
    """Check_Has_Outlets must guard Emit_Asset_Events with
    _suppress_asset_event. Regression for cascade='none' backfill
    (ADR #57) — without this, isolated backfills would still emit
    asset events and trigger downstream consumers."""
    states = template["States"]
    choice = states["Check_Has_Outlets"]
    cond = choice["Choices"][0]["Condition"]
    assert "_suppress_asset_event" in cond, (
        f"Check_Has_Outlets condition must check _suppress_asset_event for cascade='none' backfill semantics: {cond}"
    )
    # Default must still skip to next state without emitting (existing flow)
    assert choice["Default"] == "Check_Orchestration_Token_Success"


def test_pause_check_still_runs_for_normal_tasks(template):
    """After the skip check, normal tasks must still hit Check_Execution_Paused
    so pause/resume semantics are preserved."""
    states = template["States"]
    assert "Check_Execution_Paused" in states
    # Route_Pause_Check still leads to Update_Status_Running (existing flow)
    assert states["Route_Pause_Check"]["Default"] == "Update_Status_Running"


def test_no_orphan_states(template):
    """All declared states must be reachable from StartAt. Catches typos
    in Next/Default that would create unreachable code."""
    states = template["States"]
    reachable = set()

    def walk(state_name):
        if state_name in reachable or state_name not in states:
            return
        reachable.add(state_name)
        s = states[state_name]
        # Linear next
        for k in ("Next", "Default"):
            if k in s and isinstance(s[k], str):
                walk(s[k])
        # Choice branches
        for c in s.get("Choices", []):
            if isinstance(c.get("Next"), str):
                walk(c["Next"])
        # Catch
        for c in s.get("Catch", []):
            if isinstance(c.get("Next"), str):
                walk(c["Next"])
        # Map nested
        if s.get("ItemProcessor", {}).get("States"):
            # Sub-states are independent — just verify they're walkable too
            sub_states = s["ItemProcessor"]["States"]
            sub_start = s["ItemProcessor"]["StartAt"]
            sub_reachable = set()
            def walk_sub(name):
                if name in sub_reachable or name not in sub_states:
                    return
                sub_reachable.add(name)
                ss = sub_states[name]
                for k in ("Next", "Default"):
                    if k in ss and isinstance(ss[k], str):
                        walk_sub(ss[k])
                for c in ss.get("Choices", []):
                    if isinstance(c.get("Next"), str):
                        walk_sub(c["Next"])
            walk_sub(sub_start)
            unreachable_sub = set(sub_states.keys()) - sub_reachable
            assert not unreachable_sub, (
                f"Map sub-states unreachable in {state_name}: {unreachable_sub}"
            )

    walk(template["StartAt"])
    orphans = set(states.keys()) - reachable
    assert not orphans, f"Unreachable top-level states: {orphans}"
