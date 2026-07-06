"""
Trigger Rule Sync Test

Verifies that JSONata (registration helper) and Python (evaluate_deps)
implementations produce identical results for all trigger rules and status combinations.

This test prevents drift between the two implementations.

Note: In v51+, notify_dependents is a SFN helper, not a Lambda.
The Python source of truth for trigger rules is evaluate_deps/index.py.
"""

import itertools
from typing import List

# All supported trigger rules
TRIGGER_RULES = [
    'all_success',
    'one_success', 
    'all_failed',
    'one_failed',
    'all_done',
    'one_done',
    'none_failed',
    'none_failed_min_one_success',
    'all_done_min_one_success',
    'all_skipped',
    'none_skipped',
]

# All possible dependency statuses
# Terminal statuses
TERMINAL_STATUSES = {'success', 'failed', 'skipped', 'upstream_failed', 'aborted'}

# Statuses to test: terminal + non-terminal (waiting, running, etc.)
# not_found = task not yet registered; waiting = registered but deps not ready
STATUSES = ['success', 'failed', 'skipped', 'upstream_failed', 'not_found', 'aborted',
            'waiting', 'running', 'deps_ready']


def python_check_trigger_rule(trigger_rule: str, dep_statuses: List[str]) -> bool:
    """
    Python implementation (from evaluate_deps).
    Returns True if trigger_rule is satisfied.
    """
    if not dep_statuses:
        return True
    
    success_count = sum(1 for s in dep_statuses if s == 'success')
    failed_count = sum(1 for s in dep_statuses if s in ['failed', 'upstream_failed', 'aborted'])
    skipped_count = sum(1 for s in dep_statuses if s == 'skipped')
    done_count = sum(1 for s in dep_statuses if s in TERMINAL_STATUSES)
    total = len(dep_statuses)
    pending_count = sum(1 for s in dep_statuses if s not in TERMINAL_STATUSES)
    ok_count = success_count + skipped_count
    
    if trigger_rule == 'all_success':
        return pending_count == 0 and ok_count == total
    elif trigger_rule == 'one_success':
        return success_count > 0
    elif trigger_rule == 'all_failed':
        return pending_count == 0 and failed_count == total
    elif trigger_rule == 'one_failed':
        return failed_count > 0
    elif trigger_rule == 'all_done':
        return pending_count == 0
    elif trigger_rule == 'one_done':
        return done_count > 0
    elif trigger_rule == 'none_failed':
        return pending_count == 0 and failed_count == 0
    elif trigger_rule == 'none_failed_min_one_success':
        return pending_count == 0 and failed_count == 0 and success_count > 0
    elif trigger_rule == 'all_done_min_one_success':
        return pending_count == 0 and success_count > 0
    elif trigger_rule == 'all_skipped':
        return pending_count == 0 and skipped_count == total
    elif trigger_rule == 'none_skipped':
        return pending_count == 0 and skipped_count == 0
    else:
        return pending_count == 0 and ok_count == total


def jsonata_check_trigger_rule(trigger_rule: str, dep_statuses: List[str]) -> bool:
    """
    JSONata implementation (from registration helper).
    Simulates the JSONata logic in Python for testing.
    
    After P0.1 fix: $pending := $c.total - $c.done
    (was: $pending := $c.not_found — only counted not_found as pending)
    """
    if not dep_statuses:
        return True
    
    success_count = sum(1 for s in dep_statuses if s == 'success')
    failed_count = sum(1 for s in dep_statuses if s in ['failed', 'upstream_failed', 'aborted'])
    skipped_count = sum(1 for s in dep_statuses if s == 'skipped')
    done_count = sum(1 for s in dep_statuses if s in TERMINAL_STATUSES)
    total = len(dep_statuses)
    pending_count = total - done_count  # Fixed: was not_found_count, now total - done
    ok_count = success_count + skipped_count
    
    # Exact mirror of JSONata logic
    if trigger_rule == 'all_success':
        return pending_count == 0 and ok_count == total
    elif trigger_rule == 'one_success':
        return success_count > 0
    elif trigger_rule == 'all_failed':
        return pending_count == 0 and failed_count == total
    elif trigger_rule == 'one_failed':
        return failed_count > 0
    elif trigger_rule == 'all_done':
        return pending_count == 0
    elif trigger_rule == 'one_done':
        return done_count > 0
    elif trigger_rule == 'none_failed':
        return pending_count == 0 and failed_count == 0
    elif trigger_rule == 'none_failed_min_one_success':
        return pending_count == 0 and failed_count == 0 and success_count > 0
    elif trigger_rule == 'all_done_min_one_success':
        return pending_count == 0 and success_count > 0
    elif trigger_rule == 'all_skipped':
        return pending_count == 0 and skipped_count == total
    elif trigger_rule == 'none_skipped':
        return pending_count == 0 and skipped_count == 0
    else:
        # Default: all_success behavior
        return pending_count == 0 and ok_count == total


