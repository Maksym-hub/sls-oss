"""slsflow CLI — backfill commands + help dispatch (v0.78+, per ADR #51).

This is the main `slsflow` entry point. Without arguments it prints help.
With ``backfill`` or ``backfills`` as the first arg, dispatches to the
corresponding backfill subcommand.

Subcommands:
  slsflow backfill pipeline NAME --start DATE --end DATE [opts]
  slsflow backfill asset NAME    --start DATE --end DATE [opts]
  slsflow backfills list         [--status active|pending|running|completed|failed|partial|canceled]
  slsflow backfills show BF_ID
  slsflow backfills cancel BF_ID
  slsflow backfills retry-failed BF_ID

Configuration (env vars):
  SLSFLOW_API_URL    Base URL of the Console API. Required for backfill ops.
                     Example: https://abc123.execute-api.us-east-1.amazonaws.com/Prod
  SLSFLOW_API_TOKEN  Optional bearer token for protected deployments.

Exit codes:
  0  success
  1  API returned 4xx/5xx
  2  missing or invalid configuration
  3  network/transport failure
  4  bad CLI arguments
  130  interrupted (Ctrl-C)

Output: human-readable on stdout; structured errors on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional, Tuple


HELP_TEXT = """
slsflow - Serverless Data Pipeline Orchestration
═════════════════════════════════════════════════

Available commands:
  slsflow backfill pipeline NAME    Start a backfill for a pipeline
  slsflow backfill asset NAME       Start a backfill for an asset
  slsflow backfills list            List recent backfills
  slsflow backfills show ID         Show details of one backfill
  slsflow backfills cancel ID       Cooperatively cancel a backfill
  slsflow backfills retry-failed ID Retry failed partitions of a backfill

Deployment commands (separate entry points):
  slsflow-init         Create a new pipeline or project config
  slsflow-deploy       Deploy pipeline via CloudFormation
  slsflow-validate     Validate pipeline(s) for errors
  slsflow-output       Generate pipeline artifacts (JSON, Mermaid, graph)
  slsflow-register     Register pipeline in DynamoDB

Configuration:
  export SLSFLOW_API_URL=<console-api-url>
  export SLSFLOW_API_TOKEN=<optional-bearer-token>

Example:
  slsflow backfill pipeline daily-etl --start 2024-01-15 --end 2024-01-20
  slsflow backfills list --status active
  slsflow backfills show bf-a1b2c3d4

Documentation:
  https://github.com/Maksym-hub/slsflow
