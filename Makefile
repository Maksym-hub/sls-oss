.PHONY: test test-sdk test-backend test-integration test-lambdas test-ui test-sfn-jsonata e2e-health e2e-smoke check lint sync-constants check-versions smoke-pipelines help oss-export

# Default target
help:
	@echo "slsflow Development Commands"
	@echo ""
	@echo "  make test              - Run all tests (sdk + backend + integration + lambdas + sfn-jsonata + ui)"
	@echo "  make test-sdk          - Run SDK tests only (ASL generation, templates, trigger rules)"
	@echo "  make test-backend      - Run backend API tests only (routes, alerting)"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-lambdas      - Run Lambda inline tests only"
	@echo "  make test-sfn-jsonata  - Run SFN JSONata expression tests"
	@echo "  make test-ui           - Run UI tests only"
	@echo "  make e2e-health        - E2E: hit live API /health (needs SLSFLOW_API_URL)"
	@echo "  make e2e-smoke         - E2E: read-only + backfill smoke vs live AWS (needs SLSFLOW_API_URL + SLSFLOW_ID_TOKEN)"
	@echo "  make check             - Run all checks (lint, sync, versions, smoke, test)"
	@echo "  make lint              - Check Python + JSON syntax"
	@echo "  make sync-constants    - Verify Lambda constants in sync"
	@echo "  make check-versions    - Verify version consistency across files"
	@echo "  make smoke-pipelines   - Verify all pipelines import cleanly"
	@echo "  make oss-export        - Produce + verify the public (free) source tree (no push)"
	@echo ""

# Run all tests
test: test-sdk test-backend test-integration test-lambdas test-sfn-jsonata test-ui

# SDK tests (smoke + trigger rules + SFN flow + ASL snapshots)
test-sdk:
	@echo "🧪 Running SDK tests..."
	python -m pytest tests/sdk/ -v

# Backend API tests (routes, alerting)
test-backend:
	@echo "🧪 Running Backend tests..."
	python -m pytest tests/backend/ -v

# Integration tests (cross-layer)
test-integration:
	@echo "🧪 Running Integration tests..."
	python -m pytest tests/integration/ -v

# Lambda tests
test-lambdas:
	@echo "🧪 Running Lambda tests..."
	cd sam/lambdas/evaluate_deps && PYTHONPATH=. python -m pytest test_evaluate_deps.py -v
	@if [ -d sam/lambdas/notify_asset_subscribers ] && [ -f sam/lambdas/notify_asset_subscribers/test_notify_asset_subscribers.py ]; then \
		cd sam/lambdas/notify_asset_subscribers && PYTHONPATH=. python -m pytest test_notify_asset_subscribers.py -v; \
	fi
	@if [ -f sam/lambdas/check_assets/test_check_assets.py ]; then \
		echo "  Running check_assets tests..."; \
		cd sam/lambdas/check_assets && PYTHONPATH=. python -m pytest test_check_assets.py -v; \
	fi
	@if [ -d sam/lambdas/console_api/tests ]; then \
		echo "  Running console_api tests (requires boto3, pytest-mock)..."; \
		cd sam/lambdas/console_api && PYTHONPATH=. python -m pytest tests/ -v 2>/dev/null || \
			echo "  ⚠️  console_api tests skipped (run: pip install -e '.[dev]')"; \
	fi

# SFN JSONata expression tests (requires Node.js)
test-sfn-jsonata:
	@echo "🧪 Running SFN JSONata tests..."
	@if [ -f tests/sfn_jsonata/node_modules/.package-lock.json ]; then \
		cd tests/sfn_jsonata && npm test; \
	else \
		echo "  Installing jsonata..."; \
		cd tests/sfn_jsonata && npm install --silent && npm test; \
	fi

# UI tests (requires npm install first)
test-ui:
	@echo "🧪 Running UI tests..."
	@if [ -f ui/node_modules/.package-lock.json ]; then \
		cd ui && npm test -- --run; \
	else \
		echo "  ⚠️  UI tests skipped (run: cd ui && npm ci)"; \
	fi