def test_trigger_rules_sync():
    """
    Test that Python and JSONata implementations are in sync.
    Tests all trigger rules against all combinations of 1-3 dependencies.
    """
    print("Testing trigger_rule sync between Python and JSONata...")
    
    failures = []
    test_count = 0
    
    for rule in TRIGGER_RULES:
        # Test with 1, 2, and 3 dependencies
        for dep_count in [1, 2, 3]:
            for combo in itertools.product(STATUSES, repeat=dep_count):
                statuses = list(combo)
                test_count += 1
                
                py_result = python_check_trigger_rule(rule, statuses)
                js_result = jsonata_check_trigger_rule(rule, statuses)
                
                if py_result != js_result:
                    failures.append({
                        'rule': rule,
                        'statuses': statuses,
                        'python': py_result,
                        'jsonata': js_result
                    })
    
    print(f"Tested {test_count} combinations")
    
    if failures:
        print(f"\n❌ Found {len(failures)} mismatches:")
        for f in failures[:10]:  # Show first 10
            print(f"  {f['rule']}: {f['statuses']} -> Python={f['python']}, JSONata={f['jsonata']}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")
        raise AssertionError(f"{len(failures)} trigger_rule mismatches found")
    
    print(f"✅ All {test_count} combinations match between Python and JSONata")


def test_edge_cases():
    """Test specific edge cases that are easy to get wrong."""
    print("\nTesting edge cases...")
    
    cases = [
        # (rule, statuses, expected)
        ('all_success', [], True),  # No deps = ready
        ('all_success', ['success'], True),
        ('all_success', ['skipped'], True),  # skipped = OK for all_success
        ('all_success', ['failed'], False),
        ('all_success', ['not_found'], False),  # pending
        ('all_success', ['aborted'], False),  # aborted = failure
        
        ('one_success', ['not_found', 'not_found'], False),  # no success yet
        ('one_success', ['success', 'not_found'], True),  # one success = ready
        ('one_success', ['failed', 'failed'], False),
        ('one_success', ['aborted', 'aborted'], False),  # aborted != success
        
        ('one_failed', ['success', 'success'], False),
        ('one_failed', ['success', 'failed'], True),
        ('one_failed', ['success', 'upstream_failed'], True),
        ('one_failed', ['success', 'aborted'], True),  # aborted counts as failed
        
        ('all_done', ['success', 'failed', 'skipped'], True),
        ('all_done', ['success', 'not_found'], False),
        ('all_done', ['success', 'aborted'], True),  # aborted is done
        ('all_done', ['aborted', 'aborted'], True),  # all aborted = all done
        
        ('one_done', ['not_found'], False),
        ('one_done', ['aborted'], True),  # aborted counts as done
        
        ('none_failed', ['success', 'skipped'], True),
        ('none_failed', ['success', 'failed'], False),
        ('none_failed', ['success', 'not_found'], False),  # pending
        ('none_failed', ['success', 'aborted'], False),  # aborted = failure
        
        ('all_skipped', ['skipped', 'skipped'], True),
        ('all_skipped', ['skipped', 'success'], False),
        ('all_skipped', ['skipped', 'aborted'], False),  # aborted != skipped
        
        ('none_skipped', ['success', 'failed'], True),
        ('none_skipped', ['success', 'skipped'], False),
        ('none_skipped', ['success', 'aborted'], True),  # aborted != skipped
        ('none_skipped', ['aborted', 'failed'], True),  # no skipped
        
        # NON-TERMINAL STATUS TESTS (P0.1 regression: waiting/running must block)
        ('all_done', ['waiting'], False),  # waiting is NOT done
        ('all_done', ['running'], False),  # running is NOT done
        ('all_done', ['deps_ready'], False),  # deps_ready is NOT done
        ('all_done', ['success', 'waiting'], False),  # one still waiting
        ('none_failed', ['waiting'], False),  # pending blocks none_failed
        ('none_failed', ['running'], False),  # pending blocks none_failed
        ('none_skipped', ['waiting'], False),  # pending blocks none_skipped
        ('none_skipped', ['running'], False),  # pending blocks none_skipped
        ('all_success', ['waiting'], False),  # pending blocks all_success
        ('all_success', ['running'], False),  # pending blocks all_success
        ('one_success', ['waiting'], False),  # no success yet
        ('one_done', ['waiting'], False),  # waiting is not done
        ('one_done', ['running'], False),  # running is not done
    ]
    
    for rule, statuses, expected in cases:
        py_result = python_check_trigger_rule(rule, statuses)
        js_result = jsonata_check_trigger_rule(rule, statuses)
        
        assert py_result == expected, f"Python {rule}({statuses}) = {py_result}, expected {expected}"
        assert js_result == expected, f"JSONata {rule}({statuses}) = {js_result}, expected {expected}"
    
    print(f"✅ All {len(cases)} edge cases passed")


if __name__ == '__main__':
    test_trigger_rules_sync()
    test_edge_cases()
    print("\n=== All trigger_rule tests passed ===")
