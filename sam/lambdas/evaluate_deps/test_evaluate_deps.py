"""
Tests for evaluate_deps Lambda

Coverage:
- All 11 trigger_rules
- Edge cases: empty deps, all pending, mixed statuses
- Pause handling
- Error scenarios
"""

import pytest
# pytest-mock: mocker fixture used for patching
import sys
import os

# Add lambda to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate_deps.index import (
    handler,
    _check_trigger_rule,
    _calculate_counts,
    _is_pipeline_paused,
    TERMINAL_SUCCESS,
    TERMINAL_FAILURE,
    TERMINAL_STATUSES,
)


class TestCheckTriggerRule:
    """Test trigger_rule evaluation logic."""
    
    # ===== all_success (default) =====
    
    def test_all_success_with_all_success(self):
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'success'])
        assert is_ready is True
        assert reason == 'all_success'
    
    def test_all_success_with_success_and_skipped(self):
        """Skipped counts as OK for all_success."""
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'skipped'])
        assert is_ready is True
        assert reason == 'all_success'
    
    def test_all_success_with_failure(self):
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'failed'])
        assert is_ready is False
        assert 'failed' in reason
    
    def test_all_success_with_pending(self):
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'waiting'])
        assert is_ready is False
        assert 'waiting' in reason
    
    def test_all_success_with_upstream_failed(self):
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'upstream_failed'])
        assert is_ready is False
        assert 'failed' in reason
    
    def test_all_success_with_aborted(self):
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'aborted'])
        assert is_ready is False
        assert 'failed' in reason
    
    # ===== one_success =====
    
    def test_one_success_with_one(self):
        """Triggers immediately when one succeeds - doesn't wait!"""
        is_ready, reason = _check_trigger_rule('one_success', ['success', 'waiting'])
        assert is_ready is True
        assert reason == 'one_success'
    
    def test_one_success_none_yet(self):
        is_ready, reason = _check_trigger_rule('one_success', ['waiting', 'running'])
        assert is_ready is False
        assert 'waiting' in reason
    
    def test_one_success_all_failed(self):
        is_ready, reason = _check_trigger_rule('one_success', ['failed', 'failed'])
        assert is_ready is False
        assert 'none succeeded' in reason
    
    # ===== all_failed =====
    
    def test_all_failed_with_all_failed(self):
        is_ready, reason = _check_trigger_rule('all_failed', ['failed', 'upstream_failed', 'aborted'])
        assert is_ready is True
        assert reason == 'all_failed'
    
    def test_all_failed_with_some_success(self):
        is_ready, reason = _check_trigger_rule('all_failed', ['failed', 'success'])
        assert is_ready is False
    
    def test_all_failed_with_pending(self):
        is_ready, reason = _check_trigger_rule('all_failed', ['failed', 'waiting'])
        assert is_ready is False
        assert 'waiting' in reason
    
    # ===== one_failed =====
    
    def test_one_failed_with_one(self):
        """Triggers immediately when one fails - doesn't wait!"""
        is_ready, reason = _check_trigger_rule('one_failed', ['failed', 'running'])
        assert is_ready is True
        assert reason == 'one_failed'
    
    def test_one_failed_none_yet(self):
        is_ready, reason = _check_trigger_rule('one_failed', ['success', 'running'])
        assert is_ready is False
        assert 'waiting' in reason
    
    def test_one_failed_all_success(self):
        is_ready, reason = _check_trigger_rule('one_failed', ['success', 'success'])
        assert is_ready is False
        assert 'none failed' in reason
    
    # ===== all_done =====
    
    def test_all_done_mixed_terminal(self):
        is_ready, reason = _check_trigger_rule('all_done', ['success', 'failed', 'skipped'])
        assert is_ready is True
        assert reason == 'all_done'
    
    def test_all_done_with_pending(self):
        is_ready, reason = _check_trigger_rule('all_done', ['success', 'waiting'])
        assert is_ready is False
        assert 'waiting' in reason
    
    # ===== one_done =====
    
    def test_one_done_with_one(self):
        """Triggers immediately when one completes - doesn't wait!"""
        is_ready, reason = _check_trigger_rule('one_done', ['success', 'waiting'])
        assert is_ready is True
        assert reason == 'one_done'
    
    def test_one_done_failed_counts(self):
        is_ready, reason = _check_trigger_rule('one_done', ['failed', 'waiting'])
        assert is_ready is True
        assert reason == 'one_done'
    
    def test_one_done_all_pending(self):
        is_ready, reason = _check_trigger_rule('one_done', ['waiting', 'running'])
        assert is_ready is False
        assert 'waiting' in reason
    
    # ===== all_skipped =====
    
    def test_all_skipped_with_all(self):
        is_ready, reason = _check_trigger_rule('all_skipped', ['skipped', 'skipped'])
        assert is_ready is True
        assert reason == 'all_skipped'
    
    def test_all_skipped_with_success(self):
        is_ready, reason = _check_trigger_rule('all_skipped', ['skipped', 'success'])
        assert is_ready is False
    
    # ===== none_failed =====
    
    def test_none_failed_success_and_skipped(self):
        is_ready, reason = _check_trigger_rule('none_failed', ['success', 'skipped'])
        assert is_ready is True
        assert reason == 'none_failed'
    
    def test_none_failed_with_failure(self):
        is_ready, reason = _check_trigger_rule('none_failed', ['success', 'failed'])
        assert is_ready is False
        assert 'failed' in reason
    
    def test_none_failed_with_pending(self):
        is_ready, reason = _check_trigger_rule('none_failed', ['success', 'waiting'])
        assert is_ready is False
        assert 'waiting' in reason
    
    # ===== none_skipped =====
    
    def test_none_skipped_all_success(self):
        is_ready, reason = _check_trigger_rule('none_skipped', ['success', 'success'])
        assert is_ready is True
        assert reason == 'none_skipped'
    
    def test_none_skipped_with_skip(self):
        is_ready, reason = _check_trigger_rule('none_skipped', ['success', 'skipped'])
        assert is_ready is False
        assert 'skipped' in reason
    
    # ===== none_failed_min_one_success =====
    
    def test_none_failed_min_one_success_ok(self):
        is_ready, reason = _check_trigger_rule('none_failed_min_one_success', ['success', 'skipped'])
        assert is_ready is True
        assert reason == 'none_failed_min_one_success'
    
    def test_none_failed_min_one_success_all_skipped(self):
        is_ready, reason = _check_trigger_rule('none_failed_min_one_success', ['skipped', 'skipped'])
        assert is_ready is False
        assert 'no success' in reason
    
    def test_none_failed_min_one_success_with_failure(self):
        is_ready, reason = _check_trigger_rule('none_failed_min_one_success', ['success', 'failed'])
        assert is_ready is False
        assert 'failed' in reason
    
    # ===== all_done_min_one_success =====
    
    def test_all_done_min_one_success_ok(self):
        is_ready, reason = _check_trigger_rule('all_done_min_one_success', ['success', 'failed'])
        assert is_ready is True
        assert reason == 'all_done_min_one_success'
    
    def test_all_done_min_one_success_no_success(self):
        is_ready, reason = _check_trigger_rule('all_done_min_one_success', ['failed', 'skipped'])
        assert is_ready is False
        assert 'no success' in reason
    
    def test_all_done_min_one_success_with_pending(self):
        is_ready, reason = _check_trigger_rule('all_done_min_one_success', ['success', 'waiting'])
        assert is_ready is False
        assert 'waiting' in reason
    
    # ===== Edge cases =====
    
    def test_empty_deps(self):
        is_ready, reason = _check_trigger_rule('all_success', [])
        assert is_ready is True
        assert reason == 'no_deps'
    
    def test_unknown_trigger_rule_defaults_to_all_success(self):
        """Unknown rules fall back to all_success."""
        is_ready, reason = _check_trigger_rule('invalid_rule', ['success', 'success'])
        assert is_ready is True
    
    def test_not_found_counts_as_pending(self):
        """not_found status means task hasn't registered yet."""
        is_ready, reason = _check_trigger_rule('all_success', ['success', 'not_found'])
        assert is_ready is False
        assert 'waiting' in reason


