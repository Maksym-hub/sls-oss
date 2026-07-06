"""Generator-engine tests — ASL validation + the public generation surface.

Two clusters, both driving real code paths (CLAUDE.md #13):

  1. ``validate_asl`` — the Amazon States Language validator. Exercised with
     hand-built ASL dicts covering every structural rule it enforces
     (missing fields, bad transitions, Choice/Parallel/Map shape,
     reachability, terminal states).

  2. The public generation functions (``generate_step_function_json``,
     ``generate_dag_json``, ``generate_mermaid``, asset/EventBridge JSON,
     debug info, hashing) — driven from real DAGs built with the public DSL.
     A key property test asserts that the machine we *generate* is itself
     *valid* under ``validate_asl``.
"""
from __future__ import annotations

import json

from polyris.generators import (
    validate_asl,
    generate_step_function_json,
    generate_dag_json,
    generate_dag_hash,
    generate_mermaid,
    generate_debug_info,
    generate_eventbridge_schedule,
    generate_assets_json,
    generate_all_assets,
    generate_asset_eventbridge_rules,
)

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:test"


def _asl(states, start="A"):
    return {"StartAt": start, "States": states}


# ============================================================ #
# validate_asl
# ============================================================ #
class TestValidateAsl:
    def test_valid_minimal_machine(self):
        ok, errors, warnings = validate_asl(_asl({"A": {"Type": "Pass", "End": True}}))
        assert ok is True
        assert errors == []
        assert warnings == []

    def test_missing_start_at_errors(self):
        ok, errors, _ = validate_asl({"States": {"A": {"Type": "Pass", "End": True}}})
        assert ok is False
        assert any("StartAt" in e for e in errors)

    def test_missing_states_short_circuits(self):
        ok, errors, warnings = validate_asl({"StartAt": "A"})
        assert ok is False
        assert any("States" in e for e in errors)
        assert warnings == []  # returns immediately, no further checks

    def test_start_at_nonexistent_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Pass", "End": True}}, start="X"))
        assert ok is False
        assert any("does not exist" in e for e in errors)

    def test_state_missing_type_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"End": True}}))
        assert ok is False
        assert any("Missing required field 'Type'" in e for e in errors)

    def test_invalid_state_type_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Nonsense", "End": True}}))
        assert ok is False
        assert any("Invalid Type" in e for e in errors)

    def test_succeed_with_next_warns(self):
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Succeed", "Next": "B"},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is True  # only a warning, not an error
        assert any("should not have 'Next'" in w for w in warnings)

    def test_choice_without_choices_errors(self):
        ok, errors, _ = validate_asl(_asl({
            "A": {"Type": "Choice", "Default": "B"},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is False
        assert any("missing 'Choices'" in e for e in errors)

    def test_choice_branch_without_next_errors(self):
        ok, errors, _ = validate_asl(_asl({
            "A": {"Type": "Choice", "Choices": [{"Variable": "x"}], "Default": "B"},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is False
        assert any("Choice[0] missing 'Next'" in e for e in errors)

    def test_choice_without_default_warns(self):
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Choice", "Choices": [{"Next": "B"}]},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is True
        assert any("Choice without 'Default'" in w for w in warnings)

    def test_choice_with_default_no_default_warning(self):
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Choice", "Choices": [{"Next": "B"}], "Default": "B"},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is True
        assert not any("Choice without 'Default'" in w for w in warnings)

    def test_state_without_end_or_next_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Task"}}))
        assert ok is False
        assert any("Must have either 'End' or 'Next'" in e for e in errors)

    def test_both_end_and_next_warns(self):
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Task", "End": True, "Next": "B"},
            "B": {"Type": "Pass", "End": True},
        }))
        assert ok is True
        assert any("Has both 'End' and 'Next'" in w for w in warnings)

    def test_next_to_nonexistent_state_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Task", "Next": "Z"}}))
        assert ok is False
        assert any("non-existent state 'Z'" in e for e in errors)

    def test_unreachable_state_warns(self):
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Pass", "End": True},
            "B": {"Type": "Pass", "End": True},  # never referenced
        }))
        assert ok is True
        assert any("unreachable" in w for w in warnings)

    def test_no_terminal_states_warns(self):
        # A Choice that only loops back to itself — reachable, valid, but no
        # End/Succeed/Fail anywhere.
        ok, _errors, warnings = validate_asl(_asl({
            "A": {"Type": "Choice", "Choices": [{"Next": "A"}], "Default": "A"},
        }))
        assert ok is True
        assert any("No terminal states" in w for w in warnings)

    def test_parallel_without_branches_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Parallel", "End": True}}))
        assert ok is False
        assert any("no branches" in e for e in errors)

    def test_parallel_branch_errors_bubble_up(self):
        ok, errors, _ = validate_asl(_asl({
            "A": {
                "Type": "Parallel", "End": True,
                "Branches": [{"StartAt": "X", "States": {"X": {"End": True}}}],  # X missing Type
            },
        }))
        assert ok is False
        assert any("Branch[0]" in e for e in errors)

    def test_map_without_iterator_errors(self):
        ok, errors, _ = validate_asl(_asl({"A": {"Type": "Map", "End": True}}))
        assert ok is False
        assert any("missing 'Iterator' or 'ItemProcessor'" in e for e in errors)

    def test_map_with_item_processor_validates(self):
        ok, errors, _ = validate_asl(_asl({
            "A": {
                "Type": "Map", "End": True,
                "ItemProcessor": {"StartAt": "X", "States": {"X": {"Type": "Pass", "End": True}}},
            },
        }))
        assert ok is True
        assert errors == []


