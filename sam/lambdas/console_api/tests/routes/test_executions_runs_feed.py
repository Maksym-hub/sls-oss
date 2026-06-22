"""
Unit tests for the unified Run/Activity feed in routes.executions.get_all_runs
(ADR #95): Backfills merged into /api/runs as first-class ``kind='backfill'``
rows alongside ``kind='execution'`` rows.

Pattern follows test_backfill.py — pytest-mock (ADR #26), patch the repo methods
get_all_runs calls (its external data boundary). The merge/filter/sort logic and
should_skip_token_row run for real (CLAUDE.md #13/#14: pin the integration
contract, mock only at the boundary).
"""

import json

import pytest
from botocore.exceptions import ClientError


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _event(date=None, status=None, pipeline=None):
    qs = {}
    if date:
        qs['date'] = date
    if status:
        qs['status'] = status
    if pipeline:
        qs['pipeline'] = pipeline
    return {'queryStringParameters': qs or None}


def _exec_row(pe='p-2024-01-15-abc', name='extract-2024-01-15-abc',
              pipeline='test-pipeline', status='running',
              started='2024-01-15T10:00:00Z', date='2024-01-15'):
    return {
        'execution_name': name,
        'pipeline_execution': pe,
        'pipeline_execution_short': pe[-8:],
        'pipeline_name': pipeline,
        'status': status,
        'date': date,
        'started_at': started,
        'finished_at': '',
    }


def _backfill_record(bf_id='bf-abc123', target='test-pipeline', status='completed',
                     started='2024-01-15T12:00:00Z', finished='2024-01-15T12:30:00Z',
                     keys=None, total=10, completed=10, failed=0, skipped=0,
                     cascade='auto', granularity='daily', started_by='alice'):
    return {
        'execution_name': bf_id,
        'backfill_id': bf_id,
        'record_type': 'backfill',
        'pipeline_name': '_slsflow_bulk_backfill',
        'target_pipeline': target,
        'status': status,
        'started_at': started,
        'finished_at': finished,
        'started_by': started_by,
        'partition_keys': json.dumps(keys if keys is not None
                                     else ['2024-01-10', '2024-01-11', '2024-01-12']),
        'total_partitions': total,
        'completed_partitions': completed,
        'failed_partitions': failed,
        'skipped_partitions': skipped,
        'cascade': cascade,
        'granularity': granularity,
    }


def _call(mocker, exec_rows, backfill_records, event):
    """Patch the two repos get_all_runs depends on, then call it."""
    from routes import executions
    mocker.patch.object(executions.executions_repo, 'query_by_date',
                         return_value=list(exec_rows))
    mocker.patch.object(executions.backfills_repo, 'list_recent',
                        return_value=list(backfill_records))
    resp = executions.get_all_runs(event)
    return resp, json.loads(resp['body'])


# ──────────────────────────────────────────────────────────────────────────────
# kind discriminator (ADR #95 decision 1)
# ──────────────────────────────────────────────────────────────────────────────

class TestKindDiscriminator:
    def test_executions_tagged_kind_execution(self, mocker):
        resp, body = _call(mocker, [_exec_row()], [], _event(date='2024-01-15'))
        assert resp['statusCode'] == 200
        execs = [r for r in body['runs'] if r['kind'] == 'execution']
        assert len(execs) == 1
        assert execs[0]['pipeline_execution'] == 'p-2024-01-15-abc'

    def test_backfills_tagged_kind_backfill_with_expected_fields(self, mocker):
        resp, body = _call(mocker, [], [_backfill_record()], _event(date='2024-01-11'))
        bfs = [r for r in body['runs'] if r['kind'] == 'backfill']
        assert len(bfs) == 1
        row = bfs[0]
        assert row['id'] == 'bf-abc123'
        assert row['backfill_id'] == 'bf-abc123'
        assert row['pipeline_name'] == 'test-pipeline'
        assert row['status'] == 'completed'
        assert row['total_partitions'] == 10
        assert row['completed_partitions'] == 10
        assert row['downstream'] == 'auto'
        assert row['granularity'] == 'daily'
        # finished - started == 30 min
        assert row['duration_ms'] == 30 * 60 * 1000

    def test_every_row_has_a_kind(self, mocker):
        resp, body = _call(mocker, [_exec_row()], [_backfill_record(keys=['2024-01-15'])],
                           _event(date='2024-01-15'))
        assert all('kind' in r for r in body['runs'])
        assert {r['kind'] for r in body['runs']} == {'execution', 'backfill'}


# ──────────────────────────────────────────────────────────────────────────────
# No double-count + no internal/sentinel leakage (CLAUDE.md #13, ADR #38)
# ──────────────────────────────────────────────────────────────────────────────

