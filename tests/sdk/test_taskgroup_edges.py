"""TaskGroup operator edges — Task-in-list, group << Task, unsupported operands.

Closes the remaining ``TaskGroup`` operator branches (CLAUDE.md #13): a bare
``Task`` object as a downstream list element, ``group << task`` wiring the task
ahead of every root, and the ``NotImplemented`` returns for unsupported operands.
"""
from __future__ import annotations

import pytest

from polyris import DAG, task
from polyris.task_group import TaskGroup

ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:test"


def _group_with_inner(dag):
    with TaskGroup("g") as grp:
        @task.sfn(arn=ARN)
        def inner():
            pass
        inner()
    return grp


class TestTaskGroupOperatorEdges:
    def test_group_rshift_task_in_list(self):
        with DAG("tg1", schedule=None):
            grp = _group_with_inner("tg1")

            @task.sfn(arn=ARN)
            def after():
                pass
            grp >> [after]  # bare Task in the list → Task branch
        assert grp.leaves[0] in after.dependencies

    def test_group_rshift_unsupported_raises(self):
        with DAG("tg2", schedule=None):
            grp = _group_with_inner("tg2")
        with pytest.raises(TypeError):
            grp >> 42

    def test_group_lshift_task(self):
        with DAG("tg3", schedule=None):
            grp = _group_with_inner("tg3")

            @task.sfn(arn=ARN)
            def before():
                pass
            grp << before  # Task connects ahead of every root
        assert before in grp.roots[0].dependencies

    def test_group_lshift_unsupported_raises(self):
        with DAG("tg4", schedule=None):
            grp = _group_with_inner("tg4")
        with pytest.raises(TypeError):
            grp << 42
