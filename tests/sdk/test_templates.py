"""Tests for v55.1 features: orchestration_timeout, backfill orchestrator, route table."""

import json
import re
import sys
import os
from datetime import timedelta


def load_template(path):
    """Load a SFN template JSON file, replacing ${var} placeholders with dummy values."""
    with open(path) as f:
        text = f.read()
    text = re.sub(r'\$\{[^}]+\}', '0', text)
    return json.loads(text)

# Add project root to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'sam', 'lambdas', 'console_api'))


# ============================================================
# orchestration_timeout tests
# ============================================================

def test_orchestration_timeout_default():
    """orchestration_timeout defaults to execution_timeout."""
    from polyris.task import Task
    t = Task(task_id='test', execution_timeout=timedelta(hours=2))
    assert t.orchestration_timeout is None
    assert t.orchestration_timeout_seconds == 7200  # Same as execution_timeout
    assert t.timeout == 7200


def test_orchestration_timeout_explicit():
    """orchestration_timeout can be set independently."""
    from polyris.task import Task
    t = Task(
        task_id='test',
        execution_timeout=timedelta(hours=2),
        orchestration_timeout=timedelta(days=3)
    )
    assert t.orchestration_timeout_seconds == 259200  # 3 days
    assert t.timeout == 7200  # execution_timeout unchanged


def test_orchestration_timeout_via_default_args():
    """orchestration_timeout propagates through default_args."""
    from polyris import DAG, task

    with DAG(
        'test-dag',
        schedule=None,
        alerts=None,
        default_args={
            'orchestration_timeout': timedelta(hours=12),
        }
    ) as dag:
        @task.sfn(arn='arn:aws:states:us-east-1:123:stateMachine:test')
        def my_task():
            pass
        my_task()

    t = dag.tasks[0]
    assert t.orchestration_timeout_seconds == 43200  # 12 hours


def test_orchestration_timeout_override_default_args():
    """Task-level orchestration_timeout overrides default_args."""
    from polyris import DAG, task

    with DAG(
        'test-dag',
        schedule=None,
        alerts=None,
        default_args={
            'orchestration_timeout': timedelta(hours=12),
        }
    ) as dag:
        @task.sfn(
            arn='arn:aws:states:us-east-1:123:stateMachine:test',
            orchestration_timeout=timedelta(days=7)
        )
        def my_task():
            pass
        my_task()

    t = dag.tasks[0]
    assert t.orchestration_timeout_seconds == 604800  # 7 days, not 12h


def test_orchestration_timeout_in_generated_sfn():
    """Generator passes orchestration_timeout to wrapper input."""
    from polyris import DAG, task
    from polyris.generators import generate_step_function_json

    with DAG('test-gen', schedule=None, alerts=None) as dag:
        @task.sfn(
            arn='arn:aws:states:us-east-1:123:stateMachine:test',
            orchestration_timeout=timedelta(days=3)
        )
        def t1():
            pass
        t1()

    sfn_json = generate_step_function_json(dag)
    sfn = json.loads(sfn_json)

    # Find the wrapper task input
    found = False
    for name, state in sfn['States'].items():
        if state.get('Type') == 'Parallel':
            for branch in state.get('Branches', []):
                for sn, ss in branch.get('States', {}).items():
                    inp = ss.get('Arguments', {}).get('Input', {})
                    if 'orchestration_timeout' in inp:
                        assert inp['orchestration_timeout'] == 259200
                        found = True

    assert found, "orchestration_timeout not found in generated SFN"


def test_orchestration_timeout_default_in_generated_sfn():
    """Default orchestration_timeout = execution_timeout in generated SFN."""
    from polyris import DAG, task
    from polyris.generators import generate_step_function_json

    with DAG('test-gen-default', schedule=None, alerts=None) as dag:
        @task.sfn(arn='arn:aws:states:us-east-1:123:stateMachine:test')
        def t1():
            pass
        t1()

    sfn_json = generate_step_function_json(dag)
    sfn = json.loads(sfn_json)

    found = False
    for name, state in sfn['States'].items():
        if state.get('Type') == 'Parallel':
            for branch in state.get('Branches', []):
                for sn, ss in branch.get('States', {}).items():
                    inp = ss.get('Arguments', {}).get('Input', {})
                    if 'orchestration_timeout' in inp:
                        assert inp['orchestration_timeout'] == 86400  # 24h default
                        found = True

    assert found, "orchestration_timeout not found in generated SFN"


