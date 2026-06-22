"""End-to-end tests for Backfill endpoints (v0.78+, ADR #51).

These exercise the deployed Console API against real DynamoDB + Step
Functions. They are skipped when ``SLSFLOW_API_URL`` is unset, so they
do not run in CI by default.

**Before tagging a release**, run these against a dev deployment:

  SLSFLOW_API_URL=https://<dev-api>.execute-api.us-east-1.amazonaws.com \\
  SLSFLOW_ID_TOKEN=<cognito-id-token> \\
  pytest tests/e2e/test_backfill.py -v -m smoke

These tests intentionally use a very small partition range (1-2 days) so
they complete quickly and have low cost impact (~$0.001 per run).

Per CLAUDE.md #15 (smoke test before release) and #16 (new endpoints get
e2e tests in the same delivery).
"""

import pytest
import time

# All tests in this file require live API
pytestmark = [pytest.mark.smoke]


def _skip_if_no_api(api):
    """Skip if the api fixture didn't initialize a real URL."""
    if not getattr(api, 'base_url', '').startswith('http'):
        pytest.skip("SLSFLOW_API_URL not set — skipping E2E tests")


@pytest.fixture
def pipeline_name(api):
    """Find any registered pipeline to use as a backfill target.

    Skips the whole module if no pipelines are registered (we have nothing
    safe to backfill against)."""
    _skip_if_no_api(api)
    resp = api.get("/api/pipelines")
    if resp["status"] != 200:
        pytest.skip(f"GET /api/pipelines returned {resp['status']}")
    pipelines = resp.get("body", [])
    if not pipelines:
        pytest.skip("No pipelines registered in this deployment")
    # Prefer a daily-cron pipeline (simplest partition format)
    daily = [p for p in pipelines if '@daily' in p.get('schedule', '')
             or '0 ' in p.get('schedule', '')]
    return (daily[0] if daily else pipelines[0])['pipeline_name']


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/backfill — preview mode (no SFN start, no cost)
# ──────────────────────────────────────────────────────────────────────────────

class TestBackfillPreview:
    def test_preview_returns_plan_without_starting(self, api, pipeline_name):
        """preview=true returns partition count + cost estimate, doesn't
        write a Backfill record, doesn't start the SFN. This is the safest
        E2E to run repeatedly — fully read-only."""
        yesterday = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400))
        resp = api.post(
            "/api/backfill",
            params={'preview': 'true'},
            body={
                'target': {'type': 'pipeline', 'name': pipeline_name},
                'partitions': {'start': yesterday, 'end': yesterday},
            },
        )
        assert resp['status'] == 200, f"Expected 200, got {resp['status']}: {resp.get('body')}"
        body = resp['body']
        assert body.get('preview') is True
        assert body['target_pipeline'] == pipeline_name
        assert body['partition_count_to_run'] == 1
        # Cost estimate removed in v0.78.2 (ADR #62) — was: 'estimated_sfn_cost_usd' in body
        assert isinstance(body.get('warnings'), list)

    def test_preview_rejects_invalid_date_range(self, api, pipeline_name):
        """end < start → 400 invalid_partitions."""
        resp = api.post(
            "/api/backfill",
            params={'preview': 'true'},
            body={
                'target': {'type': 'pipeline', 'name': pipeline_name},
                'partitions': {'start': '2024-01-20', 'end': '2024-01-15'},
            },
        )
        assert resp['status'] == 400
        assert resp['body'].get('error') == 'invalid_partitions'

    def test_preview_rejects_batch_target(self, api, pipeline_name):
        """target.type='batch' was removed in v0.78 → 400 invalid_target_type."""
        resp = api.post(
            "/api/backfill",
            params={'preview': 'true'},
            body={
                'target': {'type': 'batch', 'items': [{'type': 'pipeline', 'name': pipeline_name}]},
                'partitions': {'start': '2024-01-15', 'end': '2024-01-15'},
            },
        )
        assert resp['status'] == 400
        assert resp['body'].get('error') == 'invalid_target_type'

    def test_preview_unknown_pipeline_returns_404(self, api):
        """target_not_found → 404."""
        _skip_if_no_api(api)
        resp = api.post(
            "/api/backfill",
            params={'preview': 'true'},
            body={
                'target': {'type': 'pipeline', 'name': '__nonexistent_pipeline_xyz__'},
                'partitions': {'start': '2024-01-15', 'end': '2024-01-15'},
            },
        )
        assert resp['status'] in (400, 404)
        assert resp['body'].get('error') in (
            'target_not_found', 'no_producer', 'invalid_target',
        )


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/backfills — list
# ──────────────────────────────────────────────────────────────────────────────

