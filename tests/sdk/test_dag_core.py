"""DAG-object tests — scheduling, alerts validation, graph methods.

Drives ``polyris.dag.DAG`` directly (CLAUDE.md #13):

  - ``__post_init__`` validation: the alerts-shape checks (still live even
    though ``alerts=`` is deprecated/ignored at runtime), the
    ``schedule_interval`` alias, and ``trigger_assets`` → asset schedule.
  - Graph methods: ``topological_sort`` (ordering + cycle detection),
    ``roots``, ``leaves``, ``get_task`` / ``task_dict``.
  - The Airflow-compat ``test()`` / ``cli()`` helpers.
"""
from __future__ import annotations

import pytest

from polyris import DAG, task, Asset

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:test"


def _chain():
    """a >> b >> c; returns (dag, a, b, c) as Task objects."""
    with DAG("dag_chain", schedule=None) as dag:
        @task.sfn(arn=ARN)
        def a():
            pass

        @task.sfn(arn=ARN)
        def b():
            pass

        @task.sfn(arn=ARN)
        def c():
            pass

        a() >> b() >> c()
    return dag, a, b, c


# ============================================================ #
# scheduling + alerts validation (__post_init__)
# ============================================================ #
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestSchedulingAndAlerts:
    def test_alerts_must_be_dict(self):
        with pytest.raises(ValueError, match="must be a dict"):
            DAG("d", schedule=None, alerts="not-a-dict")

    def test_alerts_reject_unknown_keys(self):
        with pytest.raises(ValueError, match="Invalid alerts keys"):
            DAG("d", schedule=None, alerts={"bogus": 1})

    def test_alerts_pagerduty_severity_validated(self):
        with pytest.raises(ValueError, match="Invalid pagerduty severity"):
            DAG("d", schedule=None, alerts={"pagerduty": "meltdown"})

    def test_alerts_slack_channel_prefix_validated(self):
        with pytest.raises(ValueError, match="must start with"):
            DAG("d", schedule=None, alerts={"slack": "nohash"})

    def test_alerts_slack_mentions_must_be_list(self):
        with pytest.raises(ValueError, match="must be a list"):
            DAG("d", schedule=None, alerts={"slack_mentions": "U123"})

    def test_alerts_slack_mentions_items_must_be_strings(self):
        with pytest.raises(ValueError, match="must be strings"):
            DAG("d", schedule=None, alerts={"slack_mentions": [123]})

    def test_alerts_slack_mentions_entry_format_validated(self):
        with pytest.raises(ValueError, match="Invalid slack_mentions entry"):
            DAG("d", schedule=None, alerts={"slack_mentions": ["nonsense"]})

    def test_valid_alerts_accepted_and_slack_channel_populated(self):
        with pytest.warns(DeprecationWarning):
            dag = DAG("d", schedule=None, alerts={
                "slack": "#alerts",
                "slack_mentions": ["U123", "here"],
                "pagerduty": "critical",
            })
        # Legacy back-compat: slack_channel is filled from alerts.slack.
        assert dag.slack_channel == "#alerts"

    def test_schedule_interval_alias(self):
        dag = DAG("d", schedule_interval="rate(1 hour)")
        assert dag.schedule == "rate(1 hour)"
        assert dag.is_asset_triggered is False

    def test_trigger_assets_any_makes_asset_triggered(self):
        dag = DAG("d", trigger_assets=[Asset("ns/x")], trigger_mode="any")
        assert dag.is_asset_triggered is True
        assert "ns/x" in str(dag.asset_schedule_info)

    def test_trigger_assets_all_is_default(self):
        dag = DAG("d", trigger_assets=[Asset("ns/x"), Asset("ns/y")])
        assert dag.is_asset_triggered is True
        info = str(dag.asset_schedule_info)
        assert "ns/x" in info and "ns/y" in info

    def test_asset_schedule_via_single_asset(self):
        dag = DAG("d", schedule=Asset("ns/z"))
        assert dag.is_asset_triggered is True


# ============================================================ #
# graph methods
# ============================================================ #
class TestGraphMethods:
    def test_topological_sort_orders_deps_first(self):
        dag, a, b, c = _chain()
        order = [t.task_id for t in dag.topological_sort()]
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_sort_detects_cycle(self):
        with DAG("dag_cycle", schedule=None) as dag:
            @task.sfn(arn=ARN)
            def a():
                pass

            @task.sfn(arn=ARN)
            def b():
                pass

            ai, bi = a(), b()
            ai >> bi
            bi >> ai  # close the loop
        with pytest.raises(ValueError, match="Cycle detected"):
            dag.topological_sort()

    def test_roots_have_no_task_deps(self):
        dag, a, b, c = _chain()
        assert [t.task_id for t in dag.roots()] == ["a"]

    def test_leaves_have_no_downstream(self):
        dag, a, b, c = _chain()
        assert [t.task_id for t in dag.leaves()] == ["c"]

    def test_get_task_hit_and_miss(self):
        dag, a, b, c = _chain()
        assert dag.get_task("a") is a
        assert dag.get_task("does-not-exist") is None

    def test_task_dict_maps_ids(self):
        dag, a, b, c = _chain()
        assert set(dag.task_dict.keys()) == {"a", "b", "c"}


# ============================================================ #
# Airflow-compat helpers
# ============================================================ #
class TestCompatHelpers:
    def test_cli_is_noop(self):
        dag, *_ = _chain()
        assert dag.cli() is None

    def test_test_runs_callables(self, capsys):
        dag, *_ = _chain()
        dag.test()
        out = capsys.readouterr().out
        assert "Testing DAG" in out

    def test_test_catches_callable_errors(self, capsys):
        with DAG("dag_boom", schedule=None) as dag:
            @task.sfn(arn=ARN)
            def boom():
                raise RuntimeError("kaboom")
            boom()
        dag.test()  # must not propagate — the runner catches and prints
        assert "Error" in capsys.readouterr().out