class TestCalculateCounts:
    """Test status counting logic."""
    
    def test_all_success(self):
        counts = _calculate_counts(['success', 'success', 'success'])
        assert counts == {'total': 3, 'success': 3, 'failed': 0, 'skipped': 0, 'pending': 0}
    
    def test_mixed_statuses(self):
        counts = _calculate_counts(['success', 'failed', 'skipped', 'waiting'])
        assert counts == {'total': 4, 'success': 1, 'failed': 1, 'skipped': 1, 'pending': 1}
    
    def test_failure_types(self):
        """failed, upstream_failed, aborted all count as failed."""
        counts = _calculate_counts(['failed', 'upstream_failed', 'aborted'])
        assert counts['failed'] == 3
        assert counts['pending'] == 0
    
    def test_pending_types(self):
        """waiting, running, deps_ready, not_found all count as pending."""
        counts = _calculate_counts(['waiting', 'running', 'deps_ready', 'not_found', 'waiting_delay'])
        assert counts['pending'] == 5
        assert counts['success'] == 0
    
    def test_empty(self):
        counts = _calculate_counts([])
        assert counts == {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'pending': 0}



class TestHandler:
    """Test main handler function.

    v0.79.3 (ADR #75) — tests mock `tokens_repo.batch_get_statuses` /
    `.is_paused` directly instead of patching boto3 internals. The DAL
    pattern makes test setup ~10x shorter.
    """

    def test_empty_dependencies(self, mocker):
        """Empty deps = immediately ready."""
        # No DDB access expected; DAL methods don't need patching.
        result = handler({'dependencies': [], 'trigger_rule': 'all_success'}, None)
        assert result['is_ready'] is True
        assert result['is_blocked'] is False
        assert result['reason'] == 'no_deps'
        assert result['dep_statuses'] == []

    def test_all_ready(self, mocker):
        """All deps success = ready."""
        mocker.patch('evaluate_deps.index.tokens_repo.batch_get_statuses',
                     return_value={
                         'task_a-2026-01-19-abc123': 'success',
                         'task_b-2026-01-19-abc123': 'success',
                     })
        result = handler({
            'dependencies': ['task_a', 'task_b'],
            'trigger_rule': 'all_success',
            'date': '2026-01-19',
            'pipeline_execution_short': 'abc123',
            'pipeline_execution': '',
        }, None)
        assert result['is_ready'] is True
        assert result['is_blocked'] is False
        assert result['dep_statuses'] == ['success', 'success']
        assert result['counts']['success'] == 2

    def test_blocked_scenario(self, mocker):
        """All done but rule not satisfied = blocked."""
        mocker.patch('evaluate_deps.index.tokens_repo.batch_get_statuses',
                     return_value={
                         'task_a-2026-01-19-abc123': 'success',
                         'task_b-2026-01-19-abc123': 'failed',
                     })
        result = handler({
            'dependencies': ['task_a', 'task_b'],
            'trigger_rule': 'all_success',
            'date': '2026-01-19',
            'pipeline_execution_short': 'abc123',
            'pipeline_execution': '',
        }, None)
        assert result['is_ready'] is False
        assert result['is_blocked'] is True
        assert result['counts']['failed'] == 1

    def test_pending_scenario(self, mocker):
        """Some still running = pending (waiting)."""
        mocker.patch('evaluate_deps.index.tokens_repo.batch_get_statuses',
                     return_value={
                         'task_a-2026-01-19-abc123': 'success',
                         'task_b-2026-01-19-abc123': 'running',
                     })
        result = handler({
            'dependencies': ['task_a', 'task_b'],
            'trigger_rule': 'all_success',
            'date': '2026-01-19',
            'pipeline_execution_short': 'abc123',
            'pipeline_execution': '',
        }, None)
        assert result['is_ready'] is False
        assert result['is_blocked'] is False
        assert result['counts']['pending'] == 1

    def test_paused_pipeline(self, mocker):
        """Paused pipeline = not ready even if deps are ready, but deps_satisfied=True."""
        mocker.patch('evaluate_deps.index.tokens_repo.batch_get_statuses',
                     return_value={'task_a-2026-01-19-abc123': 'success'})
        mocker.patch('evaluate_deps.index.tokens_repo.is_paused',
                     return_value=True)
        result = handler({
            'dependencies': ['task_a'],
            'trigger_rule': 'all_success',
            'date': '2026-01-19',
            'pipeline_execution_short': 'abc123',
            'pipeline_execution': 'pipeline-2026-01-19-abc123',
        }, None)
        assert result['is_ready'] is False
        assert result['is_paused'] is True
        assert result['deps_satisfied'] is True

    def test_paused_pipeline_deps_not_ready(self, mocker):
        """Paused + deps not ready = is_ready=False, deps_satisfied=False."""
        mocker.patch('evaluate_deps.index.tokens_repo.batch_get_statuses',
                     return_value={'task_a-2026-01-19-abc123': 'waiting'})
        mocker.patch('evaluate_deps.index.tokens_repo.is_paused',
                     return_value=True)
        result = handler({
            'dependencies': ['task_a'],
            'trigger_rule': 'all_success',
            'date': '2026-01-19',
            'pipeline_execution_short': 'abc123',
            'pipeline_execution': 'pipeline-2026-01-19-abc123',
        }, None)
        assert result['is_ready'] is False
        assert result['is_paused'] is True
        assert result['deps_satisfied'] is False


