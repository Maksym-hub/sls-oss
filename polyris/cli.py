"""polyris CLI — command index / help dispatch.

This is the bare ``polyris`` entry point. Its sole job is to print the list of
available commands; it performs no operations itself. Each real command is its
own console script (``polyris-init``, ``polyris-deploy``, …) wired in
``pyproject.toml``.

Backfill is a Team-tier capability and ships as ``polyris-backfill`` from the
proprietary ``polyris-ee`` package (ADR #51, revised by ADR #104 for the
open-core split). It is intentionally absent from the open-source build.
"""

from __future__ import annotations

import sys
from typing import Optional


HELP_TEXT = """\
polyris - Serverless Data Pipeline Orchestration
═════════════════════════════════════════════════

Available commands:
  polyris-init         Create a new pipeline or project config
  polyris-deploy       Deploy pipeline via CloudFormation
  polyris-validate     Validate pipeline(s) for errors
  polyris-output       Generate pipeline artifacts (JSON, Mermaid, graph)
  polyris-register     Register pipeline in DynamoDB

Each command has its own --help. Run e.g. `polyris-deploy --help`.

Team tier:
  polyris-backfill     Date-range backfill (ships with the Team edition)

Documentation:
  https://github.com/Maksym-hub/polyris
"""


def main(argv: Optional[list] = None) -> int:
    """Print the command index. Always succeeds — this entry point performs
    no work itself; the real commands are the separate ``polyris-*`` scripts."""
    print(HELP_TEXT)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
