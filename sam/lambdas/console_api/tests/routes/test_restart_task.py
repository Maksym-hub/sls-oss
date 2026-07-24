"""Tests for routes.tasks.restart_task.

No test file existed for this function before. Regression tests here cover
a real, high-impact bug found in a code-review pass: restart_task's own
precondition check only accepted TASK_TERMINAL_STATUSES (success, failed,
skipped, aborted, upstream_failed, succeeded) — it did NOT accept 'stopped'.
But stop_task's own success message tells the user "Use Restart to resume",
and stop_task deliberately treats 'stopped' as non-terminal/resumable (not
in TASK_TERMINAL_STATUSES on purpose). So the advertised "stop, then
restart" workflow was completely non-functional: any user who stopped a
task and then tried to restart it, exactly as told, got a 409 saying their
task "is not in a restartable state" — contradicting the message they had
just followed.
"""
import json

import pytest

from routes.tasks import restart_task


def _item(status="failed", **overrides):
    base = {
        "execution_name": "extract-2024-01-15-abc12345",
        "task_name": "extract",
        "status": status,
        "date": "2024-01-15",
        "pipeline_execution": "run1",
    }
    base.update(overrides)
    return base


def _event(date="2024-01-15"):
    return {"body": json.dumps({"date": date})}


def _body(resp):
    return json.loads(resp["body"])


@pytest.fixture
def no_sfn_helper(monkeypatch):
    """Force the fallback (non-SFN-helper) restart path."""
    monkeypatch.delenv("RESTART_HELPER_ARN", raising=False)


@pytest.fixture
def with_sfn_helper(monkeypatch):
    monkeypatch.setenv("RESTART_HELPER_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:restart-helper")


class TestRestartTaskAcceptsStoppedStatus:
    """The exact bug: 'stopped' must be restartable via BOTH code paths."""

    def test_stopped_task_restartable_via_fallback_path(self, mocker, no_sfn_helper):
        item = _item(status="stopped")
        mocker.patch("routes.tasks.resolve_task_item", return_value=(item, item["execution_name"]))
        mocker.patch("routes.tasks.record_manual_decision")
        mocker.patch("routes.tasks.stop_task_executions")
        update_mock = mocker.patch("routes.tasks.executions_repo.update")

        resp = restart_task(item["execution_name"], _event())

        assert resp["statusCode"] == 200
        assert "reset" in _body(resp)["message"]
        # The DynamoDB call must actually supply a value for :stopped, since
        # RESTART_CONDITION references it — a placeholder with no value
        # would be rejected by DynamoDB itself.
        call_kwargs = update_mock.call_args.kwargs
        assert ":stopped" in call_kwargs["expr_values"]
        assert call_kwargs["expr_values"][":stopped"] == "stopped"
        assert ":stopped" in call_kwargs["condition_expr"]

    def test_stopped_task_restartable_via_sfn_helper_path(self, mocker, with_sfn_helper):
        item = _item(status="stopped")
        mocker.patch("routes.tasks.resolve_task_item", return_value=(item, item["execution_name"]))
        mocker.patch("routes.tasks.record_manual_decision")
        mocker.patch("routes.tasks.sfn.start_execution",
                      return_value={"executionArn": "arn:aws:states:us-east-1:123456789012:execution:x:y"})

        resp = restart_task(item["execution_name"], _event())

        assert resp["statusCode"] == 200
        assert "Restart initiated" in _body(resp)["message"]


class TestRestartTaskStillAcceptsTerminalStatuses:
    """Control: every status that worked before must keep working."""

    @pytest.mark.parametrize("status", ["success", "failed", "skipped", "aborted", "upstream_failed"])
    def test_each_terminal_status_is_restartable(self, mocker, no_sfn_helper, status):
        item = _item(status=status)
        mocker.patch("routes.tasks.resolve_task_item", return_value=(item, item["execution_name"]))
        mocker.patch("routes.tasks.record_manual_decision")
        mocker.patch("routes.tasks.stop_task_executions")
        mocker.patch("routes.tasks.executions_repo.update")

        resp = restart_task(item["execution_name"], _event())

        assert resp["statusCode"] == 200


class TestRestartTaskRejectsNonRestartableStatuses:
    """Statuses that genuinely cannot be restarted must still 409."""

    @pytest.mark.parametrize("status", ["running", "waiting", "waiting_delay", "deps_ready"])
    def test_active_statuses_rejected(self, mocker, no_sfn_helper, status):
        item = _item(status=status)
        mocker.patch("routes.tasks.resolve_task_item", return_value=(item, item["execution_name"]))

        resp = restart_task(item["execution_name"], _event())

        assert resp["statusCode"] == 409
        assert status in _body(resp)["error"]

    def test_task_not_found_returns_404(self, mocker, no_sfn_helper):
        mocker.patch("routes.tasks.resolve_task_item", return_value=(None, None))

        resp = restart_task("nonexistent", _event())

        assert resp["statusCode"] == 404