class TestStatusCategories:
    """Verify status category definitions.

    v0.79.5 (ADR #77) — sets are now imported from canonical
    slsflow/constants.py via generated module-level constants. The
    canonical TaskStatus enum includes both 'success' (legacy/Airflow 2
    form) and 'succeeded' (Airflow 3 form), so the terminal/success
    sets contain both.
    """

    def test_terminal_success(self):
        # Both legacy 'success' and Airflow-3 'succeeded' are success-like
        assert TERMINAL_SUCCESS == {'success', 'succeeded', 'skipped'}

    def test_terminal_failure(self):
        assert TERMINAL_FAILURE == {'failed', 'upstream_failed', 'aborted'}

    def test_terminal_statuses(self):
        assert TERMINAL_STATUSES == {
            'success', 'succeeded', 'skipped',
            'failed', 'upstream_failed', 'aborted',
        }


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_trigger_rule_one_success_doesnt_wait(self):
        """Critical: one_success triggers immediately, doesn't wait for all deps."""
        # One success, others still running - should be ready!
        is_ready, _ = _check_trigger_rule('one_success', ['success', 'running', 'waiting'])
        assert is_ready is True
    
    def test_trigger_rule_one_failed_doesnt_wait(self):
        """Critical: one_failed triggers immediately, doesn't wait for all deps."""
        is_ready, _ = _check_trigger_rule('one_failed', ['failed', 'running', 'waiting'])
        assert is_ready is True
    
    def test_trigger_rule_one_done_doesnt_wait(self):
        """Critical: one_done triggers immediately, doesn't wait for all deps."""
        is_ready, _ = _check_trigger_rule('one_done', ['skipped', 'running', 'waiting'])
        assert is_ready is True
    
    def test_skipped_treated_as_ok_for_all_success(self):
        """Manual skip via UI should allow pipeline to continue."""
        is_ready, _ = _check_trigger_rule('all_success', ['success', 'skipped', 'skipped'])
        assert is_ready is True
    
    def test_waiting_decision_counts_as_pending(self):
        """waiting_decision status = task waiting for human decision."""
        counts = _calculate_counts(['waiting_decision'])
        assert counts['pending'] == 1
    
    def test_waiting_paused_counts_as_pending(self):
        counts = _calculate_counts(['waiting_paused'])
        assert counts['pending'] == 1
