"""Task routes for Console API.

Handles task operations:
- get_all_tasks: List all tasks with filters
- get_task_config: Get task configuration
- update_task_config: Update task configuration
- skip_task: Skip a waiting/failed task
- fail_task: Mark task as failed
- mark_success: Mark task as successful manually
- stop_task: Stop a running task (can be restarted)
- restart_task: Restart a stopped/failed task
- get_task_events: Get task timeline events
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError, BotoCoreError

from config import sfn
from dal import executions_repo, pipelines_repo
from dal.task_events_repo import task_events_repo
from constants import Limits, TaskStatus, TASK_WAITING_STATUSES
from response import cors_response, safe_parse_body
from logger import log
from utils import (
    is_internal_record, should_skip_token_row,
    is_execution_name, safe_int, safe_param_int,
    stop_task_executions, record_manual_decision, ensure_pipeline_execution_short,
    resolve_pagerduty
)
from task_actions import (
    notify_dependents_via_sfn,
    is_terminal_status,
    build_condition_expression_values,
    TERMINAL_CONDITION_EXPRESSION,
    RESOLVED_CONDITION_EXPRESSION,
    build_resolved_expression_values
)



def resolve_task_item(
    task_name: str, 
    date: str, 
    pipeline_execution: str = ''
) -> tuple:
    """
    Resolve task item from DynamoDB by task_name or execution_name.
    
    Handles both formats:
    - Full execution_name (e.g., 'extract-2024-01-15-abc123xyz')
    - Task name only (requires GSI lookup with date)
    
    Uses pagination for GSI queries to handle large datasets.
    Falls back to GSI if direct lookup fails.
    
    Args:
        task_name: Task name or full execution_name
        date: Date for GSI lookup (YYYY-MM-DD)
        pipeline_execution: Optional pipeline execution filter
        
    Returns:
        (item, execution_name) tuple, or (None, None) if not found
    """
    item = None
    execution_name = task_name
    
    # Try direct lookup first if it looks like execution_name
    if is_execution_name(task_name):
        item = executions_repo.get(task_name)
        if item:
            return item, task_name
        # Fall through to GSI lookup if not found
    
    # GSI lookup with pagination
    filter_expr = Attr('task_name').eq(task_name)
    if pipeline_execution:
        filter_expr = (
            Attr('task_name').eq(task_name) & 
            Attr('pipeline_execution').eq(pipeline_execution)
        )
    
    query_kwargs = {
        'KeyConditionExpression': Key('date').eq(date),
        'FilterExpression': filter_expr,
        # Only fetch fields needed for discovery (not full record)
        'ProjectionExpression': 'execution_name, started_at, task_name, pipeline_execution',
    }
    
    # Paginate through results to find matching task
    last_key = None
    all_items = []
    max_pages = 10  # Safety limit
    
    for _ in range(max_pages):
        if last_key:
            query_kwargs['ExclusiveStartKey'] = last_key
        
        response = executions_repo.query_by_date_raw(**query_kwargs)
        items = response.get('Items', [])
        all_items.extend(items)
        
        # Early exit if we found items (FilterExpression already applied)
        if items:
            break
            
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
    
    if all_items:
        # Get the most recent one if multiple
        best = sorted(all_items, key=lambda x: x.get('started_at', ''), reverse=True)[0]
        execution_name = best.get('execution_name', task_name)
        # Fetch full record by primary key (GSI may not have all fields)
        item = executions_repo.get(execution_name)
        if item:
            return item, execution_name
    
    return None, None


TERMINAL_TASK_STATUSES = {'success', 'succeeded', 'failed', 'upstream_failed', 'skipped', 'stopped', 'aborted'}
# Resolved = already in a "good" terminal state, no recovery needed
RESOLVED_TASK_STATUSES = {'success', 'succeeded', 'skipped'}


def _reconcile_orphaned_tasks(tasks):
    """Reconcile tasks stuck in non-terminal status when their execution already failed.
    
    When an orchestrator SFN times out or fails, tasks like waiting_delay
    remain in DynamoDB with their old status. This checks SFN execution
    status and marks orphaned tasks as 'aborted'.
    """
    # Find non-terminal tasks grouped by (pipeline_name, pipeline_execution)
    pending_execs = {}  # {(pipeline_name, pipeline_execution): [task_indices]}
    for i, task in enumerate(tasks):
        if task['status'] not in TERMINAL_TASK_STATUSES and task.get('pipeline_execution'):
            key = (task.get('pipeline_name', ''), task['pipeline_execution'])
            pending_execs.setdefault(key, []).append(i)
    
    if not pending_execs:
        return tasks
    
    # Get SFN ARNs from registry for unique pipeline names
    pipeline_arns = {}
    for pipeline_name in set(k[0] for k in pending_execs):
        try:
            item = pipelines_repo.get(pipeline_name)
            if item:
                pipeline_arns[pipeline_name] = item.get('sfn_arn', '') or item.get('arn', '')
        except (ClientError, BotoCoreError) as e:
            log.warn("_reconcile_orphaned_tasks", "Failed to load pipeline registry entry",
                        pipeline_name=pipeline_name, error=str(e))
    
    # Check execution status for each pending group
    failed_execs = set()
    for (pipeline_name, exec_name), _ in pending_execs.items():
        sm_arn = pipeline_arns.get(pipeline_name)
        if not sm_arn:
            continue
        
        # Construct execution ARN: stateMachine:name → execution:name:exec_name
        exec_arn = sm_arn.replace(':stateMachine:', ':execution:') + ':' + exec_name
        try:
            resp = sfn.describe_execution(executionArn=exec_arn)
            status = resp.get('status', '')
            if status in ('FAILED', 'TIMED_OUT', 'ABORTED'):
                failed_execs.add((pipeline_name, exec_name))
        except (ClientError, BotoCoreError) as e:
            log.warn("_reconcile_orphaned_tasks", "Failed to describe pipeline execution",
                        pipeline_name=pipeline_name, exec_name=exec_name, error=str(e))
    
    # Reconcile: mark non-terminal tasks in failed executions as 'aborted'
    # BUT skip tasks whose wrapper is still running (e.g. restarted tasks)
    if failed_execs:
        for (pipeline_name, exec_name), indices in pending_execs.items():
            if (pipeline_name, exec_name) in failed_execs:
                for i in indices:
                    # Check if task has a running wrapper (restart creates new wrapper)
                    wrapper_arn = tasks[i].get('wrapper_execution_arn', '')
                    if wrapper_arn:
                        try:
                            resp = sfn.describe_execution(executionArn=wrapper_arn)
                            if resp.get('status', '') == 'RUNNING':
                                continue  # Wrapper still active, not orphaned
                        except (ClientError, BotoCoreError) as e:
                            # Can't check wrapper — fall through to mark aborted.
                            # This is intentional: stale ARN or missing wrapper means
                            # the task has no live execution to continue from.
                            log.info("_reconcile_orphaned_tasks", "Wrapper describe failed, marking aborted",
                                     wrapper_arn=wrapper_arn, error=str(e))
                    tasks[i] = {**tasks[i], 'status': 'aborted'}
    
    return tasks


def get_all_tasks(event: Dict) -> Dict:
    """Get all task instances across all pipelines.
    
    Optimized: Uses GSI 'date-pipeline-index' when date filter is provided.
    """
    params = event.get('queryStringParameters', {}) or {}
    
    # Optional filters
    status_filter = params.get('status')
    date_filter = params.get('date')
    pipeline_filter = params.get('pipeline')
    limit = safe_param_int(params, 'limit', 100, 500)
    
    try:
        # Optimized path: Use GSI when date filter is provided
        if date_filter:
            key_cond = Key('date').eq(date_filter)
            # Add pipeline filter to key condition if provided
            if pipeline_filter:
                key_cond = Key('date').eq(date_filter) & Key('pipeline_name').eq(pipeline_filter)
            
            filter_expr = Attr('status').eq(status_filter) if status_filter else None
            
            items = executions_repo.query_by_date(
                date_filter,
                max_items=Limits.MAX_FETCH_ITEMS,
                key_condition=key_cond,
                filter_expr=filter_expr,
                projection='execution_name, task_name, pipeline_name, #s, #d, started_at, running_at, finished_at, dependencies, pipeline_execution, wait_for, wrapper_execution_arn',
                expr_names={'#s': 'status', '#d': 'date'}
            )
        else:
            # Fallback: Scan with filters (for queries without date)
            # Build filter expression
            filter_parts = []
            expr_values = {}
            expr_names = {'#s': 'status', '#d': 'date', '#p': 'pipeline_name'}
            
            if status_filter:
                filter_parts.append('#s = :status')
                expr_values[':status'] = status_filter
            
            if pipeline_filter:
                filter_parts.append('#p = :pipeline')
                expr_values[':pipeline'] = pipeline_filter
            
            filter_expr = ' AND '.join(filter_parts) if filter_parts else None
            
            scan_kwargs = {
                'ProjectionExpression': 'execution_name, task_name, pipeline_name, #s, #d, started_at, running_at, finished_at, dependencies, pipeline_execution, wait_for, wrapper_execution_arn',
                'ExpressionAttributeNames': expr_names
            }
            
            if filter_expr:
                scan_kwargs['FilterExpression'] = filter_expr
                scan_kwargs['ExpressionAttributeValues'] = expr_values
            
            items = executions_repo.scan(max_items=Limits.MAX_FETCH_ITEMS, **scan_kwargs)
        
        # Sort by started_at descending
        items.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        
        # Apply limit after sorting
        items = items[:limit]
        
        # Format response
        tasks = []
        for item in items:
            # Skip internal/special records (_pause_, _notify_warn_) and Backfill records.
            if should_skip_token_row(item):
                continue
            # Calculate duration if possible — use running_at (actual task start) not started_at (wrapper start)
            duration_ms = None
            actual_start = item.get('running_at') or item.get('started_at')
            if actual_start and item.get('finished_at'):
                try:
                    start = datetime.fromisoformat(actual_start.replace('Z', '+00:00'))
                    end = datetime.fromisoformat(item['finished_at'].replace('Z', '+00:00'))
                    duration_ms = int((end - start).total_seconds() * 1000)
                except (ValueError, TypeError, AttributeError) as e:
                    log.warn("get_all_tasks", "Bad timestamp on task; duration_ms left None",
                             execution_name=item.get('execution_name'),
                             actual_start=actual_start,
                             finished_at=item.get('finished_at'),
                             error=str(e))
            
            tasks.append({
                'execution_name': item.get('execution_name'),
                'task_name': item.get('task_name'),
                'pipeline_name': item.get('pipeline_name', 'unknown'),
                'status': item.get('status', 'unknown'),
                'date': item.get('date'),
                'started_at': item.get('started_at'),
                'running_at': item.get('running_at'),
                'finished_at': item.get('finished_at'),
                'duration_ms': duration_ms,
                'dependencies': item.get('dependencies', []),
                'wait_for': item.get('wait_for', '[]'),
                'pipeline_execution': item.get('pipeline_execution'),
                'notification_failed': item.get('notification_failed')
            })
        
        # Reconcile: tasks stuck in non-terminal status but execution already failed
        tasks = _reconcile_orphaned_tasks(tasks)
        
        return cors_response(200, {
            'tasks': tasks,
            'count': len(tasks),
            'filters': {
                'status': status_filter,
                'date': date_filter,
                'pipeline': pipeline_filter
            }
        })
    except Exception as e:
        log.error("unknown", "Unexpected error", error=str(e))
        return cors_response(500, {'error': f'Failed to get tasks: {str(e)}'})


def get_task_config(task_name: str, event: Dict) -> Dict:
    """Get task configuration.
    
    Supports both execution_name (full) and task_name (requires date lookup).
    Uses pagination for GSI queries to handle large datasets.
    
    Returns config fields only (not runtime state like retry_attempts).
    """
    params = event.get('queryStringParameters') or {}
    date = params.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    pipeline_execution = params.get('pipeline_execution', '')
    
    item, execution_name = resolve_task_item(task_name, date, pipeline_execution)
    
    if not item:
        item = {}
        execution_name = task_name
    
    return cors_response(200, {
        'task_name': task_name,
        'execution_name': execution_name,
        'config': {
            'timeout_seconds': safe_int(item.get('timeout_seconds'), 14400),
            'slack_channel': item.get('slack_channel', '#alerts'),
            'max_retries': safe_int(item.get('max_retries'), 3)
        },
        # Runtime state (read-only, for reference)
        'runtime': {
            'retry_attempts': safe_int(item.get('retry_attempts'), 0),
            'status': item.get('status', 'unknown')
        }
    })


def get_task_events(execution_name: str, event: Dict) -> Dict:
    """
    Get real timeline events for a task.
    
    Returns all events from task_events table for debugging and timeline display.
    Events are ordered chronologically by event_time.
    """
    import urllib.parse
    execution_name = urllib.parse.unquote(execution_name)
    
    # Try to get task_run_id from tokens table first
    try:
        token_item = executions_repo.get(execution_name)
        task_run_id = (token_item or {}).get('task_run_id', execution_name)
    except Exception as e:
        # Falling back to execution_name as task_run_id keeps the events lookup
        # working (the GSI query below handles either id). Log so a real DDB
        # error doesn't get masked as "no events for this task".
        log.warn("get_task_events", "Token lookup failed; falling back to execution_name as task_run_id",
                 execution_name=execution_name, error=str(e))
        task_run_id = execution_name
    
    events = []
    
    # Try by task_run_id first
    try:
        events = task_events_repo.query_by_task_run_id(task_run_id)
    except Exception as e:
        log.error("get_task_events", "Error querying by task_run_id", error=str(e))
    
    # If no events found, try by execution_name GSI
    if not events:
        try:
            events = task_events_repo.query_by_execution_name(execution_name)
        except Exception as e:
            log.error("get_task_events", "Error querying by execution_name", error=str(e))
    
    # Format events for response
    formatted_events = []
    for evt in events:
        formatted_events.append({
            'event_type': evt.get('event_type', ''),
            'event_time': evt.get('event_time', '').split('#')[0],  # Remove sequence suffix
            'task_name': evt.get('task_name', ''),
            'status': evt.get('status', ''),
            'reason': evt.get('reason', ''),
            'decision': evt.get('decision', ''),  # For MANUAL_DECISION events
            'error_summary': evt.get('error_summary', ''),
            'dependencies': evt.get('dependencies', ''),
            'task_type': evt.get('task_type', ''),
            'task_arn': evt.get('task_arn', ''),
            'attempt': safe_int(evt.get('attempt'), 1)
        })
    
    return cors_response(200, {
        'execution_name': execution_name,
        'task_run_id': task_run_id,
        'events': formatted_events,
        'event_count': len(formatted_events)
    })


def register(router) -> None:
    """Register the free task read routes. See ADR #97."""
    router.add('GET', '/api/tasks', get_all_tasks)
    router.add('GET', '/api/task-config', get_task_config, 'name')
    router.add('GET', '/api/task-events', get_task_events, 'name')
