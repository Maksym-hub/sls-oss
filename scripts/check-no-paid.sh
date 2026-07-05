#!/usr/bin/env bash
# ── check-no-paid.sh ─────────────────────────────────────────────────────────
# Fails if any proprietary path is tracked in this PUBLIC repo. The free product
# must never carry paid code: no `ee/` console routes, no `ui/src/ee/`, no
# `polyris/_ee/`. Run in CI on every PR (companion to ui/scripts/check-oss-build.sh,
# which proves the free build works with ee/ absent).
set -euo pipefail
cd "$(dirname "$0")/.."

paid="$(git ls-files | grep -E '(^|/)(_ee|ee)/' || true)"

if [ -n "$paid" ]; then
  echo "❌ proprietary (paid) paths are tracked in the public repo — they belong"
  echo "   only in the private polyris-ee repo. Remove them:"
  echo "$paid" | sed 's/^/     /'
  exit 1
fi

echo "✓ no paid code in the public repo — no ee/ or _ee/ paths tracked"
