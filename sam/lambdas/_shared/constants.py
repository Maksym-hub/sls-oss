"""
Shared Constants for Lambda Functions

This is the SINGLE SOURCE OF TRUTH for status constants across all Lambdas.
When updating these values, ensure all Lambdas that use them are updated.

IMPORTANT: Lambda functions cannot share code directly. Each Lambda that needs
these constants should either:
1. Copy this file into their directory during build
2. Use a Lambda Layer (recommended for production)
3. Manually keep their local constants in sync with this file

Lambdas using these constants:
- console_api (has own copy in constants.py)
- evaluate_deps (has own copy inline)
- check_assets (doesn't need - only checks asset freshness)
- notify_asset_subscribers (doesn't need - only notifies)
"""


class TaskStatus:
    """Task execution status values.

    v0.79.5 (ADR #77) — class-level sets moved to module-level
    constants generated from polyris/constants.py.
    """
    WAITING = 'waiting'
    WAITING_PAUSED = 'waiting_paused'
    WAITING_DELAY = 'waiting_delay'
    DEPS_READY = 'deps_ready'
    RUNNING = 'running'
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    STOPPED = 'stopped'  # Non-terminal: task can be restarted
    ABORTED = 'aborted'
    UPSTREAM_FAILED = 'upstream_failed'
    WAITING_DECISION = 'waiting_decision'


# v0.79.5 (ADR #77) — module-level sets (re-exported from generated).
# Lambda using this _shared copy also needs constants_generated.py
# in its deploy package; `make sync-constants` handles that copy.
# Import lazily so import-time failure (missing generated file) is
# diagnosable from the _shared copy.
try:
    from constants_generated import (
        TASK_TERMINAL_STATUSES,
        TASK_SUCCESS_STATUSES,
        TASK_FAILURE_STATUSES,
        TASK_ACTIVE_STATUSES,
        TASK_WAITING_STATUSES,
        TASK_STOPPABLE_STATUSES,
    )
except ImportError:
    # Fallback (mostly for direct unit tests of _shared/constants.py):
    # these match the canonical values in polyris/constants.py.
    TASK_TERMINAL_STATUSES = {'success', 'succeeded', 'failed', 'skipped',
                              'aborted', 'upstream_failed'}
    TASK_SUCCESS_STATUSES = {'success', 'succeeded', 'skipped'}
    TASK_FAILURE_STATUSES = {'failed', 'upstream_failed', 'aborted'}
    TASK_ACTIVE_STATUSES = {'running', 'pending'}
    TASK_WAITING_STATUSES = {'waiting', 'waiting_paused', 'waiting_delay',
                             'deps_ready', 'waiting_decision'}
    TASK_STOPPABLE_STATUSES = (TASK_ACTIVE_STATUSES | TASK_WAITING_STATUSES)


class TriggerRule:
    """Airflow-compatible trigger rules."""
    ALL_SUCCESS = 'all_success'
    ALL_FAILED = 'all_failed'
    ALL_DONE = 'all_done'
    ALL_DONE_MIN_ONE_SUCCESS = 'all_done_min_one_success'
    ALL_SKIPPED = 'all_skipped'
    ONE_SUCCESS = 'one_success'
    ONE_FAILED = 'one_failed'
    ONE_DONE = 'one_done'
    NONE_FAILED = 'none_failed'
    NONE_FAILED_MIN_ONE_SUCCESS = 'none_failed_min_one_success'
    NONE_SKIPPED = 'none_skipped'


class AssetOperator:
    """Asset dependency operators."""
    AND = 'AND'  # All assets required
    OR = 'OR'    # Any asset triggers


# ──────────────────────────────────────────────────────────────────────────────
# ExecutionStatus normalization (ADR #71, v0.78.14)
# ──────────────────────────────────────────────────────────────────────────────
# SFN's DescribeExecution API returns statuses in UPPERCASE
# ('RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED'). Internal code
# and DDB write lowercase. Without a single normalization point, raw SFN
# values can leak through API responses to the UI, which historically had to
# accept BOTH cases in its TypeScript union type (mess). This helper
# centralizes the mapping; call it at every boundary where SFN status enters
# our system (read path) AND before writing status to DDB (write path).
#
# Canonical lowercase values (SFN-aligned):
#   'running' / 'succeeded' / 'failed' / 'timed_out' / 'aborted' / 'stopped'

EXECUTION_STATUS_CANONICAL = {
    'running', 'succeeded', 'failed', 'timed_out', 'aborted', 'stopped',
}

_EXECUTION_STATUS_UPPERCASE_MAP = {
    'RUNNING': 'running',
    'SUCCEEDED': 'succeeded',
    'FAILED': 'failed',
    'TIMED_OUT': 'timed_out',
    'ABORTED': 'aborted',
    'STOPPED': 'stopped',
    # Common variant — some legacy code wrote 'success' (TaskStatus form)
    # instead of 'succeeded' (ExecutionStatus form). Normalize to canonical.
    'SUCCESS': 'succeeded',
    'success': 'succeeded',
}


def normalize_execution_status(status, log_warn=None):
    """Normalize a pipeline-execution status to the canonical lowercase form.

    Args:
        status: input status string (may be UPPERCASE from SFN, lowercase
                from DDB, or already canonical).
        log_warn: optional callable accepting (message, **context) to emit
                  a warning when an unexpected value is seen. Pass a
                  logger.warn-like function. Pass None to skip logging.

    Returns:
        Canonical lowercase status if mappable; original input otherwise
        (callers decide how strict to be).
    """
    if status is None:
        return None
    if status in EXECUTION_STATUS_CANONICAL:
        return status  # already canonical
    mapped = _EXECUTION_STATUS_UPPERCASE_MAP.get(status)
    if mapped is not None:
        return mapped
    # Unknown — log diagnostically and return as-is (don't drop the value)
    if log_warn is not None:
        log_warn("Unexpected execution status; cannot normalize",
                 status=status)
    return status
