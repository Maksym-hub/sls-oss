"""
Constants and type definitions for SFN-DSL.
"""

from enum import Enum
from typing import FrozenSet, Literal, Set


# =============================================================================
# Task Status Lifecycle
# =============================================================================

class TaskStatus(str, Enum):
    """
    Task execution status lifecycle.
    
    Lifecycle diagram:
    
        ┌─────────────────────────────────────────────────────────────┐
        │                         WAITING                             │
        │  (initial state - waiting for dependencies or schedule)     │
        └─────────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────┐     ┌───────────────────┐
        │    DEPS_READY     │     │  WAITING_PAUSED   │
        │ (deps satisfied)  │     │ (pipeline paused) │
        └───────────────────┘     └───────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  WAITING_DELAY    │
        │ (countdown timer) │
        └───────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │      RUNNING      │
        │ (task executing)  │
        └───────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
    ┌─────────┐           ┌─────────┐
    │ SUCCESS │           │ FAILED  │
    └─────────┘           └─────────┘
    
    Other terminal states:
    - SKIPPED: Task was skipped (manual or trigger rule)
    - ABORTED: Task was aborted (system)
    - UPSTREAM_FAILED: Upstream dependency failed (trigger rule blocked)
    
    Non-terminal stop state:
    - STOPPED: Task was stopped via UI (can be restarted)
    """
    # Active states
    WAITING = "waiting"                    # Initial: waiting for dependencies
    DEPS_READY = "deps_ready"              # Dependencies satisfied, ready to run
    WAITING_DELAY = "waiting_delay"        # In countdown timer (wait_before)
    WAITING_PAUSED = "waiting_paused"      # Pipeline is paused
    WAITING_DECISION = "waiting_decision"  # Waiting for manual decision
    RUNNING = "running"                    # Task is executing
    PENDING = "pending"                    # Pending redrive (SFN)
    
    # Terminal success states
    SUCCESS = "success"                    # Task completed successfully
    SUCCEEDED = "succeeded"                # Alias for success (Airflow compat)
    
    # Terminal failure states
    FAILED = "failed"                      # Task execution failed
    UPSTREAM_FAILED = "upstream_failed"    # Blocked by upstream failure
    ABORTED = "aborted"                    # Task was aborted (system)
    
    # Terminal skip state
    SKIPPED = "skipped"                    # Task was skipped
    
    # Non-terminal stop state (can be restarted)
    STOPPED = "stopped"                    # Task was stopped via UI


# Status sets for common checks
# Note: STOPPED is NOT terminal - task can be restarted
TERMINAL_STATUSES: Set[str] = {
    TaskStatus.SUCCESS.value,
    TaskStatus.SUCCEEDED.value,
    TaskStatus.FAILED.value,
    TaskStatus.SKIPPED.value,
    TaskStatus.ABORTED.value,
    TaskStatus.UPSTREAM_FAILED.value,
}

SUCCESS_STATUSES: Set[str] = {
    TaskStatus.SUCCESS.value,
    TaskStatus.SUCCEEDED.value,
    TaskStatus.SKIPPED.value,  # Skipped is OK for downstream
}

FAILURE_STATUSES: Set[str] = {
    TaskStatus.FAILED.value,
    TaskStatus.UPSTREAM_FAILED.value,
    TaskStatus.ABORTED.value,
}

ACTIVE_STATUSES: Set[str] = {
    TaskStatus.RUNNING.value,
    TaskStatus.PENDING.value,
}

WAITING_STATUSES: Set[str] = {
    TaskStatus.WAITING.value,
    TaskStatus.DEPS_READY.value,
    TaskStatus.WAITING_DELAY.value,
    TaskStatus.WAITING_PAUSED.value,
    TaskStatus.WAITING_DECISION.value,
}

# Statuses that show countdown in UI
COUNTDOWN_STATUSES: Set[str] = {
    TaskStatus.DEPS_READY.value,
    TaskStatus.WAITING_DELAY.value,
}

