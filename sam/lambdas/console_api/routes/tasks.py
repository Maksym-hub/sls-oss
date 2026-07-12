"""Task routes for Console API.

Handles task operations:
- get_all_tasks: List all tasks with filters
- get_task_config: Get task configuration
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
from typing import Dict

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError, BotoCoreError

from config import sfn, dynamodb, TABLE_NAME
from dal import executions_repo, pipelines_repo
from dal.task_events_repo import task_events_repo
from constants import Limits, TaskStatus, TASK_WAITING_STATUSES, TASK_SETTLED_STATUSES, TASK_SUCCESS_STATUSES
from response import cors_response, safe_parse_body
from logger import log
from utils import (
    should_skip_token_row,
    is_execution_name, safe_int, safe_param_int,
    stop_task_executions, record_manual_decision, ensure_pipeline_execution_short,
    resolve_pagerduty, retrieve_result
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


# Task-status groupings are canonical (polyris → TASK_SETTLED_STATUSES /
# TASK_SUCCESS_STATUSES); never re-list them inline.


def _reconcile_orphaned_tasks(tasks):
    """Reconcile tasks stuck in non-terminal status when their execution already failed.
    
    When an orchestrator SFN times out or fails, tasks like waiting_delay
    remain in DynamoDB with their old status. This checks SFN execution
    status and marks orphaned tasks as 'aborted'.
    """
    # Find non-terminal tasks grouped by (pipeline_name, pipeline_execution)
    pending_execs = {}  # {(pipeline_name, pipeline_execution): [task_indices]}
    for i, task in enumerate(tasks):
        if task['status'] not in TASK_SETTLED_STATUSES and task.get('pipeline_execution'):
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
            # Build filter expression. #s/#d are always used (projection); #p is
            # added only when the pipeline filter uses it, otherwise DynamoDB rejects
            # the scan with "unused ExpressionAttributeNames".
            filter_parts = []
            expr_values = {}
            expr_names = {'#s': 'status', '#d': 'date'}
            
            if status_filter:
                filter_parts.append('#s = :status')
                expr_values[':status'] = status_filter
            
            if pipeline_filter:
                expr_names['#p'] = 'pipeline_name'
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
            # Skip internal/special records (_pause_, _notify_warn_, output#) and Backfill records.
            if should_skip_token_row(item):
                continue
            # A task instance must have a task_name; skip pipeline-level/partial rows.
            if not item.get('task_name'):
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
            'max_retries': safe_int(item.get('max_retries'), 3)
        },
        # Runtime state (read-only, for reference)
        'runtime': {
            'retry_attempts': safe_int(item.get('retry_attempts'), 0),
            'status': item.get('status', 'unknown')
        }
    })


def get_task_output(task_name: str, event: Dict) -> Dict:
    """Return a task's stored input and output.

    Reads the run-stable record (``output#pipeline#task#date``). ``output`` is the
    value the task returned; ``input`` is what it received — its upstream outputs and
    the injected run variables (upstream is omitted when the input exceeds ~25 KB).
    Large outputs offloaded to S3 (``_s3_ref``) are resolved transparently;
    ``truncated: true`` means the output exceeded the inline limit.
    """
    params = event.get('queryStringParameters') or {}
    date = params.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    pipeline_execution = params.get('pipeline_execution', '')

    item, execution_name = resolve_task_item(task_name, date, pipeline_execution)
    resolved = item or {}
    pipeline_name = resolved.get('pipeline_name', '')
    # The output store keys on the plain task_name + run date; the route param may
    # be a full execution_name, so build the key from the resolved item's fields.
    plain_task = resolved.get('task_name', task_name)
    run_date = resolved.get('date', date)

    output = None
    task_input = None
    truncated = False
    if pipeline_name:
        key = f"output#{pipeline_name}#{plain_task}#{run_date}"
        try:
            resp = dynamodb.Table(TABLE_NAME).get_item(Key={'execution_name': key})
            store_item = resp.get('Item') or {}
            raw = store_item.get('result')
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get('_truncated'):
                    truncated = True
                else:
                    output = retrieve_result(parsed)
            raw_input = store_item.get('task_input')
            if raw_input:
                task_input = json.loads(raw_input)
        except (ClientError, BotoCoreError, ValueError) as e:
            log.error("get_task_output", "Error reading task input/output",
                      error=str(e), task_name=task_name)

    return cors_response(200, {
        'task_name': task_name,
        'execution_name': execution_name,
        'output': output,
        'input': task_input,
        'truncated': truncated,
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



def _write_notify_warning(
    execution_name: str, task_name: str, pipeline_execution: str, pipeline_name: str, date: str, error: str
) -> None:
    """Write a warning record to pipeline-tokens when notify_dependents fails.

    This makes the failure visible in the Notifications bell in UI,
    which polls pipeline-tokens for status=failed records.
    """
    try:
        warn_key = f"_notify_warn_{execution_name}"
        executions_repo.put(
            {
                'execution_name': warn_key,
                'task_name': task_name,
                'pipeline_execution': pipeline_execution,
                'pipeline_name': pipeline_name,
                'date': date,
                'status': 'failed',
                'error': f'Downstream notification failed: {error}. Downstream tasks may be stuck waiting.',
                'finished_at': datetime.now(timezone.utc).isoformat(),
                'ttl': int(datetime.now(timezone.utc).timestamp()) + 86400,  # 24h TTL
            }
        )
    except Exception as e:
        log.error("_write_notify_warning", "Failed to write warning", error=str(e))


def retry_task(task_name: str, event: Dict) -> Dict:
    """Retry a failed/skipped task.

    DEPRECATED: This endpoint is deprecated. Use restart_task instead.
    This function now simply delegates to restart_task for backward compatibility.
    """
    # Delegate to restart_task for actual functionality
    return restart_task(task_name, event)


def _execute_task_action(
    task_name: str,
    event: Dict,
    *,
    action_name: str,
    target_status: str,
    use_resolved_check: bool,
    include_error_field: bool = False,
    stop_error: str,
    default_reason: str = None,
    default_stop_cause: str = None,
    callback_fn,
    success_message: str,
) -> Dict:
    """Shared implementation for skip_task, fail_task, mark_success.

    Claim-first pattern: update DynamoDB status before executing side-effects.

    Args:
        action_name: For logging and record_manual_decision ('skip', 'fail', 'mark_success')
        target_status: New DynamoDB status ('skipped', 'failed', 'success')
        use_resolved_check: True = block only resolved (success/skipped), allow recovery from failed.
                            False = block all terminal states.
        include_error_field: If True, include error field in UpdateExpression (for fail_task)
        stop_error: First arg to stop_task_executions ('Skipped', 'ManuallyFailed', 'ManuallySucceeded')
        default_reason: If set, extract 'reason' from body with this as default. None = no reason.
        default_stop_cause: Fallback stop_cause when reason is None (e.g. 'Task skipped via UI').
        callback_fn: callable(token, task_name, reason) that sends orchestration callback
        success_message: Template for 200 response message (use {execution_name})
    """
    body, err = safe_parse_body(event)
    if err:
        return err
    date = body.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    pipeline_execution = body.get('pipeline_execution', '')
    reason = body.get('reason', default_reason) if default_reason else None

    # Resolve task using unified resolver (handles both formats with pagination)
    item, execution_name = resolve_task_item(task_name, date, pipeline_execution)

    if not item:
        log.warn(action_name, "Task not found", task_name=task_name, date=date)
        return cors_response(404, {'error': f'Task not found: {task_name} on {date}'})

    orchestration_token = item.get('orchestration_token')
    actual_task_name = item.get('task_name', task_name)
    pipeline_execution = item.get('pipeline_execution', '')
    pipeline_execution_short = item.get('pipeline_execution_short', '')
    current_status = item.get('status', '')

    # Check if action is blocked by current status
    if use_resolved_check:
        if current_status in TASK_SUCCESS_STATUSES:
            return cors_response(
                409,
                {
                    'error': f'Task already resolved: {current_status}',
                    'execution_name': execution_name,
                    'current_status': current_status,
                },
            )
        condition_expr = RESOLVED_CONDITION_EXPRESSION
        expr_values_fn = build_resolved_expression_values
    else:
        if is_terminal_status(current_status):
            return cors_response(
                409,
                {
                    'error': f'Task already in terminal state: {current_status}',
                    'execution_name': execution_name,
                    'current_status': current_status,
                },
            )
        condition_expr = TERMINAL_CONDITION_EXPRESSION
        expr_values_fn = build_condition_expression_values

    # Ensure pipeline_execution_short has a value (critical for notify_dependents)
    pipeline_execution_short = ensure_pipeline_execution_short(pipeline_execution, pipeline_execution_short)
    if not pipeline_execution_short:
        log.warn(action_name, "No pipeline_execution_short, event notification may fail", execution_name=execution_name)

    # Claim: update status FIRST (with ConditionExpression as race condition guard)
    try:
        if include_error_field:
            executions_repo.update(
                execution_name,
                'SET #s = :status, finished_at = :finished, #e = :error',
                expr_values=expr_values_fn(
                    {':status': target_status, ':finished': datetime.now(timezone.utc).isoformat(), ':error': reason}
                ),
                expr_names={'#s': 'status', '#e': 'error'},
                condition_expr=condition_expr,
            )
        else:
            executions_repo.update(
                execution_name,
                'SET #s = :status, finished_at = :finished',
                expr_values=expr_values_fn(
                    {':status': target_status, ':finished': datetime.now(timezone.utc).isoformat()}
                ),
                expr_names={'#s': 'status'},
                condition_expr=condition_expr,
            )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            log.warn(
                action_name, "Race condition: Task became terminal during operation", execution_name=execution_name
            )
            return cors_response(
                409,
                {'error': 'Task status changed during operation (race condition)', 'execution_name': execution_name},
            )
        else:
            raise

    # Side-effects AFTER successful claim
    stop_cause = reason or default_stop_cause or f'Task {action_name} via UI'
    stop_task_executions(item, stop_error, stop_cause)
    record_manual_decision(execution_name, action_name, stop_cause, item)

    log.info(action_name, "Successfully completed", execution_name=execution_name, actual_task_name=actual_task_name)

    # Send orchestration callback
    if orchestration_token:
        try:
            callback_fn(orchestration_token, actual_task_name, reason)
        except (sfn.exceptions.TaskTimedOut, sfn.exceptions.TaskDoesNotExist):
            # Token expired or already consumed (e.g. mark_success/skip on waiting_decision task
            # where orchestration_token was already consumed by notify_dependents).
            # Expected — continue to notify_dependents so downstream unblocks.
            log.warn(
                action_name,
                "Orchestration token expired/consumed — continuing to notify dependents",
                execution_name=execution_name,
            )
        except sfn.exceptions.InvalidToken:
            # Invalid token format — continue
            log.warn(
                action_name,
                "Invalid orchestration token — continuing to notify dependents",
                execution_name=execution_name,
            )
        except Exception as e:
            err_str = str(e)
            log.error(action_name, "Failed orchestration callback", execution_name=execution_name, error=err_str)
            if 'AccessDenied' in err_str:
                detail = 'IAM permission missing: states:SendTaskSuccess. Run sam deploy to fix.'
            else:
                detail = err_str
            return cors_response(
                500,
                {
                    'error': 'Failed to send orchestration callback',
                    'detail': detail,
                    'execution_name': execution_name,
                },
            )
    else:
        # No token means task failed before Run_Task recorded it (e.g. IAM error at startup)
        # Still notify dependents so downstream tasks can unblock
        log.warn(
            action_name,
            "No orchestration token — task may have failed before starting",
            execution_name=execution_name,
            task=actual_task_name,
        )

    # Notify dependents via SFN helper
    if not notify_dependents_via_sfn(
        task_name=actual_task_name,
        status=target_status,
        date=item.get('date', date),
        pipeline_execution_short=pipeline_execution_short,
        pipeline_execution=pipeline_execution,
    ):
        log.warn(
            action_name,
            "Failed to notify dependents — downstream tasks may stay waiting",
            execution_name=execution_name,
        )
        _write_notify_warning(
            execution_name=execution_name,
            task_name=actual_task_name,
            pipeline_execution=pipeline_execution,
            pipeline_name=item.get('pipeline_name', 'unknown'),
            date=item.get('date', date),
            error='SFN start_execution failed',
        )

    resolve_pagerduty(item)
    return cors_response(
        200, {'message': success_message.format(execution_name=execution_name), 'execution_name': execution_name}
    )


def skip_task(task_name: str, event: Dict) -> Dict:
    """Skip a waiting/failed task.

    Supports both execution_name (full) and task_name (requires date lookup).
    """
    return _execute_task_action(
        task_name,
        event,
        action_name='skip',
        target_status='skipped',
        use_resolved_check=True,
        stop_error='Skipped',
        default_reason='Task skipped via UI',
        callback_fn=lambda token, name, _reason: sfn.send_task_success(
            taskToken=token, output=json.dumps({'status': 'skipped', 'task_name': name})
        ),
        success_message='Skip triggered for {execution_name}',
    )


def fail_task(task_name: str, event: Dict) -> Dict:
    """Mark a running task as failed and stop its wrapper.

    Supports both execution_name (full) and task_name (requires date lookup).
    """
    return _execute_task_action(
        task_name,
        event,
        action_name='fail',
        target_status='failed',
        use_resolved_check=False,
        include_error_field=True,
        stop_error='ManuallyFailed',
        default_reason='Manually failed by user',
        callback_fn=lambda token, _name, reason: sfn.send_task_failure(
            taskToken=token, error='ManuallyFailed', cause=reason
        ),
        success_message='Task {execution_name} marked as failed',
    )


def mark_success(task_name: str, event: Dict) -> Dict:
    """Mark a task as successful manually.

    Supports both execution_name (full) and task_name (requires date lookup).

    Use cases:
    - Task stuck but work completed (verified via logs/S3)
    - Manual intervention - work done by human
    - Testing - quickly mark task as done
    """
    return _execute_task_action(
        task_name,
        event,
        action_name='mark_success',
        target_status='success',
        use_resolved_check=True,
        stop_error='ManuallySucceeded',
        default_reason='Manually marked successful by user',
        callback_fn=lambda token, name, reason: sfn.send_task_success(
            taskToken=token,
            output=json.dumps({'status': 'success', 'task_name': name, 'manual': True, 'reason': reason}),
        ),
        success_message='Task {execution_name} marked as successful',
    )


def stop_task(task_name: str, event: Dict) -> Dict:
    """Stop a running task (pause) without marking as failed. Task can be resumed later.
    Also handles stopping waiting tasks by marking them as aborted.

    Supports both execution_name (full) and task_name (requires date lookup).
    """
    body, err = safe_parse_body(event)
    if err:
        return err
    date = body.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    pipeline_execution = body.get('pipeline_execution', '')

    # Resolve task using unified resolver (handles both formats with pagination)
    item, execution_name = resolve_task_item(task_name, date, pipeline_execution)

    if not item:
        return cors_response(404, {'error': f'Task not found: {task_name} on {date}'})

    current_status = item.get('status', '')

    # Check if already terminal BEFORE doing anything
    if is_terminal_status(current_status):
        return cors_response(
            409,
            {
                'error': f'Task already in terminal state: {current_status}',
                'execution_name': execution_name,
                'current_status': current_status,
            },
        )

    actual_task_name = item.get('task_name', task_name)
    pipeline_execution = item.get('pipeline_execution', '')
    pipeline_execution_short = item.get('pipeline_execution_short', '')
    orchestration_token = item.get('orchestration_token')

    # Ensure pipeline_execution_short has a value (critical for notify_dependents)
    pipeline_execution_short = ensure_pipeline_execution_short(pipeline_execution, pipeline_execution_short)
    if not pipeline_execution_short:
        log.warn("stop_task", "No pipeline_execution_short, event notification may fail", execution_name=execution_name)

    # Determine final status based on current status
    # Running tasks become 'stopped', waiting tasks become 'aborted'
    if current_status in TASK_WAITING_STATUSES:
        final_status = TaskStatus.ABORTED
    else:
        final_status = TaskStatus.STOPPED

    # Claim: update status FIRST (only if not already terminal)
    try:
        executions_repo.update(
            execution_name,
            'SET #s = :status, finished_at = :finished',
            expr_values=build_condition_expression_values(
                {':status': final_status, ':finished': datetime.now(timezone.utc).isoformat()}
            ),
            expr_names={'#s': 'status'},
            condition_expr=TERMINAL_CONDITION_EXPRESSION,
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            log.info(
                "stop_task", "Task already in terminal state, skipping status update", execution_name=execution_name
            )
            return cors_response(
                409,
                {
                    'error': 'Task already in terminal state',
                    'execution_name': execution_name,
                    'current_status': current_status,
                },
            )
        else:
            raise

    # Side-effects AFTER successful claim
    stop_task_executions(item, 'Stopped', 'Task stopped via UI - can be restarted')
    record_manual_decision(execution_name, 'stop', 'Task stopped via UI', item)

    # For aborted tasks: send orchestration callback if token exists
    # This prevents pipeline from hanging waiting for callback
    if final_status == 'aborted' and orchestration_token:
        try:
            sfn.send_task_failure(taskToken=orchestration_token, error='TaskAborted', cause='Task aborted via UI')
        except Exception as e:
            log.error("stop_task", "Failed orchestration callback", execution_name=execution_name, error=str(e))

    # Notify dependents ONLY for aborted (terminal status)
    # stopped is NOT terminal - task can be restarted, so don't notify dependents yet
    if final_status == 'aborted':
        if not notify_dependents_via_sfn(
            task_name=actual_task_name,
            status=final_status,
            date=item.get('date', date),
            pipeline_execution_short=pipeline_execution_short,
            pipeline_execution=pipeline_execution,
        ):
            log.error("stop_task", "Failed to notify dependents", execution_name=execution_name)
            _write_notify_warning(
                execution_name=execution_name,
                task_name=actual_task_name,
                pipeline_execution=pipeline_execution,
                pipeline_name=item.get('pipeline_name', 'unknown'),
                date=item.get('date', date),
                error='SFN start_execution failed during stop',
            )

    return cors_response(
        200,
        {
            'message': f'Task {execution_name} {final_status}. Use Restart to resume.',
            'execution_name': execution_name,
            'status': final_status,
        },
    )


def restart_task(task_name: str, event: Dict) -> Dict:
    """Restart a task by calling the restart_task_helper Step Function.

    Supports both execution_name (full) and task_name (requires date lookup).
    """
    body, err = safe_parse_body(event)
    if err:
        return err
    date = body.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    pipeline_execution = body.get('pipeline_execution', '')

    # Resolve task using unified resolver (handles both formats with pagination)
    item, execution_name = resolve_task_item(task_name, date, pipeline_execution)

    if not item:
        return cors_response(404, {'error': f'Task not found: {task_name} on {date}'})

    current_status = item.get('status', '')

    # Only terminal tasks can be restarted
    if not is_terminal_status(current_status):
        return cors_response(
            409,
            {
                'error': f'Task not in terminal state: {current_status}. Only completed/failed/skipped tasks can be restarted.',
                'execution_name': execution_name,
                'current_status': current_status,
            },
        )

    # Get the restart helper ARN from environment
    restart_helper_arn = os.environ.get('RESTART_HELPER_ARN')

    if restart_helper_arn:
        # Record manual decision for timeline
        record_manual_decision(execution_name, 'restart', 'Task restarted via UI', item)

        # Call restart_task_helper Step Function
        try:
            exec_id = uuid.uuid4().hex[:8]
            restart_name = f"restart-{execution_name[:60]}-{exec_id}"
            result = sfn.start_execution(
                stateMachineArn=restart_helper_arn,
                name=restart_name,
                input=json.dumps({'execution_name': execution_name}),
            )
            return cors_response(
                200, {'message': f'Restart initiated for {execution_name}', 'execution_arn': result['executionArn']}
            )
        except Exception as e:
            log.error("unknown", "Unexpected error", error=str(e))
            return cors_response(500, {'error': f'Failed to start restart: {str(e)}'})
    else:
        # Fallback: stop all executions and reset status
        stop_task_executions(item, 'RestartRequested', 'Task restart requested via UI')

        # Record manual decision for timeline
        record_manual_decision(execution_name, 'restart', 'Task restart (fallback) via UI', item)

        # Reset status (only if still in terminal state - race condition guard)
        RESTART_CONDITION = '#s IN (:success, :failed, :skipped, :aborted, :upstream_failed)'
        try:
            executions_repo.update(
                execution_name,
                'SET #s = :status, started_at = :started, finished_at = :finished, #e = :error',
                expr_values=build_condition_expression_values(
                    {
                        ':status': 'waiting',
                        ':started': datetime.now(timezone.utc).isoformat(),
                        ':finished': None,
                        ':error': None,
                    }
                ),
                expr_names={'#s': 'status', '#e': 'error'},
                condition_expr=RESTART_CONDITION,
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return cors_response(
                    409, {'error': 'Task state changed (already restarted?)', 'execution_name': execution_name}
                )
            else:
                raise

        return cors_response(
            200,
            {
                'message': f'Task {execution_name} reset. Re-trigger pipeline to restart.',
                'execution_name': execution_name,
            },
        )

def register(router) -> None:
    """Register the free task read routes. See ADR #97."""
    router.add('GET', '/api/tasks', get_all_tasks)
    router.add('GET', '/api/task-config', get_task_config, 'name')
    router.add('GET', '/api/task-output', get_task_output, 'name')
    router.add('GET', '/api/task-events', get_task_events, 'name')
    # Task intervention — free (ADR #110): fix a stuck/failed task on a live run.
    router.add('POST', '/api/task-retry', retry_task, 'name')
    router.add('POST', '/api/task-skip', skip_task, 'name')
    router.add('POST', '/api/task-fail', fail_task, 'name')
    router.add('POST', '/api/task-success', mark_success, 'name')
    router.add('POST', '/api/task-stop', stop_task, 'name')
    router.add('POST', '/api/task-restart', restart_task, 'name')
