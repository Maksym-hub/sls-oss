"""Unit tests for slsflow CLI (v0.78+, ADR #51).

Pattern: mock urllib.request.urlopen + os.environ to avoid real network.
Each test exercises one command path (parser → handler → API call).
"""

import io
import json
import sys
from unittest import mock

import pytest
from types import SimpleNamespace

from slsflow.cli import (
    _api_call,
    _parse_variables,
    cmd_backfill_pipeline,
    cmd_backfill_asset,
    cmd_backfills_list,
    cmd_backfills_show,
    cmd_backfills_cancel,
    cmd_backfills_retry_failed,
    main,
)


# ──────────────────────────────────────────────────────────────────────────────
# _parse_variables
# ──────────────────────────────────────────────────────────────────────────────

class TestParseVariables:
    def test_none(self):
        assert _parse_variables(None) == {}

    def test_empty(self):
        assert _parse_variables("") == {}

    def test_json_object(self):
        assert _parse_variables('{"k": "v", "n": 1}') == {"k": "v", "n": 1}

    def test_json_invalid_falls_back(self):
        assert _parse_variables("{not-json") == {}

    def test_json_array_rejected(self):
        # Arrays don't make sense as variables
        assert _parse_variables('["a", "b"]') == {}

    def test_kv_pairs(self):
        assert _parse_variables("a=1,b=2") == {"a": "1", "b": "2"}

    def test_kv_pair_with_spaces(self):
        assert _parse_variables(" key = value , other = 2 ") == {
            "key": "value", "other": "2",
        }

    def test_kv_no_equals_ignored(self):
        assert _parse_variables("nopair,k=v") == {"k": "v"}


# ──────────────────────────────────────────────────────────────────────────────
# _api_call — error paths
# ──────────────────────────────────────────────────────────────────────────────

class TestApiCall:
    def test_missing_url_exits_2(self, monkeypatch, capsys):
        monkeypatch.delenv("SLSFLOW_API_URL", raising=False)
        with pytest.raises(SystemExit) as exc:
            _api_call("GET", "/backfills")
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "SLSFLOW_API_URL not set" in err

    def test_success_returns_status_and_payload(self, monkeypatch):
        monkeypatch.setenv("SLSFLOW_API_URL", "https://api.example.com")
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = b'{"backfill_id": "bf-xyz"}'
        mock_resp.status = 200
        mock_resp.__enter__ = lambda self: mock_resp
        mock_resp.__exit__ = lambda *a: False
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            status, payload = _api_call("GET", "/backfills/by-id", query={"id": "bf-xyz"})
        assert status == 200
        assert payload == {"backfill_id": "bf-xyz"}

    def test_empty_response_body(self, monkeypatch):
        monkeypatch.setenv("SLSFLOW_API_URL", "https://api.example.com")
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = b""
        mock_resp.status = 204
        mock_resp.__enter__ = lambda self: mock_resp
        mock_resp.__exit__ = lambda *a: False
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            status, payload = _api_call("POST", "/some/action")
        assert status == 204
        assert payload == {}

    def test_http_error_returns_status_and_json_body(self, monkeypatch):
        monkeypatch.setenv("SLSFLOW_API_URL", "https://api.example.com")
        import urllib.error

        def raise_404(*args, **kwargs):
            error = urllib.error.HTTPError(
                url="x", code=404, msg="not found", hdrs=None,
                fp=io.BytesIO(b'{"error": "not_found", "message": "missing"}'),
            )
            raise error

        with mock.patch("urllib.request.urlopen", side_effect=raise_404):
            status, payload = _api_call("GET", "/backfills/by-id?id=x")
        assert status == 404
        assert payload["error"] == "not_found"

    def test_bearer_token_included(self, monkeypatch):
        monkeypatch.setenv("SLSFLOW_API_URL", "https://api.example.com")
        monkeypatch.setenv("SLSFLOW_API_TOKEN", "secret-bearer")
        captured = {}

        def fake_urlopen(req, *args, **kwargs):
            captured["headers"] = dict(req.headers)
            resp = mock.MagicMock()
            resp.read.return_value = b"{}"
            resp.status = 200
            resp.__enter__ = lambda self: resp
            resp.__exit__ = lambda *a: False
            return resp

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            _api_call("GET", "/backfills")
        # urllib normalizes header names
        auth = captured["headers"].get("Authorization", "")
        assert auth == "Bearer secret-bearer"

    def test_url_error_exits_3(self, monkeypatch, capsys):
        monkeypatch.setenv("SLSFLOW_API_URL", "https://api.example.com")
        import urllib.error
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network down"),
        ), pytest.raises(SystemExit) as exc:
            _api_call("GET", "/backfills")
        assert exc.value.code == 3