"""


# ──────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────────────────────

def _api_url() -> str:
    return os.environ.get("SLSFLOW_API_URL", "").rstrip("/")


def _api_call(
    method: str,
    path: str,
    body: Optional[dict] = None,
    query: Optional[dict] = None,
) -> Tuple[int, dict]:
    """HTTP call to the Console API. Returns ``(status_code, parsed_body)``.

    Exits with code 2 if ``SLSFLOW_API_URL`` is unset; 3 on transport
    failure. Other HTTP errors return their status to the caller for
    formatting.
    """
    base = _api_url()
    if not base:
        print(
            "Error: SLSFLOW_API_URL not set.\n"
            "Configure with:\n  export SLSFLOW_API_URL=https://<your-api-host>",
            file=sys.stderr,
        )
        sys.exit(2)

    url = f"{base}{path}"
    if query:
        qs = "&".join(f"{k}={v}" for k, v in query.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    headers = {"Content-Type": "application/json"}
    token = os.environ.get("SLSFLOW_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            payload = json.loads(text) if text else {}
            return resp.status, payload
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except (json.JSONDecodeError, ValueError):
            payload = {"error": str(e)}
        return e.code, payload
    except urllib.error.URLError as e:
        print(f"Error: failed to reach {url}: {e}", file=sys.stderr)
        sys.exit(3)


def _format_response(status: int, payload: dict) -> int:
    """Pretty-print a response. Returns intended exit code."""
    if 200 <= status < 300:
        print(json.dumps(payload, indent=2, sort_keys=False))
        return 0
    err = payload.get("error", "unknown_error")
    msg = payload.get("message", "")
    print(f"Error {status} ({err}): {msg}", file=sys.stderr)
    if "producers" in payload:
        print("Candidate producers:", file=sys.stderr)
        for p in payload["producers"]:
            print(f"  - {p.get('pipeline_name')}: task {p.get('task_id')}", file=sys.stderr)
    return 1


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_variables(spec: Optional[str]) -> dict:
    """Parse --variables option. Accepts JSON object string, or comma-
    separated key=value pairs. Returns dict (empty if None or invalid)."""
    if not spec:
        return {}
    spec = spec.strip()
    if spec.startswith("{"):
        try:
            parsed = json.loads(spec)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            print(
                f"Warning: invalid JSON in --variables: {spec!r}; ignoring",
                file=sys.stderr,
            )
            return {}
    result: dict = {}
    for pair in spec.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _build_options(args: argparse.Namespace) -> dict:
    """Common options dict from CLI args."""
    return {
        "force": args.force,
        "skip_completed": args.skip_completed,
        "incremental": args.incremental,
        "max_parallel": args.max_parallel,
        "allow_concurrent": False,
        "variables": _parse_variables(args.variables),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Command: backfill pipeline
# ──────────────────────────────────────────────────────────────────────────────

def cmd_backfill_pipeline(args: argparse.Namespace) -> int:
    body: dict = {
        "target": {"type": "pipeline", "name": args.name},
        "partitions": {"start": args.start, "end": args.end},
        "options": _build_options(args),
    }
    if args.tasks:
        body["tasks"] = (
            args.tasks.split(",") if isinstance(args.tasks, str) else args.tasks
        )

    query = {"preview": "true"} if args.preview else None
    status, payload = _api_call("POST", "/backfill", body=body, query=query)
    return _format_response(status, payload)


# ──────────────────────────────────────────────────────────────────────────────
# Command: backfill asset
# ──────────────────────────────────────────────────────────────────────────────

def cmd_backfill_asset(args: argparse.Namespace) -> int:
    body: dict = {
        "target": {"type": "asset", "name": args.name},
        "partitions": {"start": args.start, "end": args.end},
        "options": _build_options(args),
        "cascade": args.cascade,
    }

    query = {"preview": "true"} if args.preview else None
    status, payload = _api_call("POST", "/backfill", body=body, query=query)
    return _format_response(status, payload)


# ──────────────────────────────────────────────────────────────────────────────
# Command: backfills list / show / cancel / retry-failed
# ──────────────────────────────────────────────────────────────────────────────

def cmd_backfills_list(args: argparse.Namespace) -> int:
    query: dict = {}
    if args.status:
        query["status"] = args.status
    if args.limit:
        query["limit"] = str(args.limit)
    status, payload = _api_call("GET", "/backfills", query=query or None)
    return _format_response(status, payload)


def cmd_backfills_show(args: argparse.Namespace) -> int:
    status, payload = _api_call("GET", "/backfills/by-id", query={"id": args.id})
    return _format_response(status, payload)


def cmd_backfills_cancel(args: argparse.Namespace) -> int:
    status, payload = _api_call(
        "POST", "/backfills/cancel", query={"id": args.id},
    )
    return _format_response(status, payload)


def cmd_backfills_retry_failed(args: argparse.Namespace) -> int:
    status, payload = _api_call(
        "POST", "/backfills/retry-failed", query={"id": args.id},
    )
    return _format_response(status, payload)


# ──────────────────────────────────────────────────────────────────────────────
# Argument parser construction
# ──────────────────────────────────────────────────────────────────────────────

def _add_common_backfill_args(parser: argparse.ArgumentParser) -> None:
    """Shared --start/--end/--max-parallel/--force/... options."""
    parser.add_argument(
        "--start", required=True,
        help="Start date YYYY-MM-DD or partition key",
    )
    parser.add_argument(
        "--end", required=True,
        help="End date YYYY-MM-DD or partition key",
    )
    parser.add_argument(
        "--max-parallel", type=int, default=5, dest="max_parallel",
        help="Max parallel partitions (1-10, default 5)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass safety checks",
    )
    parser.add_argument(
        "--no-skip-completed", action="store_false", dest="skip_completed",
        default=True, help="Re-run already-completed partitions",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Stop on first failure (incremental mode)",
    )
    parser.add_argument(
        "--variables", help="Variables: JSON object or 'k1=v1,k2=v2'",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Show plan without actually starting",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slsflow",
        description="Serverless Data Pipeline Orchestration CLI",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="store_true",
        help="Show extended help and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── backfill (singular) ──────────────────────────────────────────────
    bf_parser = subparsers.add_parser(
        "backfill", help="Start a backfill operation",
    )
    bf_sub = bf_parser.add_subparsers(dest="bf_subcmd", required=True)

    bp = bf_sub.add_parser("pipeline", help="Backfill a pipeline")
    bp.add_argument("name", help="Pipeline name")
    _add_common_backfill_args(bp)
    bp.add_argument("--tasks", help="Comma-separated task names")
    bp.set_defaults(func=cmd_backfill_pipeline)

    ba = bf_sub.add_parser(
        "asset", help="Backfill an asset (resolves producer pipeline)",
    )
    ba.add_argument("name", help="Asset name (e.g., catalog/db/table)")
    _add_common_backfill_args(ba)
    ba.add_argument(
        "--cascade", choices=["auto", "all", "none"], default="auto",
        help="Cascade strategy for downstream consumers (default: auto)",
    )
    ba.set_defaults(func=cmd_backfill_asset)

    # ── backfills (plural) ───────────────────────────────────────────────
    bfs_parser = subparsers.add_parser(
        "backfills", help="Manage existing backfills",
    )
    bfs_sub = bfs_parser.add_subparsers(dest="bfs_subcmd", required=True)

    bl = bfs_sub.add_parser("list", help="List recent backfills")
    bl.add_argument(
        "--status",
        choices=[
            "active", "pending", "running", "completed",
            "failed", "partial", "canceled",
        ],
        help="Filter by status",
    )
    bl.add_argument("--limit", type=int, help="Max number of results (default 50)")
    bl.set_defaults(func=cmd_backfills_list)

    bs = bfs_sub.add_parser("show", help="Show backfill detail")
    bs.add_argument("id", help="Backfill ID (e.g. bf-a1b2c3d4)")
    bs.set_defaults(func=cmd_backfills_show)

    bc = bfs_sub.add_parser("cancel", help="Cooperatively cancel a backfill")
    bc.add_argument("id", help="Backfill ID")
    bc.set_defaults(func=cmd_backfills_cancel)

    brf = bfs_sub.add_parser("retry-failed", help="Retry only failed partitions")
    brf.add_argument("id", help="Backfill ID")
    brf.set_defaults(func=cmd_backfills_retry_failed)

    return parser


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.help or args.command is None:
        print(HELP_TEXT)
        return 0

    if not hasattr(args, "func"):
        parser.print_help()
        return 4

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