# Statuses that can be stopped via UI
STOPPABLE_STATUSES: Set[str] = {
    TaskStatus.RUNNING.value,
    TaskStatus.PENDING.value,
    TaskStatus.WAITING.value,
    TaskStatus.WAITING_PAUSED.value,
    TaskStatus.WAITING_DELAY.value,
    TaskStatus.DEPS_READY.value,
    TaskStatus.WAITING_DECISION.value,
}


# =============================================================================
# Trigger Rules (Airflow 3.x compatible)
# =============================================================================


# Type alias for trigger_rule with IDE autocomplete
TriggerRuleLiteral = Literal[
    "all_success",           # All upstream tasks succeeded (default)
    "all_failed",            # All upstream tasks failed
    "all_done",              # All upstream tasks done (any status)
    "all_done_min_one_success",  # All done + at least one success
    "all_skipped",           # All upstream tasks skipped
    "one_failed",            # At least one failed (doesn't wait for all)
    "one_success",           # At least one succeeded (doesn't wait for all)
    "one_done",              # At least one done (doesn't wait for all)
    "none_failed",           # No task failed
    "none_failed_min_one_success",  # None failed + at least one success
    "none_skipped",          # No task skipped
]


# Task type for service-specific execution
TaskTypeLiteral = Literal[
    "sfn",       # Nested Step Function (default)
    "lambda",    # Direct Lambda invocation
    "glue",      # Glue Job
    "ecs",       # ECS/Fargate task
    "athena",    # Athena query
    "emr",       # EMR step
    "batch",     # AWS Batch job
    "sagemaker", # SageMaker processing/training
]


# Schedule presets (Airflow-compatible)
SCHEDULE_PRESETS = {
    "@once": None,
    "@hourly": "rate(1 hour)",
    "@daily": "rate(1 day)",
    "@weekly": "rate(7 days)",
    "@monthly": "cron(0 0 1 * ? *)",
    "@yearly": "cron(0 0 1 1 ? *)",
    "@annually": "cron(0 0 1 1 ? *)",
}


class TriggerRule:
    """
    Trigger rule constants. 100% Airflow 3.1.5-compatible.
    
    See: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#trigger-rules
    """
    ALL_SUCCESS = "all_success"           # All upstream tasks have succeeded (default)
    ALL_FAILED = "all_failed"             # All upstream tasks are in failed/upstream_failed state
    ALL_DONE = "all_done"                 # All upstream tasks are done with execution
    ALL_DONE_MIN_ONE_SUCCESS = "all_done_min_one_success"  # All done + at least one success
    ALL_SKIPPED = "all_skipped"           # All upstream tasks are in skipped state
    ONE_FAILED = "one_failed"             # At least one failed (does NOT wait for all)
    ONE_SUCCESS = "one_success"           # At least one succeeded (does NOT wait for all)
    ONE_DONE = "one_done"                 # At least one done (does NOT wait for all)
    NONE_FAILED = "none_failed"           # No task failed (success or skipped OK)
    NONE_FAILED_MIN_ONE_SUCCESS = "none_failed_min_one_success"  # None failed + at least one success
    NONE_SKIPPED = "none_skipped"         # No task skipped


# =============================================================================
# Pipeline-level statuses (v0.79.0 SSoT consolidation, ADR #72)
# =============================================================================

class PipelineStatus:
    """Aggregate pipeline status — derived from task counts for "today's"
    view in the pipelines sidebar."""
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RUNNING = "running"
    WAITING = "waiting"
    IDLE = "idle"


# =============================================================================
# ExecutionStatus — pipeline-execution-level status (SFN-aligned lowercase)
# Canonical from v0.78.14 (ADR #71); lifted into SDK at v0.79.0.
# =============================================================================

class ExecutionStatus:
    """Pipeline-execution status. Canonical lowercase form.

    AWS Step Functions returns these statuses in UPPERCASE; normalize at
    the boundary using `normalize_execution_status` before use.
    """
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"
    STOPPED = "stopped"
    RECOVERED = "recovered"  # Derived: SFN reports failed but all tasks resolved


