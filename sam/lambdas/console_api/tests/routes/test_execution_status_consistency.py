"""Cross-endpoint execution-status consistency (ADR #112).

The bug that motivated ADR #112: the same stopped execution showed 'aborted' on the
/runs feed (get_all_runs) but 'failed' in the execution-history dropdown
(get_pipeline_executions), because each endpoint hand-derived the status from its task
statuses with drifted rules. Both now share polyris' derive_execution_status; this test
locks it — identical task rows must yield an identical execution status from both
endpoints. No test previously asserted this, which is why the drift went unnoticed.

pytest-mock (ADR #26); mock only at the repo boundary. SFN reconciliation is disabled by
returning no pipeline ARN, so the pure DynamoDB derivation is what's compared.
"""
import json

import pytest


def _task_rows(statuses, pe='p-2024-01-15-abc', pipeline='test-pipeline', date='2024-01-15'):
    """One execution's task rows (same pipeline_execution, one row per task status)."""
    return [
        {
            'execution_name': f'{pipeline}-task{i}-{date}',
            'pipeline_execution': pe,
            'pipeline_execution_short': pe[-8:],
            'pipeline_name': pipeline,
            'status': s,
            'date': date,
            'started_at': '2024-01-15T10:00:00Z',
            'finished_at': '2024-01-15T10:05:00Z',
        }
        for i, s in enumerate(statuses)
    ]


def _runs_status(mocker, rows, date='2024-01-15'):
    from routes import executions
    mocker.patch.object(executions.executions_repo, 'query_by_date', return_value=list(rows))
    mocker.patch.object(executions.backfills_repo, 'list_recent', return_value=[])
    mocker.patch.object(executions.pipelines_repo, 'get', return_value=None)  # no ARN → no reconcile
    resp = executions.get_all_runs({'queryStringParameters': {'date': date}})
    body = json.loads(resp['body'])
    execs = [r for r in body['runs'] if r['kind'] == 'execution']
    assert len(execs) == 1, execs
    return execs[0]['status']


def _dropdown_status(mocker, rows, date='2024-01-15', pipeline='test-pipeline'):
    from routes import pipelines_list
    mocker.patch.object(pipelines_list.executions_repo, 'query_by_date', return_value=list(rows))
    mocker.patch.object(pipelines_list.pipelines_repo, 'get', return_value=None)  # no ARN → no reconcile
    resp = pipelines_list.get_pipeline_executions(pipeline, {'queryStringParameters': {'date': date}})
    body = json.loads(resp['body'])
    execs = body['executions']
    assert len(execs) == 1, execs
    return execs[0]['status']


# (task statuses, expected canonical execution status)
CASES = [
    (['success'], 'success'),
    (['success', 'skipped'], 'success'),
    (['success', 'failed'], 'failed'),
    (['failed'], 'failed'),
    (['aborted'], 'aborted'),
    (['stopped'], 'aborted'),
    (['upstream_failed'], 'aborted'),
    (['success', 'stopped'], 'aborted'),            # the reported bug: a stopped run
    (['success', 'aborted', 'stopped'], 'aborted'),
    (['failed', 'aborted'], 'failed'),              # a genuine failure outranks the stop
    (['running'], 'running'),
    (['running', 'success'], 'running'),
]


@pytest.mark.parametrize("statuses,expected", CASES)
def test_runs_and_dropdown_agree(mocker, statuses, expected):
    rows = _task_rows(statuses)
    runs_status = _runs_status(mocker, rows)
    dropdown_status = _dropdown_status(mocker, rows)
    assert runs_status == expected, f"/runs derived {runs_status}, expected {expected}"
    assert dropdown_status == expected, f"dropdown derived {dropdown_status}, expected {expected}"
    assert runs_status == dropdown_status
