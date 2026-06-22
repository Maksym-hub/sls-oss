"""Execution routes for Console API.

Handles pipeline execution control operations:
- get_all_runs: List all pipeline executions
- stop_execution: Stop a running execution
- pause_execution: Pause execution (running tasks complete, new tasks wait)
- resume_execution: Resume paused execution
- extend_pause: Extend pause timeout by 12 hours
- get_execution_pause_status: Check if execution is paused
- get_execution_children: Get child tasks of an execution
- get_execution_parent: Get parent execution info
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError, BotoCoreError

from config import sfn
from dal import executions_repo, pipelines_repo, backfills_repo
from dal.subscriptions_repo import dep_subscriptions_repo
from constants import TaskStatus, TASK_TERMINAL_STATUSES
from response import cors_response
from logger import log
from utils import safe_param_int, is_internal_record, should_skip_token_row


def _build_backfill_run_rows(
    limit: int,
    status_filter: str,
    pipeline_filter: str,
    date_filter: str,
) -> List[Dict]:
    """Build unified-feed rows for Backfills (``kind='backfill'``) — ADR #95.

    Backfills live in pipeline-tokens under a sentinel ``pipeline_name`` and are
    excluded from the execution rows in ``get_all_runs`` by
    ``should_skip_token_row``; they are merged into ``/api/runs`` here as
    first-class rows. Status stays in the 6-state Backfill vocabulary (ADR #56)
    — no normalization to execution statuses; the ``kind`` field lets the UI
    interpret it. Children are not embedded: a backfill row expands on demand
    via ``GET /api/backfills/by-id``.

    Filters (ADR #95 decisions):
      * ``status_filter`` — literal match against the Backfill status.
      * ``pipeline_filter`` — match on ``target_pipeline`` (cross-pipeline
        backfills surface under their target only).
      * ``date_filter`` — include when the date is within the backfill's
        partition range (string range over ``partition_keys``; daily-oriented).

    Degrades gracefully: on a DDB error the executions are still returned.
    """
    rows: List[Dict] = []
    try:
        backfills = backfills_repo.list_recent(limit=limit)
    except (ClientError, BotoCoreError) as e:
        log.error("get_all_runs", "Failed to list backfills for unified feed", error=str(e))
        return rows

    for bf in backfills:
        status = bf.get('status', 'pending')
        if status_filter and status != status_filter:
            continue

        target_pipeline = bf.get('target_pipeline', '') or ''
        if pipeline_filter and target_pipeline != pipeline_filter:
            continue

        if date_filter:
            try:
                keys = json.loads(bf.get('partition_keys') or '[]')
            except (json.JSONDecodeError, TypeError):
                keys = []
            if not keys or not (min(keys) <= date_filter <= max(keys)):
                continue

        started_at = bf.get('started_at', '') or ''
        finished_at = bf.get('finished_at', '') or ''
        duration_ms = None
        if started_at and finished_at:
            try:
                start_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
                duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
            except (ValueError, TypeError) as e:
                log.warn("get_all_runs", "Bad timestamp on backfill; duration_ms left None",
                         backfill_id=bf.get('backfill_id'), error=str(e))

        rows.append({
            'kind': 'backfill',
            'id': bf.get('backfill_id'),
            'backfill_id': bf.get('backfill_id'),
            'pipeline_name': target_pipeline,
            'status': status,
            'started_at': started_at or None,
            'finished_at': finished_at or None,
            'started_by': bf.get('started_by'),
            'total_partitions': int(bf.get('total_partitions', 0) or 0),
            'completed_partitions': int(bf.get('completed_partitions', 0) or 0),
            'failed_partitions': int(bf.get('failed_partitions', 0) or 0),
            'skipped_partitions': int(bf.get('skipped_partitions', 0) or 0),
            'downstream': bf.get('cascade'),
            'granularity': bf.get('granularity'),
            'date': None,
            'duration_ms': duration_ms,
        })
    return rows


def get_all_runs(event: Dict) -> Dict:
    """Get all pipeline runs across pipelines from DynamoDB.
    
    DATA SOURCE: DynamoDB (see DESIGN_DECISIONS.md #22).
    Uses date-pipeline-index GSI for efficient queries by logical date.
    """
    params = event.get('queryStringParameters', {}) or {}
    limit = safe_param_int(params, 'limit', 50, 200)
    date_filter = params.get('date', '')
    pipeline_filter = params.get('pipeline', '')
    status_filter = params.get('status', '')
    
    try:
        all_items = []
        
        if date_filter:
            # Single date: one GSI query
            key_cond = Key('date').eq(date_filter)
            if pipeline_filter:
                key_cond = Key('date').eq(date_filter) & Key('pipeline_name').eq(pipeline_filter)
            all_items = executions_repo.query_by_date(
                date_filter,
                max_items=2000,
                key_condition=key_cond,
                projection='pipeline_execution, pipeline_execution_short, pipeline_name, #d, #s, started_at, finished_at',
                expr_names={'#d': 'date', '#s': 'status'}
            )
        else:
            # Default: query last 14 days (SLA window)
            sla_days = 14
            for i in range(sla_days):
                date_str = (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d')
                try:
                    key_cond = Key('date').eq(date_str)
                    if pipeline_filter:
                        key_cond = Key('date').eq(date_str) & Key('pipeline_name').eq(pipeline_filter)
                    day_items = executions_repo.query_by_date(
                        date_str,
                        max_items=500,
                        key_condition=key_cond,
                        projection='pipeline_execution, pipeline_execution_short, pipeline_name, #d, #s, started_at, finished_at',
                        expr_names={'#d': 'date', '#s': 'status'}
                    )
                    all_items.extend(day_items)
                except Exception as e:
                    log.error("get_all_runs", "Error querying date", error=str(e), date_str=date_str)
        
        # Group by pipeline_execution and aggregate status
        resolved_statuses = {'success', 'succeeded', 'skipped'}
        bad_statuses = {'failed'}
        stopped_statuses = {'stopped', 'aborted', 'upstream_failed'}
        terminal_statuses = resolved_statuses | bad_statuses | stopped_statuses
        
        exec_map = {}
        for item in all_items:
            # Skip internal/special records (_pause_, _notify_warn_, etc.)
            if should_skip_token_row(item):
                continue
            pe = item.get('pipeline_execution')
            p_name = item.get('pipeline_name', '')
            if not pe or pe == 'unknown' or not p_name or p_name == 'unknown':
                continue
            
            if pe not in exec_map:
                exec_map[pe] = {
                    'pipeline_name': p_name,
                    'pipeline_execution': pe,
                    'pipeline_execution_short': item.get('pipeline_execution_short', pe[:20] if pe else ''),
                    'date': item.get('date'),
                    'started_at': item.get('started_at', ''),
                    'finished_at': item.get('finished_at', ''),
                    'statuses': set()
                }
            
            entry = exec_map[pe]
            entry['statuses'].add(item.get('status', 'waiting'))
            
            started = item.get('started_at', '')
            if started and (not entry['started_at'] or started < entry['started_at']):
                entry['started_at'] = started
            finished = item.get('finished_at', '')
            if finished and (not entry['finished_at'] or finished > entry['finished_at']):
                entry['finished_at'] = finished
        
        all_runs = []
        for pe, data in exec_map.items():
            statuses = data['statuses']
            is_completed = statuses.issubset(terminal_statuses) and len(statuses) > 0
            has_failure = bool(statuses & bad_statuses)
            all_resolved = statuses.issubset(resolved_statuses) and len(statuses) > 0
            
            has_stopped = bool(statuses & stopped_statuses)
            if is_completed:
                if has_stopped and not has_failure:
                    status = 'aborted'
                else:
                    status = 'failed' if has_failure else 'succeeded'
            elif has_failure:
                status = 'failed'
            elif has_stopped:
                status = 'aborted'
            elif all_resolved:
                status = 'succeeded'
            else:
                status = 'running'
            
            # Apply status filter
            if status_filter and status != status_filter:
                continue
            
            # Calculate duration
            duration_ms = None
            if data['started_at'] and data['finished_at']:
                try:
                    start_dt = datetime.fromisoformat(data['started_at'].replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(data['finished_at'].replace('Z', '+00:00'))
                    duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                except (ValueError, TypeError) as e:
                    log.warn("get_all_runs", "Bad timestamp on run; duration_ms left None",
                             pipeline_execution=pe,
                             started_at=data.get('started_at'),
                             finished_at=data.get('finished_at'),
                             error=str(e))
            
            all_runs.append({
                'kind': 'execution',
                'pipeline_name': data['pipeline_name'],
                'pipeline_execution': pe,
                'pipeline_execution_short': data['pipeline_execution_short'],
                'status': status,
                'started_at': data['started_at'] or None,
                'finished_at': data['finished_at'] or None,
                'date': data['date'],
                'duration_ms': duration_ms
            })
        
        # Merge Backfills as first-class 'backfill' rows (ADR #95). Backfills
        # are excluded from the execution rows above by should_skip_token_row,
        # so there is no double-count — they enter only here.
        all_runs.extend(
            _build_backfill_run_rows(limit, status_filter, pipeline_filter, date_filter)
        )

        # Sort by started_at descending (newest first)
        all_runs.sort(key=lambda x: x.get('started_at') or '', reverse=True)
        all_runs = all_runs[:limit]
        
        return cors_response(200, {
            'runs': all_runs,
            'count': len(all_runs),
            'filters': {
                'pipeline': pipeline_filter,
                'status': status_filter,
                'date': date_filter
            }
        })
    except Exception as e:
        log.error("get_all_runs", "Error", error=str(e))
        return cors_response(500, {'error': f'Failed to get runs: {str(e)}'})


def get_execution_children(execution_name: str, event: Dict) -> Dict:
    """
    Get child executions of a parent execution.
    Uses GSI pipeline-execution-index on pipeline_tokens table.
    
    Includes pagination to handle >1MB of results.
    """
    try:
        # Query GSI for children (repo handles pagination)
        items = executions_repo.query_by_pipeline_execution(execution_name)
        
        children = []
        for item in items:
            if should_skip_token_row(item):
                continue
            children.append({
                'execution_name': item.get('execution_name'),
                'task_name': item.get('task_name', ''),
                'status': item.get('status'),
                'date': item.get('date'),
                'started_at': item.get('started_at'),
                'finished_at': item.get('finished_at')
            })
        
        # Sort by started_at
        children.sort(key=lambda x: x.get('started_at', ''))
        
        return cors_response(200, {
            'pipeline_execution': execution_name,
            'children': children,
            'count': len(children)
        })
    
    except Exception as e:
        log.error("get_execution_children", "Error getting children", error=str(e), execution_name=execution_name)
        return cors_response(200, {
            'pipeline_execution': execution_name,
            'children': [],
            'count': 0
        })


def get_execution_parent(execution_name: str, event: Dict) -> Dict:
    """
    Get parent execution info for a given execution.
    """
    try:
        # Get the execution record
        item = executions_repo.get(execution_name)
        
        if not item:
            return cors_response(404, {'error': 'Execution not found'})
        
        pipeline_execution = item.get('pipeline_execution', 'none')
        pipeline_name = item.get('pipeline_name', 'none')
        parent_task = item.get('task_name', 'none')
        
        # If no parent, return empty
        if pipeline_execution == 'none' or not pipeline_execution:
            return cors_response(200, {
                'execution_name': execution_name,
                'has_parent': False,
                'parent': None
            })
        
        # Get parent execution details
        parent_item = executions_repo.get(pipeline_execution)
        
        parent_info = None
        if parent_item:
            parent_info = {
                'execution_name': pipeline_execution,
                'pipeline': pipeline_name,
                'task': parent_task,
                'status': parent_item.get('status'),
                'date': parent_item.get('date')
            }
        else:
            # Parent record might be expired/deleted, just return what we know
            parent_info = {
                'execution_name': pipeline_execution,
                'pipeline': pipeline_name,
                'task': parent_task,
                'status': 'unknown',
                'date': ''
            }
        
        return cors_response(200, {
            'execution_name': execution_name,
            'has_parent': True,
            'parent': parent_info
        })
    
    except Exception as e:
        log.error("executions", "Error getting parent", error=str(e), execution_name=execution_name)
        return cors_response(500, {'error': str(e)})


def register(router) -> None:
    """Register the free execution read routes. See ADR #97."""
    router.add('GET', '/api/runs', get_all_runs)
    router.add('GET', '/api/execution-children', get_execution_children, 'id')
    router.add('GET', '/api/execution-parent', get_execution_parent, 'id')