# ──────────────────────────────────────────────────────────────────────────────
# Command dispatch — verify body shape
# ──────────────────────────────────────────────────────────────────────────────

def _stub_api(monkeypatch, response=(202, {"backfill_id": "bf-xyz", "partition_count_to_run": 3, "warnings": []})):
    """Patch _api_call to capture the request and return a fixed response."""
    captured = {}

    def fake_call(method, path, body=None, query=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        captured["query"] = query
        return response

    monkeypatch.setattr("slsflow.cli._api_call", fake_call)
    return captured


class TestCmdBackfillPipeline:
    def test_basic_call(self, monkeypatch, capsys):
        captured = _stub_api(monkeypatch)
        args = SimpleNamespace(
            name="daily-etl",
            start="2024-01-15",
            end="2024-01-17",
            max_parallel=5,
            force=False,
            skip_completed=True,
            incremental=False,
            variables=None,
            tasks=None,
            preview=False,
        )
        rc = cmd_backfill_pipeline(args)
        assert rc == 0
        assert captured["method"] == "POST"
        assert captured["path"] == "/backfill"
        body = captured["body"]
        assert body["target"] == {"type": "pipeline", "name": "daily-etl"}
        assert body["partitions"] == {"start": "2024-01-15", "end": "2024-01-17"}
        assert body["options"]["max_parallel"] == 5
        assert body["options"]["skip_completed"] is True

    def test_with_tasks(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        args = SimpleNamespace(
            name="daily-etl",
            start="2024-01-15", end="2024-01-15",
            max_parallel=3, force=True, skip_completed=False,
            incremental=False, variables=None,
            tasks="extract,transform",
            preview=False,
        )
        cmd_backfill_pipeline(args)
        assert captured["body"]["tasks"] == ["extract", "transform"]
        assert captured["body"]["options"]["force"] is True
        assert captured["body"]["options"]["skip_completed"] is False

    def test_preview_adds_query(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        args = SimpleNamespace(
            name="p", start="2024-01-15", end="2024-01-15",
            max_parallel=5, force=False, skip_completed=True,
            incremental=False, variables=None, tasks=None,
            preview=True,
        )
        cmd_backfill_pipeline(args)
        assert captured["query"] == {"preview": "true"}

    def test_variables_json_parsed(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        args = SimpleNamespace(
            name="p", start="2024-01-15", end="2024-01-15",
            max_parallel=5, force=False, skip_completed=True,
            incremental=False,
            variables='{"region": "us-east", "limit": 100}',
            tasks=None, preview=False,
        )
        cmd_backfill_pipeline(args)
        assert captured["body"]["options"]["variables"] == {
            "region": "us-east", "limit": 100,
        }

    def test_error_response_returns_1(self, monkeypatch, capsys):
        _stub_api(monkeypatch, response=(400, {"error": "invalid_target", "message": "bad"}))
        args = SimpleNamespace(
            name="x", start="2024-01-15", end="2024-01-15",
            max_parallel=5, force=False, skip_completed=True,
            incremental=False, variables=None, tasks=None, preview=False,
        )
        rc = cmd_backfill_pipeline(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "invalid_target" in err


class TestCmdBackfillAsset:
    def test_includes_cascade(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        args = SimpleNamespace(
            name="catalog/db/table",
            start="2024-01-15", end="2024-01-15",
            max_parallel=5, force=False, skip_completed=True,
            incremental=False, variables=None,
            cascade="all", preview=False,
        )
        cmd_backfill_asset(args)
        assert captured["body"]["target"] == {"type": "asset", "name": "catalog/db/table"}
        assert captured["body"]["cascade"] == "all"

    def test_multi_producer_shows_candidates(self, monkeypatch, capsys):
        _stub_api(monkeypatch, response=(400, {
            "error": "multi_producer_asset",
            "message": "multiple producers",
            "producers": [
                {"pipeline_name": "p1", "task_id": "t1"},
                {"pipeline_name": "p2", "task_id": "t2"},
            ],
        }))
        args = SimpleNamespace(
            name="shared/asset",
            start="2024-01-15", end="2024-01-15",
            max_parallel=5, force=False, skip_completed=True,
            incremental=False, variables=None,
            cascade="auto", preview=False,
        )
        rc = cmd_backfill_asset(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "Candidate producers" in err
        assert "p1: task t1" in err


class TestCmdBackfillsList:
    def test_no_filter(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfills": [], "count": 0}))
        args = SimpleNamespace(status=None, limit=None)
        cmd_backfills_list(args)
        assert captured["method"] == "GET"
        assert captured["path"] == "/backfills"
        assert captured["query"] is None

    def test_status_filter(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfills": []}))
        args = SimpleNamespace(status="active", limit=None)
        cmd_backfills_list(args)
        assert captured["query"] == {"status": "active"}

    def test_with_limit(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfills": []}))
        args = SimpleNamespace(status="failed", limit=25)
        cmd_backfills_list(args)
        assert captured["query"] == {"status": "failed", "limit": "25"}


class TestCmdBackfillsShow:
    def test_basic(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfill_id": "bf-x"}))
        args = SimpleNamespace(id="bf-x")
        cmd_backfills_show(args)
        assert captured["method"] == "GET"
        assert captured["path"] == "/backfills/by-id"
        assert captured["query"] == {"id": "bf-x"}

    def test_404_returns_1(self, monkeypatch):
        _stub_api(monkeypatch, response=(404, {"error": "not_found"}))
        args = SimpleNamespace(id="bf-nope")
        rc = cmd_backfills_show(args)
        assert rc == 1


class TestCmdBackfillsCancel:
    def test_basic(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"status": "canceled"}))
        args = SimpleNamespace(id="bf-x")
        rc = cmd_backfills_cancel(args)
        assert rc == 0
        assert captured["method"] == "POST"
        assert captured["path"] == "/backfills/cancel"
        assert captured["query"] == {"id": "bf-x"}

    def test_already_terminal_returns_1(self, monkeypatch):
        _stub_api(monkeypatch, response=(409, {
            "error": "already_terminal",
            "status": "completed",
        }))
        args = SimpleNamespace(id="bf-done")
        rc = cmd_backfills_cancel(args)
        assert rc == 1


class TestCmdBackfillsRetry:
    def test_basic(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(202, {"backfill_id": "bf-new"}))
        args = SimpleNamespace(id="bf-old")
        rc = cmd_backfills_retry_failed(args)
        assert rc == 0
        assert captured["path"] == "/backfills/retry-failed"
        assert captured["query"] == {"id": "bf-old"}


# ──────────────────────────────────────────────────────────────────────────────
# main() — top-level parser
# ──────────────────────────────────────────────────────────────────────────────

class TestMain:
    def test_no_args_prints_help(self, capsys):
        rc = main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert "slsflow" in out
        assert "backfill pipeline" in out

    def test_help_flag(self, capsys):
        rc = main(["--help"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Available commands" in out

    def test_dispatches_to_backfill_pipeline(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        rc = main([
            "backfill", "pipeline", "daily-etl",
            "--start", "2024-01-15", "--end", "2024-01-17",
            "--max-parallel", "3",
        ])
        assert rc == 0
        assert captured["body"]["target"]["name"] == "daily-etl"
        assert captured["body"]["options"]["max_parallel"] == 3

    def test_dispatches_to_backfill_asset_with_cascade(self, monkeypatch):
        captured = _stub_api(monkeypatch)
        rc = main([
            "backfill", "asset", "catalog/db/orders",
            "--start", "2024-01-15", "--end", "2024-01-15",
            "--cascade", "none",
        ])
        assert rc == 0
        assert captured["body"]["cascade"] == "none"

    def test_dispatches_to_backfills_list(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfills": []}))
        rc = main(["backfills", "list", "--status", "active"])
        assert rc == 0
        assert captured["path"] == "/backfills"

    def test_dispatches_to_backfills_show(self, monkeypatch):
        captured = _stub_api(monkeypatch, response=(200, {"backfill_id": "bf-x"}))
        rc = main(["backfills", "show", "bf-x"])
        assert rc == 0
        assert captured["query"] == {"id": "bf-x"}

    def test_invalid_args_exits(self, capsys):
        # Missing --start for backfill pipeline
        with pytest.raises(SystemExit):
            main(["backfill", "pipeline", "p"])
