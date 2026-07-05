"""
Tests for stop_task and restart_task.

stop_task:
- Running → stopped (can be restarted)
- Waiting → aborted (terminal, sends callback, notifies dependents)
- Terminal → 409
- Race condition → 409, no side-effects

restart_task:
- Terminal → restart initiated (SFN helper)
- Non-terminal → 409
- No restart helper ARN → fallback reset
"""

import json
import os
from botocore.exceptions import ClientError

os.environ.setdefault('DYNAMODB_TABLE', 'test-tokens')
os.environ.setdefault('PIPELINES_TABLE', 'test-registry')
os.environ.setdefault('TASK_EVENTS_TABLE', 'test-events')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')


def _conditional_check_failed():
    return ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Condition not met'}}, 'UpdateItem'
    )


def _make_item(status='running'):
    return {
        'execution_name': 'extract-2026-02-20-abc12345',
        'task_name': 'extract',
        'status': status,
        'pipeline_name': 'test_pipeline',
        'pipeline_execution': 'arn:aws:states:us-east-1:123:execution:test:exec-1',
        'pipeline_execution_short': 'exec-1',
        'date': '2026-02-20',
        'orchestration_token': 'tok-123',
        'task_run_id': 'extract-2026-02-20-abc12345',
        'wrapper_execution_arn': 'arn:aws:states:us-east-1:123:execution:wrapper:extract-123',
    }


def _make_event(date='2026-02-20'):
    return {'body': json.dumps({'date': date})}


# ============================================================
# stop_task
# ============================================================


def test_stop_running_returns_stopped(mocker):
    """Running task → stopped status (not aborted)."""
    from routes.tasks import stop_task

    item = _make_item(status='running')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop_exec = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mock_repo = mocker.patch('routes.tasks.executions_repo')
    mock_repo.update.return_value = {}

    response = stop_task('extract', _make_event())

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'stopped'
    mock_stop_exec.assert_called_once()
    mock_record.assert_called_once()


def test_stop_waiting_returns_aborted(mocker):
    """Waiting task → aborted status (terminal), sends callback."""
    from routes.tasks import stop_task

    item = _make_item(status='waiting_decision')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mocker.patch('routes.tasks.stop_task_executions')
    mocker.patch('routes.tasks.record_manual_decision')
    mock_notify = mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mock_repo = mocker.patch('routes.tasks.executions_repo')
    mock_repo.update.return_value = {}
    mock_sfn = mocker.patch('routes.tasks.sfn')

    response = stop_task('extract', _make_event())

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'aborted'
    mock_sfn.send_task_failure.assert_called_once()
    mock_notify.assert_called_once()


def test_stop_terminal_returns_409(mocker):
    """Already terminal → 409 conflict."""
    from routes.tasks import stop_task

    item = _make_item(status='success')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))

    response = stop_task('extract', _make_event())

    assert response['statusCode'] == 409
    assert 'terminal' in json.loads(response['body'])['error'].lower()


def test_stop_not_found_returns_404(mocker):
    """Task not found → 404."""
    from routes.tasks import stop_task

    mocker.patch('routes.tasks.resolve_task_item', return_value=(None, None))

    response = stop_task('nonexistent', _make_event())

    assert response['statusCode'] == 404


# ============================================================
# restart_task
# ============================================================


def test_restart_terminal_task_with_helper(mocker):
    """Terminal task + RESTART_HELPER_ARN → starts restart SFN."""
    from routes.tasks import restart_task

    item = _make_item(status='failed')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mock_sfn = mocker.patch('routes.tasks.sfn')
    mock_sfn.start_execution.return_value = {'executionArn': 'arn:aws:states:us-east-1:123:execution:restart:r-123'}
    mocker.patch.dict(os.environ, {'RESTART_HELPER_ARN': 'arn:restart-helper'})

    response = restart_task('extract', _make_event())

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert 'execution_arn' in body
    mock_sfn.start_execution.assert_called_once()
    mock_record.assert_called_once()


def test_restart_non_terminal_returns_409(mocker):
    """Non-terminal task → 409 conflict."""
    from routes.tasks import restart_task

    item = _make_item(status='running')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))

    response = restart_task('extract', _make_event())

    assert response['statusCode'] == 409
    assert 'not in terminal state' in json.loads(response['body'])['error'].lower()


def test_restart_not_found_returns_404(mocker):
    """Task not found → 404."""
    from routes.tasks import restart_task

    mocker.patch('routes.tasks.resolve_task_item', return_value=(None, None))

    response = restart_task('nonexistent', _make_event())

    assert response['statusCode'] == 404


def test_restart_fallback_resets_status(mocker):
    """No RESTART_HELPER_ARN → fallback: reset status to waiting."""
    from routes.tasks import restart_task

    item = _make_item(status='failed')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mocker.patch('routes.tasks.record_manual_decision')
    mock_stop_exec = mocker.patch('routes.tasks.stop_task_executions')
    mock_repo = mocker.patch('routes.tasks.executions_repo')
    mock_repo.update.return_value = {}

    os.environ.pop('RESTART_HELPER_ARN', None)
    response = restart_task('extract', _make_event())

    assert response['statusCode'] == 200
    mock_repo.update.assert_called_once()
    mock_stop_exec.assert_called_once()