class TestNoLeakage:
    def test_backfill_sentinel_and_internal_rows_never_appear_as_executions(self, mocker):
        # query_by_date returns a real exec row, a backfill-sentinel row, and an
        # internal _notify_warn_ row. Only the exec row may become an execution.
        sentinel_in_tokens = {
            'execution_name': 'bf-leak',
            'pipeline_execution': 'bf-leak',
            'pipeline_name': '_slsflow_bulk_backfill',
            'record_type': 'backfill',
            'status': 'running',
            'date': '2024-01-15',
            'started_at': '2024-01-15T09:00:00Z',
        }
        notify_warn = {
            'execution_name': '_notify_warn_extract-2024-01-15-abc',
            'pipeline_execution': 'p-2024-01-15-abc',
            'pipeline_name': 'test-pipeline',
            'status': 'failed',
            'date': '2024-01-15',
            'started_at': '2024-01-15T09:30:00Z',
        }
        resp, body = _call(
            mocker,
            [_exec_row(), sentinel_in_tokens, notify_warn],
            [_backfill_record(bf_id='bf-real', keys=['2024-01-15'])],
            _event(date='2024-01-15'),
        )
        execs = [r for r in body['runs'] if r['kind'] == 'execution']
        bfs = [r for r in body['runs'] if r['kind'] == 'backfill']
        # exactly one execution (the real one); sentinel + notify_warn filtered
        assert len(execs) == 1
        assert execs[0]['pipeline_execution'] == 'p-2024-01-15-abc'
        assert all(r['pipeline_name'] != '_slsflow_bulk_backfill' for r in execs)
        # the backfill appears exactly once, sourced from list_recent
        assert len(bfs) == 1
        assert bfs[0]['backfill_id'] == 'bf-real'


# ──────────────────────────────────────────────────────────────────────────────
# Filters (ADR #95 decisions 2-4)
# ──────────────────────────────────────────────────────────────────────────────

class TestFilters:
    def test_status_filter_matches_backfill_vocabulary(self, mocker):
        # ?status=completed: backfill (completed) in, running execution out.
        resp, body = _call(
            mocker,
            [_exec_row(status='running')],
            [_backfill_record(status='completed', keys=['2024-01-15'])],
            _event(date='2024-01-15', status='completed'),
        )
        kinds = {r['kind'] for r in body['runs']}
        assert kinds == {'backfill'}

    def test_pipeline_filter_matches_backfill_target(self, mocker):
        resp, body = _call(
            mocker,
            [],
            [
                _backfill_record(bf_id='bf-match', target='wanted', keys=['2024-01-15']),
                _backfill_record(bf_id='bf-other', target='other', keys=['2024-01-15']),
            ],
            _event(date='2024-01-15', pipeline='wanted'),
        )
        ids = {r['backfill_id'] for r in body['runs'] if r['kind'] == 'backfill'}
        assert ids == {'bf-match'}

    def test_date_filter_includes_backfill_in_partition_range(self, mocker):
        # range covers 2024-01-10..2024-01-12
        _, in_range = _call(mocker, [], [_backfill_record()], _event(date='2024-01-11'))
        assert any(r['kind'] == 'backfill' for r in in_range['runs'])

    def test_date_filter_excludes_backfill_outside_partition_range(self, mocker):
        _, out_of_range = _call(mocker, [], [_backfill_record()], _event(date='2024-02-01'))
        assert not any(r['kind'] == 'backfill' for r in out_of_range['runs'])


# ──────────────────────────────────────────────────────────────────────────────
# Sort + graceful degradation (ADR #95 decision 5)
# ──────────────────────────────────────────────────────────────────────────────

class TestSortAndDegrade:
    def test_merged_feed_sorted_by_started_at_desc(self, mocker):
        # exec at 10:00, backfill at 12:00 → backfill first
        resp, body = _call(
            mocker,
            [_exec_row(started='2024-01-15T10:00:00Z')],
            [_backfill_record(started='2024-01-15T12:00:00Z', keys=['2024-01-15'])],
            _event(date='2024-01-15'),
        )
        assert body['runs'][0]['kind'] == 'backfill'
        assert body['runs'][1]['kind'] == 'execution'

    def test_list_recent_error_degrades_gracefully(self, mocker):
        from routes import executions
        mocker.patch.object(executions.executions_repo, 'query_by_date',
                            return_value=[_exec_row()])
        mocker.patch.object(
            executions.backfills_repo, 'list_recent',
            side_effect=ClientError({'Error': {'Code': 'X', 'Message': 'boom'}}, 'Scan'),
        )
        resp = executions.get_all_runs(_event(date='2024-01-15'))
        body = json.loads(resp['body'])
        # executions still returned, no 500
        assert resp['statusCode'] == 200
        assert any(r['kind'] == 'execution' for r in body['runs'])
        assert not any(r['kind'] == 'backfill' for r in body['runs'])