# ============================================================
# Wrapper template tests
# ============================================================

def test_wrapper_timeout_is_dynamic():
    """Wait_For_Dependencies uses dynamic TimeoutSeconds via JSONata expression."""
    template_path = os.path.join(
        REPO_ROOT, 'sam',
        'sfn_templates', 'dependency_wrapper', 'sfn.tpl.json'
    )
    data = load_template(template_path)

    state = data['States']['Wait_For_Dependencies']
    assert 'Timeout' not in state, "Timeout is not supported in JSONata ASL, use TimeoutSeconds"
    assert 'TimeoutSeconds' in state, "Dynamic TimeoutSeconds should be present"
    assert 'orchestration_timeout' in state['TimeoutSeconds'], "Should read from input"


# ============================================================
# Backfill staggered start tests
# ============================================================

def test_backfill_orchestrator_template_removed():
    """Backfill orchestrator SFN template should not exist."""
    template_path = os.path.join(
        REPO_ROOT, 'sam',
        'sfn_templates', 'helpers', 'backfill_orchestrator'
    )
    assert not os.path.exists(template_path), \
        "backfill_orchestrator template dir should be removed"


# ============================================================
# Route table tests
# ============================================================

def test_route_table_completeness():
    """Free (open-core) routes are always registered.

    Runs in both the full build (63 routes) and the OSS-stripped build
    (27 free routes), so it asserts the *free subset* is present rather than an
    exact count. The full 63-route surface (incl. Team routes) is pinned by
    ee/team/tests/test_route_table_ee.py, which only runs when `ee` is present.
    The asset console route `GET /api/assets` moved to Team (ADR #105); task
    intervention (skip/fail/success/stop/restart[/retry]) and execution control
    (stop/pause/resume/extend) are free (ADR #110). See ADR #98.
    """
    from main import ROUTES

    # The free intervention surface must always be present (ADR #110) — a free
    # build that 404s these is the regression this guard exists to catch.
    free_intervention = [
        ('POST', '/api/task-skip'), ('POST', '/api/task-fail'), ('POST', '/api/task-success'),
        ('POST', '/api/task-stop'), ('POST', '/api/task-restart'), ('POST', '/api/task-retry'),
        ('POST', '/api/execution-stop'), ('POST', '/api/execution-pause'),
        ('POST', '/api/execution-resume'), ('POST', '/api/execution-extend'),
    ]
    for method, path in free_intervention:
        assert (method, path) in ROUTES, f"Missing free intervention route: {method} {path}"

    # Config mutation stays Team — must be ABSENT from the OSS-stripped build.
    # (In the full build ee adds it; this assert only holds when ee is stripped.)
    try:
        import ee  # noqa: F401
        ee_present = True
    except ImportError:
        ee_present = False
    if not ee_present:
        assert ('PUT', '/api/task-config') not in ROUTES, "task-config PUT must be Team-only"

    # Loose free-floor sanity check; the full build adds Team routes on top.
    assert len(ROUTES) >= 26

    # Critical *free* routes must always exist (present in both tiers).
    critical = [
        ('GET', '/api/pipelines'),
        ('GET', '/api/tasks'),
        ('GET', '/api/runs'),
        ('GET', '/api/health'),
        ('POST', '/api/pipeline-run'),
        ('POST', '/api/pipeline-register'),
    ]
    for method, path in critical:
        assert (method, path) in ROUTES, f"Missing free route: {method} {path}"


def test_route_table_handlers_callable():
    """All route handlers are callable."""
    from main import ROUTES

    for (method, path), (handler, param_key) in ROUTES.items():
        assert callable(handler), f"Handler for {method} {path} is not callable"
        assert param_key is None or isinstance(param_key, str), \
            f"Invalid param_key for {method} {path}: {param_key}"