# =============================================================================
# E2E (hit a LIVE deployed API — not part of `make test`/CI by default)
# =============================================================================
# e2e-health : read-only /health probe. No token. Safe anywhere.
# e2e-smoke  : read-only routes + real backfill (triggers a live SFN run, ~$0.001).
#              Needs SLSFLOW_API_URL and SLSFLOW_ID_TOKEN.
#              Token helper:  export SLSFLOW_ID_TOKEN=$$(scripts/get-e2e-token.sh)
e2e-health:
	@: "$${SLSFLOW_API_URL:?set SLSFLOW_API_URL (e.g. https://abc.execute-api.us-east-1.amazonaws.com)}"
	@echo "🌐 E2E health probe against $$SLSFLOW_API_URL ..."
	python -m pytest tests/e2e/test_health.py -v

e2e-smoke:
	@: "$${SLSFLOW_API_URL:?set SLSFLOW_API_URL}"
	@: "$${SLSFLOW_ID_TOKEN:?set SLSFLOW_ID_TOKEN (use scripts/get-e2e-token.sh)}"
	@echo "🌐 E2E read-only routes ..."
	python -m pytest tests/e2e/ -v -m "not write"
	@echo "🌐 E2E backfill smoke (live SFN+DDB) ..."
	python -m pytest tests/e2e/test_backfill.py -v -m smoke

# All checks before commit
check: lint sync-constants check-versions smoke-pipelines test
	@echo "✅ All checks passed!"

# Python syntax + JSON template validation
lint:
	@echo "🔍 Checking Python syntax..."
	@find slsflow/ -name "*.py" -not -path "*/__pycache__/*" | xargs -I{} python -m py_compile {}
	@find sam/lambdas/ -name "*.py" -not -path "*/__pycache__/*" | xargs -I{} python -m py_compile {}
	@find pipelines/ -name "*.py" -not -path "*/__pycache__/*" | xargs -I{} python -m py_compile {}
	@echo "🔍 Running ruff (E,F,W)..."
	@ruff check .
	@echo "🔍 Checking JSON templates..."
	@# .tpl.json files contain ${var} substitutions that break json.load (CLAUDE.md SFN Pitfall #1).
	@# Strip them the same way CI does before validating.
	@find sam/sfn_templates -name "*.json" | while read f; do \
		python3 -c "import json, re, sys; \
src = open('$$f').read(); \
src = re.sub(r'\"\\\$$\\{[^}]+\\}\"', '\"X\"', src); \
src = re.sub(r':\s*\\\$$\\{[^}]+\\}', ': 0', src); \
src = re.sub(r'\\\$$\\{[^}]+\\}', 'X', src); \
json.loads(src)" 2>&1 || (echo "❌ Invalid JSON: $$f" && exit 1); \
	done
	@echo "🔍 Checking SAM template (cfn-lint)..."
	@# CLAUDE.md Principle 4: every change goes through pytest + cfn-lint + syntax check.
	@# CI has a dedicated cfn-lint job (.github/workflows/ci.yml); this keeps the
	@# local `make check` workflow in sync so a CFN regression is caught before push.
	@command -v cfn-lint >/dev/null 2>&1 || (echo "❌ cfn-lint not installed (pip install cfn-lint)" && exit 1)
	@cfn-lint sam/template.yaml
	@echo "✅ Syntax OK"

# Generate enum mirrors from slsflow/constants.py (ADR #72, v0.79.0)
# Writes:
#   - sam/lambdas/_shared/constants_generated.py
#   - sam/lambdas/console_api/constants_generated.py
#   - ui/src/generated/enums.ts
generate-enums:
	@echo "🔄 Generating enum mirrors from slsflow/constants.py..."
	@python -m slsflow.codegen.sync_enums

# Check generated enum files are in sync (CI gate)
check-generate-enums:
	@python -m slsflow.codegen.sync_enums --check

# Check SFN template status literals against canonical (v0.79.6, ADR #78).
# Catches typos in JSONata expressions and drift between templates and
# slsflow.constants.TaskStatus. Run in CI to prevent silent breakage.
check-sfn-templates:
	@python -m slsflow.codegen.check_sfn_templates