EXECUTION_STATUS_CANONICAL: Set[str] = {
    ExecutionStatus.RUNNING,
    ExecutionStatus.SUCCEEDED,
    ExecutionStatus.FAILED,
    ExecutionStatus.TIMED_OUT,
    ExecutionStatus.ABORTED,
    ExecutionStatus.STOPPED,
    ExecutionStatus.RECOVERED,
}

_EXECUTION_STATUS_UPPERCASE_MAP = {
    'RUNNING': ExecutionStatus.RUNNING,
    'SUCCEEDED': ExecutionStatus.SUCCEEDED,
    'FAILED': ExecutionStatus.FAILED,
    'TIMED_OUT': ExecutionStatus.TIMED_OUT,
    'ABORTED': ExecutionStatus.ABORTED,
    'STOPPED': ExecutionStatus.STOPPED,
    # Legacy: some code wrote 'success' (TaskStatus form) for executions
    'SUCCESS': ExecutionStatus.SUCCEEDED,
    'success': ExecutionStatus.SUCCEEDED,
}


def normalize_execution_status(status, log_warn=None):
    """Normalize a pipeline-execution status to canonical lowercase.

    See ADR #71 for full reasoning. Idempotent on canonical inputs.
    """
    if status is None:
        return None
    if status in EXECUTION_STATUS_CANONICAL:
        return status
    mapped = _EXECUTION_STATUS_UPPERCASE_MAP.get(status)
    if mapped is not None:
        return mapped
    if log_warn is not None:
        log_warn("Unexpected execution status; cannot normalize",
                 status=status)
    return status


# =============================================================================
# Backfill-level statuses + enums
# =============================================================================

class BackfillStatus:
    """Backfill status — aggregate of N partition outcomes (ADR #54)."""
    PENDING = "pending"      # record created; bulk SFN not yet running Map
    RUNNING = "running"      # Map iterating; at least one partition in flight
    COMPLETED = "completed"  # all attempted partitions succeeded
    FAILED = "failed"        # all attempted partitions failed (zero succeeded)
    PARTIAL = "partial"      # some succeeded, some failed (mixed outcome)
    CANCELED = "canceled"    # user-initiated cancel via /api/backfills/{id}/cancel


BACKFILL_TERMINAL_STATUSES: Set[str] = {
    BackfillStatus.COMPLETED,
    BackfillStatus.FAILED,
    BackfillStatus.PARTIAL,
    BackfillStatus.CANCELED,
}

BACKFILL_ACTIVE_STATUSES: Set[str] = {
    BackfillStatus.PENDING,
    BackfillStatus.RUNNING,
}


class BackfillCascade:
    """Asset backfill cascade mode — how downstream consumers are handled."""
    AUTO = "auto"  # Default: trigger downstreams that depend on the affected asset
    ALL = "all"    # Trigger entire downstream subgraph
    NONE = "none"  # Don't trigger anything downstream


class BackfillUpstream:
    """Asset backfill upstream lineage build mode (ADR #92).

    Mirrors BackfillCascade on the upstream side. Codegen-generated into
    constants_generated.py (backend) and ui/src/generated/enums.ts (UI) so the
    backend validator and the TS type derive from this one definition rather
    than hand-maintained copies (ADR #94)."""
    OFF = "off"      # Default: build only the producer (input assumed present)
    SMART = "smart"  # Build missing same-pipeline ancestors (frontier stops at present output)
    FORCE = "force"  # Rebuild the full same-pipeline lineage regardless of presence


