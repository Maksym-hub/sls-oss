"""Task variable schema — single source of truth.

Every variable available to child tasks is defined here. Prepare_Task_Input
in run_task SFN reads this list and the drift tests in
``tests/backend/test_alerting.py::TestVariableSchemaDrift`` verify the
implementation stays in sync.

═══════════════════════════════════════════════════════════
  HOW TO ADD A NEW VARIABLE
═══════════════════════════════════════════════════════════

1. Add entry to TASK_VARIABLES dict below (source="jsonata").

2. Implement the computation in Prepare_Task_Input ($dateVars object) in:
     sam/sfn_templates/helpers/run_task/sfn.tpl.json
   Example: 'my_var': $replace($cd, '-', '')

3. Run drift tests:
     pytest tests/backend/test_alerting.py::TestVariableSchemaDrift -v

═══════════════════════════════════════════════════════════
  HISTORY
═══════════════════════════════════════════════════════════

Pre-v0.78, source could be "jsonata" (computed in Prepare_Task_Input),
"python" (computed in routes/backfill.py before SFN start), or "flag"
(set by routes/backfill.py as a boolean). After ADR #51 (Backfill
Unification), the Python builder is removed — all task vars are JSONata-
derived in Prepare_Task_Input. Removed: minus_1_month, minus_3_months,
day_of_year, week_of_year (no longer built; users compute from
current_date in task code if needed), is_reprocess (unused).
"""


TASK_VARIABLES = {
    # Date formats (from current_date — daily anchor)
    "current_date":         {"source": "jsonata", "description": "YYYY-MM-DD"},
    "PARTITION_ARG":        {"source": "jsonata", "description": "Alias for Hive partitioning"},
    "date_iso":             {"source": "jsonata", "description": "YYYY-MM-DD (same as current_date)"},
    "date_compact":         {"source": "jsonata", "description": "YYYYMMDD"},
    "date_slash":           {"source": "jsonata", "description": "YYYY/MM/DD"},
    "date_underscore":      {"source": "jsonata", "description": "YYYY_MM_DD"},

    # Date parts
    "year":                 {"source": "jsonata", "description": "YYYY"},
    "month":                {"source": "jsonata", "description": "MM"},
    "day":                  {"source": "jsonata", "description": "DD"},
    "day_of_week":          {"source": "jsonata", "description": "monday, tuesday, ..."},

    # Relative dates (simple arithmetic)
    "previous_date":        {"source": "jsonata", "description": "current_date - 1 day"},
    "next_date":            {"source": "jsonata", "description": "current_date + 1 day"},
    "minus_7_days":         {"source": "jsonata", "description": "current_date - 7 days"},
    "minus_14_days":        {"source": "jsonata", "description": "current_date - 14 days"},
    "minus_30_days":        {"source": "jsonata", "description": "current_date - 30 days"},
    "minus_7_days_compact": {"source": "jsonata", "description": "YYYYMMDD of minus_7_days"},
    "minus_30_days_compact":{"source": "jsonata", "description": "YYYYMMDD of minus_30_days"},

    # Backfill context (per ADR #51 — set in SFN input by bulk-backfill SFN,
    # propagated into task vars by Prepare_Task_Input)
    "partition_key":        {"source": "jsonata", "description": "Granularity-aware partition key"},
    "backfill_id":          {"source": "jsonata", "description": "Backfill ID (bf-XXXXXXXX) if part of a Backfill; empty otherwise"},
    "is_backfill":          {"source": "jsonata", "description": "True if this execution belongs to a Backfill"},

    # Universal flags
    "ALLOW_UNSUCCESSFUL_SPIDER_RUN": {"source": "jsonata", "description": "Always 'True' for tasks"},
}


def get_jsonata_vars():
    """Variable names computed by JSONata in Prepare_Task_Input."""
    return {k for k, v in TASK_VARIABLES.items() if v["source"] == "jsonata"}


def get_python_vars():
    """Empty set — Python builder removed in v0.78 (ADR #51).

    Kept as no-op for backward compatibility with imports.
    """
    return set()


def get_flag_vars():
    """Empty set — flag builder removed in v0.78 (ADR #51).

    is_backfill is now in jsonata source (read from SFN input).
    Kept as no-op for backward compatibility with imports.
    """
    return set()


def get_backfill_vars():
    """Variables propagated into task vars from SFN input (per ADR #51)."""
    return {"current_date", "PARTITION_ARG", "partition_key", "backfill_id", "is_backfill"}