# Check backfill terminal-status parity (v0.80.0, ADR #83). Verifies the
# bulk_backfill SFN Finalize JSONata encodes the same rule as the canonical
# slsflow.backfill_status.finalize_status. Catches the ADR #81/#82 drift
# class (raw-vs-derived, stray skipped term) at CI time.
check-backfill-parity:
	@python -m slsflow.codegen.check_backfill_status_parity

# Sync logger.py from _shared/ to each Lambda (v0.79.4, ADR #76)
sync-loggers:
	@echo "🔄 Syncing Lambda loggers..."
	@for lambda in evaluate_deps notify_asset_subscribers check_assets query_subscriptions console_api; do \
		if ! diff -q sam/lambdas/_shared/logger.py sam/lambdas/$$lambda/logger.py > /dev/null 2>&1; then \
			echo "❌ $$lambda/logger.py out of sync!"; \
			echo "   Run: cp sam/lambdas/_shared/logger.py sam/lambdas/$$lambda/logger.py"; \
			exit 1; \
		fi; \
	done
	@echo "✅ All Lambda loggers in sync"

# Validate Lambda constants are in sync
sync-constants:
	@echo "🔄 Checking Lambda constants..."
	@diff -q sam/lambdas/_shared/constants.py sam/lambdas/evaluate_deps/constants.py > /dev/null 2>&1 || \
		(echo "❌ evaluate_deps/constants.py out of sync!" && \
		 echo "   Run: cp sam/lambdas/_shared/constants.py sam/lambdas/evaluate_deps/constants.py" && exit 1)
	@python -m slsflow.codegen.check_shared_constants
	@for d in console_api check_assets evaluate_deps notify_asset_subscribers query_subscriptions; do \
		diff -q sam/lambdas/_shared/logger.py sam/lambdas/$$d/logger.py > /dev/null 2>&1 || \
		(echo "❌ sam/lambdas/$$d/logger.py drifted from _shared/logger.py!" && \
		 echo "   Run: cp sam/lambdas/_shared/logger.py sam/lambdas/$$d/logger.py" && exit 1); \
	done
	@echo "✅ Constants + logger in sync"

# Validate versions are consistent across files
check-versions:
	@echo "🔢 Checking version consistency..."
	@PY_VER=$$(grep '^version' pyproject.toml | cut -d'"' -f2) && \
	INIT_VER=$$(grep '__version__' slsflow/__init__.py | cut -d'"' -f2) && \
	PKG_VER=$$(node -p "require('./ui/package.json').version" 2>/dev/null || echo "skip") && \
	if [ "$$PY_VER" != "$$INIT_VER" ]; then \
		echo "❌ Backend mismatch: pyproject.toml=$$PY_VER vs __init__.py=$$INIT_VER"; exit 1; \
	fi && \
	if [ "$$PKG_VER" != "skip" ] && [ "$$PY_VER" != "$$PKG_VER" ]; then \
		echo "❌ Frontend mismatch: pyproject.toml=$$PY_VER vs package.json=$$PKG_VER"; exit 1; \
	fi && \
	echo "✅ Versions consistent: $$PY_VER"

# Smoke test: verify all pipeline definitions import
smoke-pipelines:
	@echo "🔍 Checking pipeline imports..."
	@COUNT=$$(find pipelines/ -name "dag.py" -not -path "*/__pycache__/*" | wc -l); \
	if [ "$$COUNT" -eq 0 ]; then \
		echo "  ⚠️  No dag.py files found in pipelines/"; \
	fi
	@find pipelines/ -name "dag.py" -not -path "*/__pycache__/*" | while read f; do \
		python -m py_compile "$$f" 2>&1 && echo "  ✅ $$f" || (echo "  ❌ $$f" && exit 1); \
	done
	@echo "✅ All pipelines OK"

# Exhaustive JSONata edge-case audit (ADR #85). Maintenance tool — runs
# 21k+ evaluations across all SFN-template expressions against
# baseline + aggressive variants. Not in CI; run before releases.
audit-jsonata:
	@python scripts/audit_jsonata.py

# Produce + verify the public (free, open-core) source tree from this private repo.
# Safe default: strips proprietary roots, builds, verifies, commits locally — no
# push. Publish with: make oss-export ARGS="--remote <url> --push". See scripts/oss-export.sh.
oss-export:
	bash scripts/oss-export.sh $(ARGS)