# Canonical registry of backfill error codes returned by the backfill route to
# the client. Codegen-generated into ui/src/generated/enums.ts; the UI friendly
# error map (utils/backfillErrors.ts) must cover every code here, gated by
# backfillErrors.test.ts (keys ⊇ codes). The registry itself is pinned to the
# route's emitted literals by test_backfill_error_registry (registry == emitted)
# so neither side silently drifts (ADR #94). Unlike the enum value objects of
# ADR #93, the code→friendly-text map is hand-authored content and cannot be
# generated away; it can only be gated — hence a registry rather than a single
# generated map.
BACKFILL_ERROR_CODES: FrozenSet[str] = frozenset({
    "already_terminal",
    "child_name_too_long",
    "concurrent_backfill_active",
    "granularity_override_not_allowed",
    "id_space_exhausted",
    "internal_error",
    "invalid_downstream",
    "invalid_downstream_for_pipeline_target",
    "invalid_granularity_override",
    "invalid_options",
    "invalid_partition_format",
    "invalid_partition_keys",
    "invalid_partitions",
    "invalid_target",
    "invalid_target_type",
    "invalid_tasks",
    "invalid_upstream",
    "invalid_upstream_for_pipeline_target",
    "malformed_body",
    "malformed_parent",
    "misconfigured",
    "multi_producer_asset",
    "no_producer",
    "not_eligible",
    "not_found",
    "nothing_to_retry",
    "nothing_to_run",
    "partition_keys_not_failed",
    "producer_pipeline_missing",
    "range_too_large",
    "sfn_start_failed",
    "status_race",
    "target_not_found",
    "throttled",
    "unreachable_target_type",
    "upstream_cycle",
})


class BackfillGranularity:
    """Backfill partition cadence (ADR #50)."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# =============================================================================
# Asset staleness
# =============================================================================

class StalenessStatus:
    """Asset freshness vs declared SLA window."""
    FRESH = "fresh"
    WARNING = "warning"
    STALE = "stale"
    UNKNOWN = "unknown"


# =============================================================================
# Asset trigger operator
# =============================================================================

class AssetOperator:
    """How multiple asset dependencies combine to trigger downstream."""
    AND = "AND"  # All assets required
    OR = "OR"    # Any asset triggers


# =============================================================================
# task_config contract (SDK writer <-> run_task wrapper reader) — ADR #108
# =============================================================================

class TaskConfigKey(str, Enum):
    """
    Keys of the per-task `task_config` dict the SDK passes to the run_task
    wrapper. This is the single source of truth for BOTH sides of the contract:
    the writer (generators) keys its dicts with these members, and the template
    contract test asserts every `task_config.<key>` the wrapper reads is
    declared here. Add a key here first; a bare string literal on either side
    fails tests/sdk/test_task_config_contract.py.

    str-Enum: members compare and JSON-serialize as their plain string values.
    """
    # lambda
    FUNCTION_NAME = "function_name"
    PAYLOAD = "payload"
    # glue
    JOB_NAME = "job_name"
    ARGUMENTS = "arguments"
    WORKER_TYPE = "worker_type"
    NUMBER_OF_WORKERS = "number_of_workers"
    ALLOCATED_CAPACITY = "allocated_capacity"
    # ecs
    CLUSTER = "cluster"
    TASK_DEFINITION = "task_definition"
    LAUNCH_TYPE = "launch_type"
    SUBNETS = "subnets"
    SECURITY_GROUPS = "security_groups"
    ASSIGN_PUBLIC_IP = "assign_public_ip"
    OVERRIDES = "overrides"
    # athena
    QUERY_STRING = "query_string"
    DATABASE = "database"
    OUTPUT_LOCATION = "output_location"
    WORKGROUP = "workgroup"
    # emr
    CLUSTER_ID = "cluster_id"
    STEP = "step"
    # batch
    JOB_DEFINITION = "job_definition"
    JOB_QUEUE = "job_queue"
    PARAMETERS = "parameters"
    # retry policy (ADR #107)
    RETRIES = "retries"
    RETRY_DELAY = "retry_delay"
    RETRY_BACKOFF = "retry_backoff"
    MAX_RETRY_DELAY = "max_retry_delay"
    RETRY_JITTER = "retry_jitter"
