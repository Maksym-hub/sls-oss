"""Operator edge-case tests — list branches, unsupported operands, registration.

Closes the remaining operator branches in ``steps`` and ``task`` (CLAUDE.md #13):
the list-of-mixed-targets paths, the ``NotImplemented`` returns for unsupported
operands (which surface as ``TypeError``), and the ``if dag: dag.add_step(self)``
registration branch reached only when a control-flow step is built inside a DAG.
"""
from __future__ import annotations

import pytest

from polyris import DAG, task
from polyris.task_group import TaskGroup
from polyris.steps import Wait, Pass, Choice, Map, Sensor, ShortCircuit, Succeed

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:test"


def _two_tasks(dag_id="ope"):
    with DAG(dag_id, schedule=None):
        @task.sfn(arn=ARN)
        def a():
            pass

        @task.sfn(arn=ARN)
        def b():
            pass
    return a, b


# ============================================================ #
# Step operators — list + unsupported operands
# ============================================================ #
class TestStepOperatorEdges:
    def test_rshift_list_of_task_instances(self):
        a, b = _two_tasks()
        w = Wait(seconds=5)
        w >> [a(), b()]  # TaskInstances in a list → hasattr('task') branch
        assert w in a.dependencies and w in b.dependencies

    def test_rshift_unsupported_raises(self):
        with pytest.raises(TypeError):
            Wait(seconds=5) >> 42

    def test_lshift_list(self):
        a, b = _two_tasks()
        p = Pass()
        p << [a, b]
        assert a in p.dependencies and b in p.dependencies

    def test_lshift_unsupported_raises(self):
        with pytest.raises(TypeError):
            Pass() << 42

    def test_rrshift_unsupported_raises(self):
        with pytest.raises(TypeError):
            42 >> Pass()


# ============================================================ #
# Control-flow steps register when built inside a DAG
# ============================================================ #
class TestStepRegistrationInsideDag:
    def test_steps_register_with_active_dag(self):
        with DAG("reg", schedule=None) as dag:
            Choice(default=Pass())
            Map(items_path="$.x")
            Sensor(sensor_type="s3")
            ShortCircuit()
            Succeed()
        step_ids = {s.step_id for s in dag.steps}
        assert {"Choice", "Map", "Sensor_s3", "ShortCircuit", "Succeed"} <= step_ids


# ============================================================ #
# TaskInstance operators — TaskGroup, step-in-list, unsupported
# ============================================================ #
class TestTaskInstanceOperatorEdges:
    def test_ti_rshift_taskgroup(self):
        with DAG("tig", schedule=None):
            @task.sfn(arn=ARN)
            def up():
                pass

            with TaskGroup("g") as grp:
                @task.sfn(arn=ARN)
                def inner():
                    pass
                inner()
            up() >> grp
        assert any(d.task_id == "up" for d in grp.roots[0].dependencies)

    def test_ti_rshift_step_in_list(self):
        with DAG("tis", schedule=None):
            @task.sfn(arn=ARN)
            def up():
                pass
            s = Pass()
            up() >> [s]
        assert any(getattr(d, "task_id", None) == "up" for d in s.dependencies)

    def test_step_in_list_rshift_ti(self):
        with DAG("sli", schedule=None):
            @task.sfn(arn=ARN)
            def down():
                pass
            s = Pass()
            [s] >> down()
        assert s in down.dependencies

    def test_ti_rrshift_unsupported_raises(self):
        with DAG("tir", schedule=None):
            @task.sfn(arn=ARN)
            def down():
                pass
            inst = down()
        with pytest.raises(TypeError):
            42 >> inst


# ============================================================ #
# Task (decorated, pre-call) operators
# ============================================================ #
class TestTaskOperatorEdges:
    def test_task_rshift_unsupported_raises(self):
        a, _ = _two_tasks()
        with pytest.raises(TypeError):
            a >> 42

    def test_task_lshift_list(self):
        a, b = _two_tasks()
        a << [b]
        assert b in a.dependencies

    def test_task_lshift_unsupported_raises(self):
        a, _ = _two_tasks()
        with pytest.raises(TypeError):
            a << 42

    def test_task_rrshift_unsupported_raises(self):
        a, _ = _two_tasks()
        with pytest.raises(TypeError):
            42 >> a

    def test_lambda_without_target_raises(self):
        with pytest.raises(ValueError):
            task.lambda_()
