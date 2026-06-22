"""
Evaluate Dependencies Lambda

Minimal Lambda for operations Step Functions cannot do natively:
1. BatchGetItem - fetch all dependency statuses in one call
2. Evaluate trigger_rule - complex logic (11 Airflow rules)
3. Check pipeline paused status

Called from notify_dependents SFN helper.

Input:
{
    "dependencies": ["task_a", "task_b"],
    "trigger_rule": "all_success",
    "date": "2026-01-19",
    "pipeline_execution_short": "abc123",
    "pipeline_execution": "pipeline-2026-01-19-abc123"
}

Output:
{
    "is_ready": true,
    "is_blocked": false,
    "is_paused": false,
    "reason": "all_success",
    "dep_statuses": ["success", "success"],
    "counts": {
        "total": 2,
        "success": 2,
        "failed": 0,
        "skipped": 0,
        "pending": 0
    }
}
"""

import os
from typing import List, Dict, Tuple, Any

from constants import (TaskStatus, TASK_TERMINAL_STATUSES, TASK_SUCCESS_STATUSES, TASK_FAILURE_STATUSES)
# v0.79.3 (ADR #75) — DAL repository pattern for all DynamoDB access.
# All raw boto3 calls now live in dal/__init__.py; tests mock this repo
# instead of patching boto3 directly.
from dal import tokens_repo
# v0.79.4 (ADR #76) — structured JSON logging via shared logger module
# (copied to each Lambda by sync_loggers Make target; canonical source
# in sam/lambdas/_shared/logger.py).
from logger import log

TOKENS_TABLE = os.environ.get('TOKENS_TABLE', 'pipeline-tokens')

# Status categories - use centralized definitions
TERMINAL_SUCCESS = TASK_SUCCESS_STATUSES
TERMINAL_FAILURE = TASK_FAILURE_STATUSES
TERMINAL_STATUSES = TASK_TERMINAL_STATUSES


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main handler - evaluate if dependencies satisfy trigger_rule."""
    try:
        return _handler(event, context)
    except Exception as e:
        log.error("handler", "Unhandled error", error_type=type(e).__name__, error=str(e), event=event)
        raise


def _handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Inner handler."""
    dependencies = event.get('dependencies', [])
    trigger_rule = event.get('trigger_rule', 'all_success')
    date = event.get('date', '')
    pipeline_execution_short = event.get('pipeline_execution_short', '')
    pipeline_execution = event.get('pipeline_execution', '')
    
    # Handle empty dependencies
    if not dependencies:
        return {
            'is_ready': True,
            'is_blocked': False,
            'is_paused': False,
            'deps_satisfied': True,  # No deps = satisfied by default
            'reason': 'no_deps',
            'dep_statuses': [],
            'counts': _empty_counts()
        }
    
    # 1. BatchGetItem - SFN doesn't support this
    dep_statuses = _batch_get_dep_statuses(dependencies, date, pipeline_execution_short)
    
    # 2. Check if pipeline is paused
    is_paused = _is_pipeline_paused(pipeline_execution) if pipeline_execution else False
    
    # 3. Evaluate trigger rule
    deps_satisfied, reason = _check_trigger_rule(trigger_rule, dep_statuses)
    
    # 4. Check if permanently blocked (all done but rule not satisfied)
    all_done = all(s in TERMINAL_STATUSES for s in dep_statuses)
    is_blocked = all_done and not deps_satisfied
    
    # 5. Calculate counts for observability
    counts = _calculate_counts(dep_statuses)
    
    # is_ready = deps satisfied AND pipeline not paused
    # deps_satisfied = deps satisfy trigger_rule (regardless of pause)
    return {
        'is_ready': deps_satisfied and not is_paused,
        'is_blocked': is_blocked,
        'is_paused': is_paused,
        'deps_satisfied': deps_satisfied,  # NEW: true if deps satisfy rule (even if paused)
        'reason': reason,
        'dep_statuses': dep_statuses,
        'counts': counts
    }


def _batch_get_dep_statuses(
    dependencies: List[str], 
    date: str, 
    pipeline_execution_short: str
) -> List[str]:
    """
    Batch fetch dependency statuses using BatchGetItem.
    
    Returns statuses in same order as dependencies list.
    SFN doesn't support BatchGetItem, hence this Lambda.
    """
    if not dependencies:
        return []

    # v0.79.3 (ADR #75) — DAL repo replaces inline batch_get_item +
    # retry loop + fallback. The retry semantics are preserved verbatim
    # inside TokensRepo.batch_get_statuses.
    exec_names = [
        f"{dep}-{date}-{pipeline_execution_short}"
        for dep in dependencies
    ]
    results = tokens_repo.batch_get_statuses(exec_names)
    # Return statuses in original order
    return [results[name] for name in exec_names]


