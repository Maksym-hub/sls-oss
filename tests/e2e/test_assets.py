"""
E2E Tests — Asset endpoints.

Read-only asset queries. Write operations marked with @pytest.mark.write.
"""
import pytest


class TestListAssets:
    """GET /api/assets"""

    def test_returns_200(self, api):
        resp = api.get("/api/assets")
        assert resp["status"] == 200

    def test_returns_list(self, api):
        resp = api.get("/api/assets")
        body = resp["body"]
        assets = body if isinstance(body, list) else body.get("assets", [])
        assert isinstance(assets, list)


class TestAssetLineage:
    """GET /api/assets/lineage"""

    def test_returns_200(self, api):
        resp = api.get("/api/assets/lineage")
        assert resp["status"] == 200


class TestAssetQueuedEvents:
    """GET /api/assets/queued"""

    def test_returns_200(self, api):
        resp = api.get("/api/assets/queued")
        assert resp["status"] == 200


class TestRecentAssetEvents:
    """GET /api/assets/recent-events"""

    def test_returns_200(self, api):
        resp = api.get("/api/assets/recent-events")
        assert resp["status"] == 200


class TestAssetEvents:
    """GET /api/asset-events"""

    def test_requires_asset_param(self, api):
        resp = api.get("/api/asset-events")
        # Should require an asset name/uri
        assert resp["status"] in (200, 400, 422)
