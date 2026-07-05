"""
Idempotency tests for manual task actions (free UI intervention, ADR #110).

Verifies claim-first ordering: when DDB conditional update fails (race condition),
stop_task_executions and record_manual_decision must NOT be called.

After DAL migration (v69.3), routes call executions_repo.update() / .get()
directly — not repo.table.update_item() / .table.get_item().
"""

import json
import os
from botocore.exceptions import ClientError

os.environ.setdefault('DYNAMODB_TABLE', 'test-tokens')
os.environ.setdefault('PIPELINES_TABLE', 'test-registry')
os.environ.setdefault('TASK_EVENTS_TABLE', 'test-events')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')


def _conditional_check_failed():
    """Create a ConditionalCheckFailedException."""
    return ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Condition not met'}}, 'UpdateItem'
    )


def _make_task_item(status='waiting_decision'):
    """Create a minimal task item for testing."""
    return {
        'execution_name': 'test-task-2026-02-20-abc12345',
        'task_name': 'test_task',
        'status': status,
        'pipeline_name': 'test_pipeline',
        'pipeline_execution': 'arn:aws:states:us-east-1:123:execution:test:exec-1',
        'pipeline_execution_short': 'exec-1',
        'date': '2026-02-20',
        'orchestration_token': 'tok-123',
        'task_run_id': 'test-task-2026-02-20-abc12345',
        'parent_execution_id': 'exec-1',
    }


def _mock_repo_with_update_failure(mocker, item):
    """Create a mock executions_repo where .get() returns item but .update() raises."""
    mock = mocker.MagicMock()
    mock.get.return_value = item
    mock.update.side_effect = _conditional_check_failed()
    return mock


def _mock_repo_success(mocker, item):
    """Create a mock executions_repo where .get() returns item and .update() succeeds."""
    mock = mocker.MagicMock()
    mock.get.return_value = item
    mock.update.return_value = {}
    return mock


# ============================================================
# UI actions: claim-first prevents side-effects on race
# ============================================================


def test_skip_task_no_side_effects_on_race(mocker):
    """skip_task: if conditional update fails, stop/record must NOT be called."""
    from routes.tasks import skip_task

    item = _make_task_item()
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.executions_repo', _mock_repo_with_update_failure(mocker, item))

    response = skip_task('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 409
    assert 'error' in json.loads(response['body'])
    mock_stop.assert_not_called()
    mock_record.assert_not_called()


def test_fail_task_no_side_effects_on_race(mocker):
    """fail_task: if conditional update fails, stop/record must NOT be called."""
    from routes.tasks import fail_task

    item = _make_task_item()
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.executions_repo', _mock_repo_with_update_failure(mocker, item))

    response = fail_task('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 409
    mock_stop.assert_not_called()
    mock_record.assert_not_called()


def test_mark_success_no_side_effects_on_race(mocker):
    """mark_success: if conditional update fails, stop/record must NOT be called."""
    from routes.tasks import mark_success

    item = _make_task_item()
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.executions_repo', _mock_repo_with_update_failure(mocker, item))

    response = mark_success('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 409
    mock_stop.assert_not_called()
    mock_record.assert_not_called()


def test_stop_task_no_side_effects_on_race(mocker):
    """stop_task: if conditional update fails, stop/record must NOT be called."""
    from routes.tasks import stop_task

    item = _make_task_item(status='running')
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.executions_repo', _mock_repo_with_update_failure(mocker, item))

    response = stop_task('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 409
    mock_stop.assert_not_called()
    mock_record.assert_not_called()


# ============================================================
# UI actions: happy path DOES call side-effects after claim
# ============================================================


def test_skip_task_happy_path_calls_side_effects(mocker):
    """skip_task: on successful claim, stop and record ARE called."""
    from routes.tasks import skip_task

    item = _make_task_item()
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.resolve_pagerduty')
    mocker.patch('routes.tasks.sfn')
    mocker.patch('routes.tasks.executions_repo', _mock_repo_success(mocker, item))

    response = skip_task('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 200
    mock_stop.assert_called_once()
    mock_record.assert_called_once()


def test_fail_task_happy_path_calls_side_effects(mocker):
    """fail_task: on successful claim, stop and record ARE called."""
    from routes.tasks import fail_task

    item = _make_task_item()
    mocker.patch('routes.tasks.resolve_task_item', return_value=(item, item['execution_name']))
    mock_stop = mocker.patch('routes.tasks.stop_task_executions')
    mock_record = mocker.patch('routes.tasks.record_manual_decision')
    mocker.patch('routes.tasks.notify_dependents_via_sfn', return_value=True)
    mocker.patch('routes.tasks.resolve_pagerduty')
    mocker.patch('routes.tasks.sfn')
    mocker.patch('routes.tasks.executions_repo', _mock_repo_success(mocker, item))

    response = fail_task('test_task', {'body': json.dumps({'date': '2026-02-20'})})

    assert response['statusCode'] == 200
    mock_stop.assert_called_once()
    mock_record.assert_called_once()
