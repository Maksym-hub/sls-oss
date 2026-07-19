"""extract_pipeline_execution_short — its three-tier fallback logic had no direct test
anywhere in either repo. `task_actions.py` itself had no test file at all; the only
references were mocks in EE's Slack-action tests (`test_slack_actions.py`), which
isolate the Slack orchestration, not this function's own fallback correctness.

Found auditing this session's changes against the rest of the codebase (Principle #14):
mocking it there is a legitimate isolation of a *different* surface, but that leaves
this function's own three-tier priority never exercised for real — the exact gap #14
warns produces "a green suite where the actual bug hides". No boundary here to mock;
it is pure string logic over a dict and a name.
"""
from task_actions import extract_pipeline_execution_short


class TestExtractPipelineExecutionShort:
    def test_first_priority_is_the_stored_value(self):
        item = {'pipeline_execution_short': 'stored123', 'pipeline_execution': 'ignored'}
        assert extract_pipeline_execution_short(item, 'extract-2026-07-16-ignored') == 'stored123'

    def test_second_priority_computes_from_pipeline_execution(self):
        # compute_pipeline_execution_short: last 20 chars, strip '.' and ':'
        item = {'pipeline_execution': 'sales-hourly-2026-07-16-abc123def456'}
        expected_full = item['pipeline_execution'][-20:].replace('.', '').replace(':', '')
        assert extract_pipeline_execution_short(item, 'irrelevant') == expected_full

    def test_third_priority_falls_back_to_the_execution_name_suffix(self):
        item = {}      # no stored value, no pipeline_execution
        assert extract_pipeline_execution_short(item, 'extract-2026-07-16-abc123') == 'abc123'

    def test_execution_name_with_too_few_hyphens_yields_nothing(self):
        """The suffix fallback only fires on the task_name-YYYY-MM-DD-short_id shape
        (>= 3 hyphens); anything shorter has no reliable short id to extract."""
        item = {}
        assert extract_pipeline_execution_short(item, 'ab-cd') == ''

    def test_empty_stored_value_falls_through_rather_than_short_circuiting(self):
        """An empty string is falsy, same as absent — must not be returned as-is."""
        item = {'pipeline_execution_short': '', 'pipeline_execution': 'p-2026-07-16-xyz'}
        assert extract_pipeline_execution_short(item, 'irrelevant') != ''

    def test_priority_order_is_stored_then_computed_then_suffix(self):
        """All three sources present at once — the stored value must win."""
        item = {'pipeline_execution_short': 'winner', 'pipeline_execution': 'p-loses-too'}
        assert extract_pipeline_execution_short(item, 'extract-2026-07-16-loses') == 'winner'
