"""
E2E Tests — Tasks, Executions, Notifications endpoints.

Read-only queries. Tests that mutate state are marked @pytest.mark.write.
"""


# =============================================================================
# Tasks
# =============================================================================

class TestListTasks:
    """GET /api/tasks"""

    def test_returns_200(self, api):
        resp = api.get("/api/tasks")
        assert resp["status"] == 200

    def test_returns_list(self, api):
        resp = api.get("/api/tasks")
        body = resp["body"]
        tasks = body if isinstance(body, list) else body.get("tasks", [])
        assert isinstance(tasks, list)


class TestTaskConfig:
    """GET /api/task-config"""

    def test_requires_params(self, api):
        resp = api.get("/api/task-config")
        assert resp["status"] in (400, 422)


class TestTaskEvents:
    """GET /api/task-events"""

    def test_requires_params(self, api):
        resp = api.get("/api/task-events")
        assert resp["status"] in (400, 422)


# =============================================================================
# Executions
# =============================================================================

class TestListRuns:
    """GET /api/runs"""

    def test_returns_200(self, api):
        resp = api.get("/api/runs")
        assert resp["status"] == 200

    def test_returns_list(self, api):
        resp = api.get("/api/runs")
        body = resp["body"]
        runs = body if isinstance(body, list) else body.get("runs", body.get("executions", []))
        assert isinstance(runs, list)


class TestExecutionChildren:
    """GET /api/execution-children"""

    def test_requires_params(self, api):
        resp = api.get("/api/execution-children")
        assert resp["status"] in (400, 422)


class TestExecutionParent:
    """GET /api/execution-parent"""

    def test_requires_params(self, api):
        resp = api.get("/api/execution-parent")
        assert resp["status"] in (400, 422)


# =============================================================================
# Notifications
# =============================================================================

class TestNotifications:
    """GET /api/notifications"""

    def test_returns_200(self, api):
        resp = api.get("/api/notifications")
        assert resp["status"] == 200

    def test_returns_list(self, api):
        resp = api.get("/api/notifications")
        body = resp["body"]
        notifs = body if isinstance(body, list) else body.get("notifications", [])
        assert isinstance(notifs, list)


# =============================================================================
# Error handling — unknown routes
# =============================================================================

class TestUnknownRoutes:
    """Verify API returns proper errors for unknown paths."""

    def test_unknown_get_returns_error(self, api):
        resp = api.get("/api/this-does-not-exist")
        # API Gateway returns 404 or 403 for unknown routes
        assert resp["status"] in (403, 404)

    def test_unknown_post_returns_error(self, api):
        resp = api.post("/api/this-does-not-exist")
        assert resp["status"] in (403, 404)