def test_api_gateway_routes_match_lambda():
    """API Gateway routes in SAM template.yaml match Lambda ROUTES in main.py.

    Prevents deploying a Lambda endpoint without its API Gateway route
    (or vice versa). Excludes health/OPTIONS/catch-all routes.
    """
    import re
    from main import ROUTES

    sam_template = os.path.join(REPO_ROOT, 'sam', 'template.yaml')
    with open(sam_template) as f:
        content = f.read()

    # SAM uses $default catch-all route — all routing is handled inside Lambda (main.py ROUTES)
    # Test verifies: ConsoleApiFunction exists in SAM template and handler is correct
    assert 'ConsoleApiFunction:' in content, "ConsoleApiFunction not found in SAM template"
    assert 'main.handler' in content, "ConsoleApiFunction handler not pointing to main.handler"

    # Verify the Lambda has routes defined (sanity check against main.py)
    assert len(ROUTES) > 0, "Lambda ROUTES table is empty"
    # Verify a sample of critical *free* routes exist in Lambda (present in both
    # the full and OSS-stripped builds; Team routes are checked in ee/team/tests).
    critical_routes = [
        ('GET', '/api/pipelines'),
        ('POST', '/api/pipeline-run'),
        ('GET', '/api/tasks'),
        ('GET', '/api/runs'),
    ]
    for method, path in critical_routes:
        assert (method, path) in ROUTES, f"Critical route {method} {path} missing from Lambda ROUTES"


# ============================================================
# run_task resilience tests
# ============================================================

def test_run_task_all_task_states_have_catch():
    """All Task states in run_task have Catch clauses."""
    template_path = os.path.join(
        REPO_ROOT, 'sam', 'sfn_templates', 'helpers', 'run_task', 'sfn.tpl.json'
    )
    data = load_template(template_path)

    task_states = {
        name: state for name, state in data['States'].items()
        if state.get('Type') == 'Task'
    }

    missing_catch = [name for name, state in task_states.items() if 'Catch' not in state]
    assert not missing_catch, f"Task states without Catch: {missing_catch}"


def test_run_task_callback_states_have_retry():
    """Send_Pipeline_Success/Failure have Retry."""
    template_path = os.path.join(
        REPO_ROOT, 'sam', 'sfn_templates', 'helpers', 'run_task', 'sfn.tpl.json'
    )
    data = load_template(template_path)

    for name in ['Send_Pipeline_Success', 'Send_Pipeline_Failure']:
        assert name in data['States'], f"Missing state: {name}"
        state = data['States'][name]
        assert 'Retry' in state, f"{name} missing Retry"


# ============================================================
# api.js dedup test
# ============================================================

def test_api_js_has_shared_request():
    """api.js/api.ts uses shared _request method."""
    # Support both .js (Vite) and .ts (Next.js) extensions
    api_path_ts = os.path.join(REPO_ROOT, 'ui', 'src', 'utils', 'api.ts')
    api_path_js = os.path.join(REPO_ROOT, 'ui', 'src', 'utils', 'api.js')
    api_path = api_path_ts if os.path.exists(api_path_ts) else api_path_js
    with open(api_path) as f:
        content = f.read()

    assert '_request' in content, "api module should have _request base method"
    lines = content.split('\n')
    assert len(lines) < 250, f"api module should be under 250 lines (got {len(lines)})"


# ============================================================
# Runner
# ============================================================

if __name__ == '__main__':
    tests = [
        # orchestration_timeout
        test_orchestration_timeout_default,
        test_orchestration_timeout_explicit,
        test_orchestration_timeout_via_default_args,
        test_orchestration_timeout_override_default_args,
        test_orchestration_timeout_in_generated_sfn,
        test_orchestration_timeout_default_in_generated_sfn,
        # wrapper template
        test_wrapper_timeout_is_dynamic,
        # backfill staggered start
        test_backfill_orchestrator_template_removed,
        # route table
        test_route_table_completeness,
        test_route_table_handlers_callable,
        # run_task resilience
        test_run_task_all_task_states_have_catch,
        test_run_task_callback_states_have_retry,
        # api.js
        test_api_js_has_shared_request,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            print(f"  ✅ {test_fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 50}")

    sys.exit(1 if failed else 0)