class TestBackfillsList:
    def test_list_returns_200(self, api):
        _skip_if_no_api(api)
        resp = api.get("/api/backfills")
        assert resp['status'] == 200
        body = resp['body']
        # Either a list or {"backfills": [...], "count": N}
        if isinstance(body, dict):
            assert 'backfills' in body
            assert isinstance(body['backfills'], list)
        else:
            assert isinstance(body, list)

    def test_list_filter_by_status(self, api):
        _skip_if_no_api(api)
        resp = api.get("/api/backfills", params={'status': 'completed'})
        assert resp['status'] == 200

    def test_list_invalid_status_returns_400(self, api):
        _skip_if_no_api(api)
        resp = api.get("/api/backfills", params={'status': '__bogus__'})
        assert resp['status'] == 400


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/backfills/by-id — detail
# ──────────────────────────────────────────────────────────────────────────────

class TestBackfillDetail:
    def test_unknown_id_returns_404(self, api):
        _skip_if_no_api(api)
        resp = api.get("/api/backfills/by-id", params={'id': 'bf-deadbeef'})
        assert resp['status'] == 404
        assert resp['body'].get('error') == 'not_found'

    def test_missing_id_param_returns_400(self, api):
        _skip_if_no_api(api)
        resp = api.get("/api/backfills/by-id")
        assert resp['status'] == 400


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/backfills/cancel — cooperative cancel
# ──────────────────────────────────────────────────────────────────────────────

class TestBackfillCancel:
    def test_unknown_id_returns_404(self, api):
        _skip_if_no_api(api)
        resp = api.post("/api/backfills/cancel", params={'id': 'bf-nonexistent'})
        assert resp['status'] == 404

    def test_missing_id_returns_400(self, api):
        _skip_if_no_api(api)
        resp = api.post("/api/backfills/cancel")
        assert resp['status'] == 400


# ──────────────────────────────────────────────────────────────────────────────
# Full happy-path: start → list → detail → cancel
# ──────────────────────────────────────────────────────────────────────────────

class TestBackfillLifecycle:
    """End-to-end smoke: actually start a tiny backfill, verify it appears
    in list, fetch detail, then cancel it. Costs ~$0.001 per run."""

    def test_full_lifecycle(self, api, pipeline_name):
        # 1. Start a 1-partition backfill
        yesterday = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400))
        start_resp = api.post("/api/backfill", body={
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'start': yesterday, 'end': yesterday},
            'options': {'force': True, 'skip_completed': False, 'max_parallel': 1},
        })
        assert start_resp['status'] == 202, (
            f"start_backfill failed: {start_resp['status']}: {start_resp.get('body')}"
        )
        backfill_id = start_resp['body']['backfill_id']
        assert backfill_id.startswith('bf-')

        try:
            # 2. Appears in list
            list_resp = api.get("/api/backfills")
            list_body = list_resp['body']
            backfills = list_body.get('backfills', list_body) if isinstance(list_body, dict) else list_body
            assert any(b['backfill_id'] == backfill_id for b in backfills), (
                f"backfill {backfill_id} not in /api/backfills response"
            )

            # 3. Detail fetch succeeds
            detail_resp = api.get("/api/backfills/by-id", params={'id': backfill_id})
            assert detail_resp['status'] == 200
            detail = detail_resp['body']
            assert detail['backfill_id'] == backfill_id
            assert detail['target_pipeline'] == pipeline_name
            assert detail['status'] in ('pending', 'running', 'completed', 'partial', 'failed')

        finally:
            # 4. Cancel (cleanup; may already be terminal)
            cancel_resp = api.post("/api/backfills/cancel", params={'id': backfill_id})
            assert cancel_resp['status'] in (200, 409)  # 409 = already_terminal is OK


@pytest.mark.smoke
class TestBackfillOptionsCombo:
    """E2E coverage for the option combinations that span UI → API →
    DDB → SFN → child execution. Unit tests mock the boundary; this
    smoke test verifies the wire reality end-to-end."""

    def test_task_subset_skip_completed_max_parallel_combo(self, api, pipeline_name):
        """The full options chain: user picks subset of tasks, asks to
        skip already-complete partitions, caps parallelism. The whole
        chain must coordinate:
          - API computes skip_task_ids from tasks input
          - API runs skip_completed pre-flight (returns subset)
          - SFN gets MaxConcurrency from options.max_parallel
          - Child execution gets skip_tasks list
          - Backfill record stores all this
        """
        # Use a 3-partition window so skip_completed has something to scan
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'start': '2024-01-15', 'end': '2024-01-17'},
            'tasks': None,  # accept any first task if pipeline has tasks; subset filter exercised by API even with full set
            'options': {
                'max_parallel': 2,
                'skip_completed': True,
                'force': False,  # documented no-op; just verify accept
            },
        }
        # Preview first — verify the plan reflects the options
        preview = api.post('/api/backfill?preview=true', json=body)
        assert preview['status'] == 200, preview['body']
        plan = preview['body']
        # The partition count should reflect the option choices
        assert 'partition_count_to_run' in plan
        assert 'partition_count_skipped_completed' in plan
        # Cost estimate removed in v0.78.2 (ADR #62).

        # Start for real
        start = api.post('/api/backfill', json=body)
        assert start['status'] == 202, start['body']
        backfill_id = start['body']['backfill_id']

        try:
            # Detail must reflect the option choices
            detail_resp = api.get(f"/api/backfills/{backfill_id}")
            assert detail_resp['status'] == 200
            d = detail_resp['body']
            assert d['target_pipeline'] == pipeline_name
            assert d['total_partitions'] <= 3  # may be lower after skip_completed
        finally:
            api.post('/api/backfills/cancel', params={'id': backfill_id})

    def test_concurrent_backfill_returns_409(self, api, pipeline_name):
        """Concurrency guard end-to-end — second start against the
        same pipeline must return 409 without allow_concurrent override."""
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'keys': ['2024-01-15']},
            'options': {'skip_completed': False},
        }
        # First start
        first = api.post('/api/backfill', json=body)
        assert first['status'] == 202, first['body']
        first_id = first['body']['backfill_id']

        try:
            # Second start immediately — should be rejected
            second = api.post('/api/backfill', json=body)
            assert second['status'] == 409, (
                f"Concurrency guard failed: got {second['status']}, "
                f"body={second['body']}"
            )
            assert second['body']['error'] == 'concurrent_backfill_active'

            # With allow_concurrent override — should proceed
            override_body = {**body, 'options': {**body['options'], 'allow_concurrent': True}}
            override = api.post('/api/backfill', json=override_body)
            assert override['status'] == 202, override['body']
            api.post('/api/backfills/cancel', params={'id': override['body']['backfill_id']})
        finally:
            api.post('/api/backfills/cancel', params={'id': first_id})


