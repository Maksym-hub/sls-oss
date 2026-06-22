"""
Tests for normalize_execution_status (v0.78.14, ADR #71).

This helper centralizes the mapping from SFN's UPPERCASE statuses
('RUNNING'/'SUCCEEDED'/...) to internal canonical lowercase form.
Apply at every boundary where SFN status enters the system AND
before writing to DDB.
"""
import pytest
from constants import (
    normalize_execution_status,
    EXECUTION_STATUS_CANONICAL,
)


class TestNormalizeExecutionStatus:
    @pytest.mark.parametrize("uppercase,canonical", [
        ('RUNNING', 'running'),
        ('SUCCEEDED', 'succeeded'),
        ('FAILED', 'failed'),
        ('TIMED_OUT', 'timed_out'),
        ('ABORTED', 'aborted'),
        ('STOPPED', 'stopped'),
    ])
    def test_maps_uppercase_to_canonical(self, uppercase, canonical):
        assert normalize_execution_status(uppercase) == canonical

    @pytest.mark.parametrize("canonical", list(EXECUTION_STATUS_CANONICAL))
    def test_canonical_is_idempotent(self, canonical):
        assert normalize_execution_status(canonical) == canonical

    def test_legacy_success_maps_to_succeeded(self):
        # Some legacy code wrote 'success' (TaskStatus form) instead of
        # 'succeeded' (ExecutionStatus form). Normalize to canonical.
        assert normalize_execution_status('success') == 'succeeded'
        assert normalize_execution_status('SUCCESS') == 'succeeded'

    def test_none_returns_none(self):
        assert normalize_execution_status(None) is None

    def test_unknown_returns_as_is_without_log_warn(self):
        # Default: no log_warn given → no error, return original
        result = normalize_execution_status('weird_status')
        assert result == 'weird_status'

    def test_unknown_logs_when_log_warn_provided(self):
        calls = []

        def fake_warn(msg, **ctx):
            calls.append((msg, ctx))

        result = normalize_execution_status('weird_status', log_warn=fake_warn)
        assert result == 'weird_status'
        assert len(calls) == 1
        assert 'status' in calls[0][1]
        assert calls[0][1]['status'] == 'weird_status'

    def test_canonical_does_not_log_warn(self):
        # Idempotent path should not trigger any warning
        calls = []

        def fake_warn(msg, **ctx):
            calls.append((msg, ctx))

        normalize_execution_status('running', log_warn=fake_warn)
        normalize_execution_status('SUCCEEDED', log_warn=fake_warn)  # mappable
        assert calls == []

    def test_canonical_set_matches_expected(self):
        # Lock the canonical set so accidental additions/removals are caught
        # by tests, not by runtime drift.
        assert EXECUTION_STATUS_CANONICAL == {
            'running', 'succeeded', 'failed', 'timed_out', 'aborted', 'stopped',
        }