def _is_pipeline_paused(pipeline_execution: str) -> bool:
    """Check if pipeline execution is paused."""
    if not pipeline_execution:
        return False

    try:
        # v0.79.3 (ADR #75) — single DAL call; repo owns the pause-key
        # construction and the get_item shape.
        return tokens_repo.is_paused(pipeline_execution)
    except Exception as e:
        log.error("_is_pipeline_paused", "Failed to read pause flag", error_type=type(e).__name__, error=str(e), pipeline_execution=pipeline_execution)
        # Re-raise so SFN can catch and log — silently returning False would
        # cause tasks to start when pipeline is actually paused
        raise


def _check_trigger_rule(trigger_rule: str, dep_statuses: List[str]) -> Tuple[bool, str]:
    """
    Evaluate if trigger_rule is satisfied.
    
    Airflow 3.x compatible trigger rules:
    - all_success: All deps success/skipped (default)
    - one_success: At least one success (doesn't wait for all!)
    - all_failed: All deps failed
    - one_failed: At least one failed (doesn't wait for all!)
    - all_done: All deps terminal (any status)
    - one_done: At least one terminal (doesn't wait for all!)
    - all_skipped: All deps skipped
    - none_failed: No failures (success/skipped OK)
    - none_skipped: No skips
    - none_failed_min_one_success: None failed + at least one success
    - all_done_min_one_success: All done + at least one success
    
    Returns: (is_satisfied, reason)
    """
    if not dep_statuses:
        return True, "no_deps"
    
    counts = _calculate_counts(dep_statuses)
    total = counts['total']
    success = counts['success']
    failed = counts['failed']
    skipped = counts['skipped']
    pending = counts['pending']
    done = total - pending
    ok = success + skipped  # success or skipped = OK to continue
    
    rules = {
        'all_success': lambda: (
            (pending == 0 and ok == total, "all_success") if pending == 0 and ok == total
            else (False, f"waiting for {pending} deps" if pending > 0 else f"{failed} failed")
        ),
        'one_success': lambda: (
            (True, "one_success") if success >= 1
            else (False, "waiting, no success yet" if pending > 0 else "none succeeded")
        ),
        'all_failed': lambda: (
            (pending == 0 and failed == total, "all_failed") if pending == 0 and failed == total
            else (False, f"waiting for {pending} deps" if pending > 0 else f"not all failed ({failed}/{total})")
        ),
        'one_failed': lambda: (
            (True, "one_failed") if failed >= 1
            else (False, "waiting, no failure yet" if pending > 0 else "none failed")
        ),
        'all_done': lambda: (
            (True, "all_done") if pending == 0
            else (False, f"waiting for {pending} deps")
        ),
        'one_done': lambda: (
            (True, "one_done") if done >= 1
            else (False, "waiting for first completion")
        ),
        'all_skipped': lambda: (
            (pending == 0 and skipped == total, "all_skipped") if pending == 0 and skipped == total
            else (False, f"waiting for {pending} deps" if pending > 0 else f"not all skipped ({skipped}/{total})")
        ),
        'none_failed': lambda: (
            (False, f"{failed} deps failed") if failed > 0
            else ((True, "none_failed") if pending == 0 else (False, f"waiting for {pending} deps"))
        ),
        'none_skipped': lambda: (
            (False, f"{skipped} deps skipped") if skipped > 0
            else ((True, "none_skipped") if pending == 0 else (False, f"waiting for {pending} deps"))
        ),
        'none_failed_min_one_success': lambda: (
            (False, f"{failed} deps failed") if failed > 0
            else ((True, "none_failed_min_one_success") if pending == 0 and success >= 1
                  else (False, f"waiting for {pending} deps" if pending > 0 else "none failed but no success"))
        ),
        'all_done_min_one_success': lambda: (
            (True, "all_done_min_one_success") if pending == 0 and success >= 1
            else (False, f"waiting for {pending} deps" if pending > 0 else "all done but no success")
        ),
    }
    
    if trigger_rule in rules:
        return rules[trigger_rule]()
    
    # Default to all_success for unknown rules
    log.warn("_check_trigger_rule", "Unknown trigger_rule; defaulting to all_success", trigger_rule=trigger_rule)
    return rules['all_success']()


def _calculate_counts(dep_statuses: List[str]) -> Dict[str, int]:
    """Calculate status counts for observability."""
    success = sum(1 for s in dep_statuses if s == 'success')
    failed = sum(1 for s in dep_statuses if s in TERMINAL_FAILURE)
    skipped = sum(1 for s in dep_statuses if s == 'skipped')
    pending = sum(1 for s in dep_statuses if s not in TERMINAL_STATUSES)
    
    return {
        'total': len(dep_statuses),
        'success': success,
        'failed': failed,
        'skipped': skipped,
        'pending': pending
    }


def _empty_counts() -> Dict[str, int]:
    """Return empty counts structure."""
    return {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'pending': 0
    }