# ============================================================ #
# public generation surface (driven from real DAGs)
# ============================================================ #
def _chain_dag():
    from polyris import DAG, task

    with DAG("gen_chain", schedule=None) as dag:
        @task.sfn(arn=ARN)
        def extract():
            pass

        @task.sfn(arn=ARN)
        def load():
            pass

        extract() >> load()
    return dag


def _scheduled_dag():
    from polyris import DAG, task

    with DAG("gen_sched", schedule="rate(1 hour)") as dag:
        @task.sfn(arn=ARN)
        def run():
            pass
        run()
    return dag


def _asset_dag():
    from polyris import DAG, task, Asset, Column, types as t

    orders = Asset(name="shop/orders", schema=[Column("id", t.bigint()), Column("ts", t.date())])
    with DAG("gen_assets", schedule=None) as dag:
        @task.sfn(arn=ARN, outlets=[orders])
        def make():
            pass
        make()
    return dag


class TestPublicGeneration:
    def test_generated_machine_is_valid_asl(self):
        # The generator must emit a machine that passes our own ASL validator.
        asl = json.loads(generate_step_function_json(_chain_dag()))
        ok, errors, _ = validate_asl(asl)
        assert ok is True, errors

    def test_generate_dag_json_includes_dag_id(self):
        result = generate_dag_json(_chain_dag())
        assert isinstance(result, dict)
        assert "gen_chain" in json.dumps(result)

    def test_generate_dag_hash_is_deterministic(self):
        h1 = generate_dag_hash(_chain_dag())
        h2 = generate_dag_hash(_chain_dag())
        assert isinstance(h1, str) and h1
        assert h1 == h2

    def test_generate_mermaid_renders_graph(self):
        out = generate_mermaid(_chain_dag())
        assert isinstance(out, str)
        assert "graph" in out.lower()

    def test_generate_debug_info_returns_structure(self):
        info = generate_debug_info(_chain_dag())
        assert isinstance(info, dict)
        assert info  # non-empty

    def test_generate_eventbridge_schedule_for_scheduled_dag(self):
        sched = generate_eventbridge_schedule(_scheduled_dag())
        assert isinstance(sched, dict)
        assert "rate(1 hour)" in json.dumps(sched)

    def test_generate_assets_json_contains_asset(self):
        out = generate_assets_json(_asset_dag())
        assert "shop/orders" in out

    def test_generate_all_assets_aggregates(self):
        result = generate_all_assets([_asset_dag()])
        assert isinstance(result, dict)
        assert "shop/orders" in json.dumps(result)

    def test_generate_asset_eventbridge_rules_runs(self):
        rules = generate_asset_eventbridge_rules([_asset_dag()])
        assert isinstance(rules, dict)
