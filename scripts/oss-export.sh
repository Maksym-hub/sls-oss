#!/usr/bin/env bash
#
# oss-export.sh — produce the public (free, open-core) source tree from this
# private (full) repo, verify it is self-contained, and optionally push a
# snapshot to the public remote.
#
# One-way SNAPSHOT mirror (not git-filter): the public repo gets a fresh
# "Sync from private @ <sha>" commit each run, so private history — and the
# proprietary roots inside it — never reach the public repo. ADR #98/#99/#100.
#
# The strip = remove the three proprietary roots + the slsflow-ai entry point +
# local secrets. Free code reaches paid only through the generated EE stub (UI)
# and `try: import ee` (backend), so the stripped tree still builds.
#
# Usage:
#   scripts/oss-export.sh [--target DIR] [--remote URL] [--branch main]
#                         [--scrub-account-id ID] [--no-verify] [--push]
#
# Default is SAFE: it builds + verifies the public tree and commits it locally,
# but does NOT push. Inspect the result, then re-run with --push.
set -euo pipefail

TARGET="../slsflow-oss"
REMOTE=""
BRANCH="main"
SCRUB_ACCOUNT_ID=""
VERIFY=1
PUSH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --target)            TARGET="$2"; shift 2 ;;
    --remote)            REMOTE="$2"; shift 2 ;;
    --branch)            BRANCH="$2"; shift 2 ;;
    --scrub-account-id)  SCRUB_ACCOUNT_ID="$2"; shift 2 ;;
    --no-verify)         VERIFY=0; shift ;;
    --push)              PUSH=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
SHA="$(git -C "$ROOT" rev-parse --short HEAD)"

# Proprietary roots (the strip), local secrets, and caches. -a below preserves
# the console_api/slsflow symlink (slsflow/ still exists in the public tree).
EXCLUDES=(
  '/ui/src/ee/'                       # paid UI — both tiers (ADR #99/#100)
  '/sam/lambdas/console_api/ee/'      # paid backend routes (ADR #98)
  '/slsflow/_ee/'                     # paid SDK (slsflow-ai)
  '/sam/samconfig.toml'               # live deploy secrets — never publish
  '.env' '.env.local' '*.pem' 'id_ed25519*' 'id_rsa*'
  '.git/' 'node_modules/' '.next/' 'out/'
  '__pycache__/' '.pytest_cache/' '.ruff_cache/' '.mypy_cache/' '*.pyc'
)

echo "→ strip: $ROOT  ->  $TARGET   (@ $SHA)"
mkdir -p "$TARGET"
rsync_args=(-a --delete)
for e in "${EXCLUDES[@]}"; do rsync_args+=(--exclude "$e"); done
# Keep the public repo's own .git: exclude it from deletion.
rsync "${rsync_args[@]}" --filter='protect /.git/' "$ROOT/" "$TARGET/"

# Drop the slsflow-ai entry point (it lives in the stripped slsflow/_ee/).
sed -i '/^slsflow-ai[[:space:]]*=/d' "$TARGET/pyproject.toml"

# Patch tooling that hard-codes stripped proprietary test paths, so `make test`
# and CI run the free suites only in the public tree (otherwise pytest errors on
# the missing dirs). Covers current + future tiers.
sed -i 's| slsflow/_ee/tests/||g; s| ee/team/tests/||g; s| ee/enterprise/tests/||g' \
  "$TARGET/Makefile" "$TARGET/.github/workflows/ci.yml" 2>/dev/null || true

# Strip any test that imports paid (ee) code — the code it exercises is gone with
# the strip, so it cannot run in the public tree. Paid tests inside ee/ were
# already removed by the rsync; this catches paid tests living elsewhere (e.g.
# tests/integration that exercises a Team route).
while IFS= read -r f; do
  rm -f "$f"; echo "  stripped paid test: ${f#"$TARGET"/}"
done < <(grep -rlE 'ee\.(team|enterprise)|\b_ee\b' "$TARGET" --include='*.py' 2>/dev/null || true)

# Optional: scrub a known AWS account id out of example pipelines etc.
if [ -n "$SCRUB_ACCOUNT_ID" ]; then
  echo "→ scrub account id $SCRUB_ACCOUNT_ID -> <AWS_ACCOUNT_ID>"
  grep -rlF "$SCRUB_ACCOUNT_ID" "$TARGET" 2>/dev/null \
    | xargs -r sed -i "s/$SCRUB_ACCOUNT_ID/<AWS_ACCOUNT_ID>/g" || true
fi

# Secret scan — abort before commit/push if anything sensitive leaked through.
echo "→ secret scan"
# High-signal only (avoids false positives on boto's aws_secret_access_key param
# name in normal code). samconfig.toml — the real secret holder — is excluded above.
PATTERNS='AKIA[0-9A-Z]{16}|-----BEGIN[A-Z ]*PRIVATE KEY-----'
[ -n "$SCRUB_ACCOUNT_ID" ] && PATTERNS="$PATTERNS|$SCRUB_ACCOUNT_ID"
if grep -rIEl "$PATTERNS" "$TARGET" --exclude-dir=.git 2>/dev/null | grep -q .; then
  echo "✗ ABORT — sensitive pattern found in the export tree:" >&2
  grep -rIEl "$PATTERNS" "$TARGET" --exclude-dir=.git 2>/dev/null | sed 's/^/    /' >&2
  echo "  Scrub these (or add to EXCLUDES) and re-run." >&2
  exit 1
fi

# Verify the stripped tree is self-contained (no free->ee leak) and builds.
if [ "$VERIFY" = 1 ]; then
  echo "→ verify: UI OSS build"
  ( cd "$TARGET/ui" && npm ci --silent && npm run build >/dev/null && bash scripts/check-oss-build.sh )
  echo "→ verify: SDK + free backend tests"
  ( cd "$TARGET" && pip install -e . --break-system-packages -q \
      && python -m pytest tests/sdk/ tests/integration/ -q \
      && ( cd sam/lambdas/console_api && PYTHONPATH=. python -m pytest tests/ -q ) )
else
  echo "→ verify skipped (--no-verify)"
fi

# Snapshot commit (+ optional push).
cd "$TARGET"
if [ ! -d .git ]; then
  git init -q -b "$BRANCH"
  [ -n "$REMOTE" ] && git remote add origin "$REMOTE"
fi
git add -A
if git diff --cached --quiet; then
  echo "→ no changes since last export"
else
  git commit -q -s -m "Sync from private @ $SHA"
  echo "→ committed snapshot ($SHA)"
fi

if [ "$PUSH" = 1 ]; then
  [ -z "$REMOTE" ] && { echo "✗ --push needs --remote (or a configured origin)" >&2; exit 2; }
  git push -u origin "$BRANCH"
  echo "✓ pushed to $REMOTE ($BRANCH)"
else
  echo "✓ public tree ready at $TARGET — inspect, then re-run with --push"
fi