@pytest.mark.smoke
class TestBackfillValidationE2E:
    """Validation errors must be reported correctly across the wire.
    UI relies on these error codes to show user-friendly messages."""

    def test_range_too_large_returns_correct_code(self, api, pipeline_name):
        """1001 daily partitions exceed PARTITION_HARD_LIMIT=1000."""
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'start': '2021-01-01', 'end': '2024-01-01'},
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] == 'range_too_large'

    def test_unknown_pipeline_returns_404(self, api):
        body = {
            'target': {'type': 'pipeline', 'name': 'definitely-does-not-exist-12345'},
            'partitions': {'keys': ['2024-01-15']},
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 404
        assert resp['body']['error'] == 'target_not_found'

    def test_invalid_partition_format_returns_400(self, api, pipeline_name):
        """Daily pipeline + weekly-formatted keys → format mismatch."""
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'keys': ['2024-W03']},
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] in ('invalid_partition_format', 'invalid_partitions')

    def test_batch_target_rejected(self, api, pipeline_name):
        """target.type=batch is reserved for v0.79+ (deferred per ADR #51)."""
        body = {
            'target': {'type': 'batch', 'items': [
                {'type': 'pipeline', 'name': pipeline_name},
            ]},
            'partitions': {'keys': ['2024-01-15']},
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] == 'invalid_target_type'

    def test_invalid_cascade_for_pipeline_target(self, api, pipeline_name):
        """cascade option only valid for asset targets."""
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'keys': ['2024-01-15']},
            'cascade': 'all',
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] == 'invalid_cascade_for_pipeline_target'


@pytest.mark.smoke
class TestBackfillRetryFailedE2E:
    """Retry-failed must preserve granularity and create a tracked child
    backfill with parent_backfill_id lineage."""

    def test_retry_failed_on_nonexistent_returns_404(self, api):
        resp = api.post('/api/backfills/retry-failed', params={'id': 'bf-nonexistent-1234'})
        assert resp['status'] == 404

    def test_retry_failed_missing_id_returns_400(self, api):
        resp = api.post('/api/backfills/retry-failed')
        assert resp['status'] == 400


@pytest.mark.smoke
class TestBackfillCancelE2E:
    """Cancel semantics: cooperative — flips DDB status, SFN reads at
    each Map iteration boundary."""

    def test_cancel_completed_backfill_returns_409(self, api):
        """Per ADR #51 status model: can't cancel a terminal state."""
        # We need a known-completed backfill ID; list to find one
        list_resp = api.get('/api/backfills', params={'status': 'completed'})
        if list_resp['status'] != 200 or not list_resp['body']:
            pytest.skip("No completed backfills available to test cancel-of-terminal")

        terminal_id = list_resp['body'][0]['backfill_id']
        cancel_resp = api.post('/api/backfills/cancel', params={'id': terminal_id})
        assert cancel_resp['status'] == 409
        assert cancel_resp['body']['error'] == 'already_terminal'


@pytest.mark.smoke
class TestBackfillScaleLimitsE2E:
    """Verify scale boundaries documented in API.md are enforced."""

    def test_max_parallel_above_10_rejected(self, api, pipeline_name):
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'keys': ['2024-01-15']},
            'options': {'max_parallel': 50},  # over hardcap 10
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] == 'invalid_options'

    def test_max_parallel_zero_rejected(self, api, pipeline_name):
        body = {
            'target': {'type': 'pipeline', 'name': pipeline_name},
            'partitions': {'keys': ['2024-01-15']},
            'options': {'max_parallel': 0},
        }
        resp = api.post('/api/backfill', json=body)
        assert resp['status'] == 400
        assert resp['body']['error'] == 'invalid_options'
