"""Shared task action utilities for Console API.

This module contains common functions used by both UI routes (tasks.py) 
and Slack routes (slack.py) to avoid code duplication.

Functions:
- notify_dependents_via_sfn: Invoke notify_dependents_helper SFN
- get_terminal_statuses: Get set of terminal statuses
- build_condition_expression_values: Build ExpressionAttributeValues for terminal check
"""
import json
import uuid
from typing import Dict, Set

from config import sfn, NOTIFY_DEPENDENTS_HELPER_ARN
from constants import TaskStatus, TASK_TERMINAL_STATUSES
from logger import log


def get_terminal_statuses() -> Set[str]:
    """Get the set of terminal statuses.
    
    Returns TASK_TERMINAL_STATUSES which includes:
    - success, failed, skipped, upstream_failed, aborted
    
    Use this instead of hardcoding terminal sets to ensure consistency.
    """
    return TASK_TERMINAL_STATUSES


def is_terminal_status(status: str) -> bool:
    """Check if a status is terminal."""
    return status in TASK_TERMINAL_STATUSES


def build_condition_expression_values(base_values: Dict = None) -> Dict:
    """Build ExpressionAttributeValues dict with all terminal statuses.
    
    This ensures ConditionExpression checks include ALL terminal statuses:
    - :success, :failed, :skipped, :aborted, :upstream_failed
    
    Args:
        base_values: Optional dict to merge with terminal status values
        
    Returns:
        Dict with terminal status values merged with base_values
    """
    terminal_values = {
        ':success': 'success',
        ':failed': 'failed',
        ':skipped': 'skipped',
        ':aborted': 'aborted',
        ':upstream_failed': 'upstream_failed'
    }
    
    if base_values:
        terminal_values.update(base_values)
    
    return terminal_values


# Standard ConditionExpression for checking NOT in terminal state
TERMINAL_CONDITION_EXPRESSION = 'NOT #s IN (:success, :failed, :skipped, :aborted, :upstream_failed)'

# For recovery operations (skip/mark_success on failed tasks) - only block on already-resolved states
RESOLVED_CONDITION_EXPRESSION = 'NOT #s IN (:success, :skipped)'


def build_resolved_expression_values(base_values: Dict = None) -> Dict:
    """Build ExpressionAttributeValues for resolved-only check (success, skipped)."""
    resolved_values = {
        ':success': 'success',
        ':skipped': 'skipped',
    }
    if base_values:
        return {**resolved_values, **base_values}
    return resolved_values


def notify_dependents_via_sfn(
    task_name: str,
    status: str,
    date: str,
    pipeline_execution_short: str,
    pipeline_execution: str = ''
) -> bool:
    """Invoke notify_dependents_helper SFN to signal waiting tasks.
    
    Replaces EventBridge-based notify_dependents with direct SFN call.
    Returns True on success, False on failure (logged but non-blocking).
    
    Args:
        task_name: Name of the completed task
        status: Terminal status (success, failed, skipped, aborted)
        date: Execution date (YYYY-MM-DD)
        pipeline_execution_short: Short pipeline execution ID
        pipeline_execution: Full pipeline execution ID (optional)
        
    Returns:
        True if SFN started successfully, False otherwise
    """
    if not NOTIFY_DEPENDENTS_HELPER_ARN:
        log.warn("notify_dependents_via_sfn", "NOTIFY_DEPENDENTS_HELPER_ARN not configured")
        return False
    
    try:
        # Use deterministic name to prevent duplicate notifications on retry
        exec_id = uuid.uuid4().hex[:8]
        safe_task = task_name.replace('/', '-').replace('.', '-')[:40]
        notify_name = f"notify-{safe_task}-{status}-{date}-{exec_id}"
        sfn.start_execution(
            stateMachineArn=NOTIFY_DEPENDENTS_HELPER_ARN,
            name=notify_name,
            input=json.dumps({
                'task_name': task_name,
                'status': status,
                'date': date,
                'pipeline_execution_short': pipeline_execution_short,
                'pipeline_execution': pipeline_execution
            })
        )
        log.info("notify_dependents_via_sfn", "Started SFN", task=task_name, status=status)
        return True
    except Exception as e:
        log.error("notify_dependents_via_sfn", "Failed to start SFN", task=task_name, error=str(e))
        return False


def extract_pipeline_execution_short(item: Dict, execution_name: str) -> str:
    """Extract pipeline_execution_short from item or execution_name.
    
    Args:
        item: DynamoDB item with task info
        execution_name: Task execution name (format: task_name-date-short_id)
        
    Returns:
        Pipeline execution short ID
    """
    # First priority: use stored value
    pipeline_execution_short = item.get('pipeline_execution_short', '')
    if pipeline_execution_short:
        return pipeline_execution_short
    
    # Second priority: compute from pipeline_execution using same logic as wrapper
    pipeline_execution = item.get('pipeline_execution', '')
    if pipeline_execution:
        # Import here to avoid circular dependency
        from utils import compute_pipeline_execution_short
        return compute_pipeline_execution_short(pipeline_execution)
    
    # Last resort: extract from execution_name suffix
    if execution_name.count('-') >= 3:
        # Format: task_name-YYYY-MM-DD-short_id
        return execution_name.rsplit('-', 1)[-1]
    
    return ''
