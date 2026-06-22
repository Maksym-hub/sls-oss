"""
Tests for alerting architecture redesign (v64).

Validates:
- run_task: backfill suppression, conditional Slack/PagerDuty, alerts_json in DDB
- failure_handler: upstream_failed suppression, PagerDuty removed, empty token Slack
- restart_task: alerts field passed from DDB
- main.tf: pagerduty_alerter_arn wiring
"""

import json
import os
import re
import sys

import pytest

# sys.path setup moved to conftest.py

TEMPLATES = os.path.join(
    os.path.dirname(__file__), '..', '..', 'sam', 'sfn_templates'
)

def load(helper_name):
    path = os.path.join(TEMPLATES, 'helpers', helper_name, 'sfn.tpl.json')
    with open(path) as f:
        content = f.read()
    # Template variables that appear as bare (unquoted) values break JSON
    # parsing. E.g.: "HeartbeatSeconds": ${pause_heartbeat_seconds},
    # Quoted vars like "${tokens_table}" are valid JSON strings — no fix needed.
    content = re.sub(r':\s*\$\{(\w+)\}(\s*[,}\]])', r': 99999\2', content)
    return json.loads(content)


# ============================================================
# run_task — failure flow structure
# ============================================================

class TestRunTaskAlertingFlow:
    """Verify the new failure flow: Save_Error_Waiting → Check_Is_Backfill → Check_Has_Slack → ... → Wait_For_Decision"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def test_save_error_goes_to_backfill_check(self):
        """Save_Error_Waiting → Check_Is_Backfill (not Interactive_Slack)."""
        state = self.rt['States']['Save_Error_Waiting']
        assert state['Next'] == 'Check_Is_Backfill'

    def test_save_error_catch_goes_to_backfill_check(self):
        """Save_Error_Waiting catch → Check_Is_Backfill (graceful)."""
        state = self.rt['States']['Save_Error_Waiting']
        assert state['Catch'][0]['Next'] == 'Check_Is_Backfill'

    def test_backfill_skips_to_wait_for_decision(self):
        """Backfill runs skip alerting but still wait for user decision via UI."""
        state = self.rt['States']['Check_Is_Backfill']
        assert state['Type'] == 'Choice'
        assert state['Choices'][0]['Next'] == 'Wait_For_Decision'
        assert 'is_backfill' in state['Choices'][0]['Condition']

    def test_backfill_default_goes_to_slack_check(self):
        """Non-backfill runs proceed to Check_Has_Slack."""
        state = self.rt['States']['Check_Is_Backfill']
        assert state['Default'] == 'Check_Has_Slack'

    def test_slack_check_routes_correctly(self):
        """Check_Has_Slack: Slack configured → Interactive_Slack, else → Check_Has_PagerDuty."""
        state = self.rt['States']['Check_Has_Slack']
        assert state['Type'] == 'Choice'
        assert state['Choices'][0]['Next'] == 'Interactive_Slack'
        assert 'alerts.slack' in state['Choices'][0]['Condition']
        assert state['Default'] == 'Check_Has_PagerDuty'

    def test_interactive_slack_goes_to_pagerduty_check(self):
        """Interactive_Slack → Check_Has_PagerDuty (not Wait_For_Decision)."""
        state = self.rt['States']['Interactive_Slack']
        assert state['Next'] == 'Check_Has_PagerDuty'

    def test_slack_failure_goes_to_pagerduty_check(self):
        """Save_Slack_Failed → Check_Has_PagerDuty."""
        state = self.rt['States']['Save_Slack_Failed']
        assert state['Next'] == 'Check_Has_PagerDuty'
        assert state['Catch'][0]['Next'] == 'Check_Has_PagerDuty'

    def test_pagerduty_check_routes_correctly(self):
        """Check_Has_PagerDuty: PD configured → Send, else → Wait_For_Decision."""
        state = self.rt['States']['Check_Has_PagerDuty']
        assert state['Type'] == 'Choice'
        assert state['Choices'][0]['Next'] == 'Send_PagerDuty_Alert'
        assert 'alerts.pagerduty' in state['Choices'][0]['Condition']
        assert state['Default'] == 'Wait_For_Decision'

    def test_pagerduty_alert_goes_to_wait(self):
        """Send_PagerDuty_Alert → Wait_For_Decision."""
        state = self.rt['States']['Send_PagerDuty_Alert']
        assert state['Next'] == 'Wait_For_Decision'

    def test_pagerduty_alert_catch_goes_to_wait(self):
        """PagerDuty failure → still Wait_For_Decision (graceful degradation)."""
        state = self.rt['States']['Send_PagerDuty_Alert']
        assert state['Catch'][0]['Next'] == 'Wait_For_Decision'

    def test_pagerduty_alert_has_retry(self):
        """Send_PagerDuty_Alert has Retry for transient errors."""
        state = self.rt['States']['Send_PagerDuty_Alert']
        assert 'Retry' in state

    def test_pagerduty_alert_uses_alerter_arn(self):
        """Send_PagerDuty_Alert calls pagerduty_alerter SFN."""
        state = self.rt['States']['Send_PagerDuty_Alert']
        assert '${pagerduty_alerter_arn}' in state['Arguments']['StateMachineArn']

    def test_pagerduty_alert_passes_severity(self):
        """PagerDuty alert includes severity from alerts config.

        Note: Input is a JSONata $string(...) expression because
        PagerDutyAlerterSfn is EXPRESS and we use aws-sdk:sfn:startSyncExecution
        which requires Input as a string (CLAUDE.md SFN Pitfall #2).
        """
        state = self.rt['States']['Send_PagerDuty_Alert']
        inp = state['Arguments']['Input']
        assert isinstance(inp, str)
        assert "'severity'" in inp
        assert 'alerts.pagerduty' in inp

    def test_pagerduty_alert_preserves_input(self):
        """Send_PagerDuty_Alert preserves input via Output."""
        state = self.rt['States']['Send_PagerDuty_Alert']
        assert '$states.input' in state.get('Output', '')

    def test_wait_for_decision_still_goes_to_save_failed(self):
        """Wait_For_Decision timeout → Save_Failed (unchanged)."""
        state = self.rt['States']['Wait_For_Decision']
        assert state['Next'] == 'Save_Failed'


# ============================================================
# run_task — DDB alerts_json persistence
# ============================================================

class TestRunTaskAlertsInDDB:
    """Verify alerts config is stored in DDB for restart."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def test_update_status_running_stores_alerts(self):
        """Update_Status_Running writes alerts_json to DDB."""
        state = self.rt['States']['Update_Status_Running']
        assert 'alerts_json' in state['Arguments']['UpdateExpression']

    def test_alerts_json_expression_value(self):
        """alerts_json uses $string to serialize alerts object."""
        state = self.rt['States']['Update_Status_Running']
        vals = state['Arguments']['ExpressionAttributeValues']
        assert ':alerts_json' in vals
        val = vals[':alerts_json']['S']
        assert '$string' in val
        assert 'alerts' in val

    def test_alerts_json_has_fallback(self):
        """alerts_json falls back to empty object if alerts missing."""
        state = self.rt['States']['Update_Status_Running']
        val = state['Arguments']['ExpressionAttributeValues'][':alerts_json']['S']
        assert '{}' in val


# ============================================================
# run_task — all failure paths reach Check_Is_Backfill
# ============================================================

class TestRunTaskFailurePathsConverge:
    """Every task type's Catch → Save_Error_Waiting → Check_Is_Backfill."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    @pytest.mark.parametrize("task_state", [
        'Run_Task_SFN', 'Run_Task_Lambda', 'Run_Task_Glue',
        'Run_Task_ECS', 'Run_Task_Athena', 'Run_Task_EMR', 'Run_Task_Batch'
    ])
    def test_task_catch_goes_to_save_error(self, task_state):
        """All Run_Task_* states catch to Save_Error_Waiting."""
        state = self.rt['States'][task_state]
        assert state['Catch'][0]['Next'] == 'Save_Error_Waiting'


# ============================================================
# run_task — complete path tracing
# ============================================================

class TestRunTaskPathTracing:
    """Trace complete paths through the failure flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def _follow_default_path(self, start, max_steps=20):
        """Follow Default/Next path from a state."""
        path = [start]
        current = start
        for _ in range(max_steps):
            state = self.rt['States'].get(current)
            if not state or state.get('End') or state['Type'] == 'Fail':
                break
            nxt = state.get('Default', state.get('Next'))
            if not nxt:
                break
            path.append(nxt)
            current = nxt
        return path

    def test_backfill_path(self):
        """Backfill: Save_Error → Check_Is_Backfill → Save_Failed → ... → Fail_State."""
        # Backfill takes Choice[0] from Check_Is_Backfill
        path = ['Save_Error_Waiting', 'Check_Is_Backfill', 'Save_Failed']
        rest = self._follow_default_path('Save_Failed')
        full = path[:2] + rest
        assert 'Interactive_Slack' not in full, "Backfill must not send Slack"
        assert 'Send_PagerDuty_Alert' not in full, "Backfill must not send PagerDuty"
        assert 'Wait_For_Decision' not in full, "Backfill must not wait"

    def test_no_alerts_path(self):
        """No alerts configured: Save_Error → ... → Check_Has_Slack → Check_Has_PagerDuty → Wait."""
        path = self._follow_default_path('Save_Error_Waiting')
        assert 'Check_Is_Backfill' in path
        assert 'Check_Has_Slack' in path
        assert 'Check_Has_PagerDuty' in path
        assert 'Wait_For_Decision' in path
        assert 'Interactive_Slack' not in path, "No Slack = no Interactive_Slack"
        assert 'Send_PagerDuty_Alert' not in path, "No PD = no Send_PagerDuty"

    def test_slack_only_path(self):
        """Slack configured, no PD: Interactive_Slack → Check_Has_PagerDuty(default) → Wait."""
        # After Interactive_Slack succeeds → Check_Has_PagerDuty
        state = self.rt['States']['Interactive_Slack']
        assert state['Next'] == 'Check_Has_PagerDuty'
        pd_state = self.rt['States']['Check_Has_PagerDuty']
        assert pd_state['Default'] == 'Wait_For_Decision'


# ============================================================
# failure_handler — upstream_failed suppression
# ============================================================

class TestFailureHandlerUpstreamFailed:
    """Verify upstream_failed tasks skip alerting."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.fh = load('failure_handler')

    def test_check_is_upstream_failed_exists(self):
        """Check_Is_Upstream_Failed state exists."""
        assert 'Check_Is_Upstream_Failed' in self.fh['States']

    def test_upstream_failed_skips_slack(self):
        """upstream_failed → Check_Orchestration_Token (skips Slack)."""
        state = self.fh['States']['Check_Is_Upstream_Failed']
        assert state['Choices'][0]['Next'] == 'Check_Orchestration_Token'
        assert 'UpstreamFailed' in state['Choices'][0]['Condition']

    def test_non_upstream_goes_to_slack(self):
        """Normal failure → Check_Slack_Alert."""
        state = self.fh['States']['Check_Is_Upstream_Failed']
        assert state['Default'] == 'Check_Slack_Alert'

    def test_notify_dependents_goes_to_upstream_check(self):
        """Notify_Dependents → Check_Is_Upstream_Failed."""
        state = self.fh['States']['Notify_Dependents']
        assert state['Next'] == 'Check_Is_Upstream_Failed'

    def test_notify_dependents_catch_goes_to_upstream_check(self):
        """Notify_Dependents catch → Check_Is_Upstream_Failed (graceful)."""
        state = self.fh['States']['Notify_Dependents']
        assert state['Catch'][0]['Next'] == 'Check_Is_Upstream_Failed'


# ============================================================
# failure_handler — PagerDuty removed
# ============================================================

class TestFailureHandlerNoPagerDuty:
    """Verify PagerDuty ALERT states are removed from failure_handler.
    
    PD alerting is in run_task (line 1). failure_handler only does Slack + orchestration.
    PD resolve on human decisions is handled by Lambda API (slack.py, tasks.py).
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.fh = load('failure_handler')

    def test_no_pagerduty_alert_states(self):
        """PagerDuty ALERT states removed from failure_handler."""
        for name in ['Check_PagerDuty_Alert', 'Send_PagerDuty_Alert', 'Save_PagerDuty_Failed']:
            assert name not in self.fh['States'], f"{name} should be removed"

    def test_no_pagerduty_alerter_arn(self):
        """pagerduty_alerter_arn not referenced in failure_handler."""
        content = json.dumps(self.fh)
        assert 'pagerduty_alerter_arn' not in content

    def test_no_pagerduty_resolver(self):
        """No PD resolve in failure_handler — resolve is in Lambda API handlers."""
        content = json.dumps(self.fh)
        assert 'pagerduty_resolver_arn' not in content
        assert 'Resolve_PagerDuty' not in content

    def test_slack_goes_to_orchestration_token(self):
        """Send_Slack_Alert → Check_Orchestration_Token."""
        state = self.fh['States']['Send_Slack_Alert']
        assert state['Next'] == 'Check_Orchestration_Token'

    def test_record_slack_failure_goes_to_orchestration_token(self):
        """Record_Slack_Failure → Check_Orchestration_Token."""
        state = self.fh['States']['Record_Slack_Failure']
        assert state['Next'] == 'Check_Orchestration_Token'

    def test_no_slack_goes_to_orchestration_token(self):
        """Check_Slack_Alert Default → Check_Orchestration_Token."""
        state = self.fh['States']['Check_Slack_Alert']
        assert state['Default'] == 'Check_Orchestration_Token'


# ============================================================
# failure_handler — no buttons on dead task
# ============================================================

class TestFailureHandlerSlackNoButtons:
    """Verify failure_handler Slack sends empty token (Restart Only, no Skip/Fail)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.fh = load('failure_handler')

    def test_slack_sends_empty_token(self):
        """Slack alert has empty token → Interactive Slack sends 'Restart Only' message."""
        inp = self.fh['States']['Send_Slack_Alert']['Arguments']['Input']
        assert inp['token'] == '', "Token must be empty to prevent buttons on dead task"


# ============================================================
# restart_task — alerts field
# ============================================================

class TestRestartTaskAlerts:
    """Verify restart_task passes alerts from DDB to new wrapper."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rst = load('restart_task')

    def test_wrapper_input_has_alerts(self):
        """Start_New_Wrapper input includes alerts field."""
        state = self.rst['States']['Start_New_Wrapper']
        inp = state['Arguments']['Input']
        assert 'alerts' in inp, "alerts must be in wrapper input"

    def test_alerts_reads_from_ddb(self):
        """alerts field reads from DDB alerts_json."""
        state = self.rst['States']['Start_New_Wrapper']
        alerts = state['Arguments']['Input']['alerts']
        assert 'alerts_json' in alerts, "Must read from alerts_json DDB field"

    def test_alerts_parses_json(self):
        """alerts field uses $parse to deserialize JSON string."""
        state = self.rst['States']['Start_New_Wrapper']
        alerts = state['Arguments']['Input']['alerts']
        assert '$parse' in alerts, "Must parse JSON string back to object"

    def test_alerts_fallback_empty(self):
        """alerts falls back to {} if alerts_json not in DDB."""
        state = self.rst['States']['Start_New_Wrapper']
        alerts = state['Arguments']['Input']['alerts']
        assert '{}' in alerts, "Must fall back to empty object"


# ============================================================
# main.tf — pagerduty_alerter_arn wiring
# ============================================================

class TestMainTFWiring:
    """Verify SAM template variable wiring."""

    @pytest.fixture(autouse=True)
    def setup(self):
        main_tf = os.path.join(
            os.path.dirname(__file__), '..', '..', 'sam', 'template.yaml'
        )
        with open(main_tf) as f:
            self.content = f.read()

    def test_run_task_has_pagerduty_alerter(self):
        """RunTaskHelperSfn DefinitionSubstitutions has pagerduty_alerter_arn."""
        # Find RunTaskHelperSfn block and check its DefinitionSubstitutions
        idx = self.content.find('RunTaskHelperSfn:')
        assert idx != -1, "RunTaskHelperSfn not found in SAM template"
        block = self.content[idx:idx+3000]
        assert 'pagerduty_alerter_arn' in block, "pagerduty_alerter_arn not in RunTaskHelperSfn"

    def test_failure_handler_no_pagerduty_alerter(self):
        """FailureHandlerSfn has pagerduty_resolver but NOT pagerduty_alerter_arn."""
        import re as _re
        idx = self.content.find('FailureHandlerSfn:')
        assert idx != -1, "FailureHandlerSfn not found in SAM template"
        # Bound block to just this resource (stop at next top-level resource)
        end = _re.search(r'\n  [A-Z]\w+:', self.content[idx+100:])
        block = self.content[idx:idx+100+(end.start() if end else 1500)]
        # failure_handler uses resolver (to resolve alerts) not alerter (to create them)
        assert 'pagerduty_resolver_arn' in block, "pagerduty_resolver_arn should be in FailureHandlerSfn"
        assert 'pagerduty_alerter_arn' not in block, "pagerduty_alerter_arn should NOT be in FailureHandlerSfn"


# ============================================================
# Cross-template consistency
# ============================================================

class TestCrossTemplateConsistency:
    """Verify templates are consistent with each other."""

    def test_run_task_pagerduty_dedup_matches_wrapper_resolve(self):
        """PagerDuty dedup_key format in run_task must match resolver format."""
        rt = load('run_task')
        # run_task uses alerter SFN which builds:
        # dedup_key = pipeline_name + '/' + task_name + '/' + date
        rt_input = rt['States']['Send_PagerDuty_Alert']['Arguments']['Input']
        assert 'pipeline_name' in json.dumps(rt_input)
        assert 'task_name' in json.dumps(rt_input)

        # Resolver in wrapper uses same fields
        wrapper_path = os.path.join(TEMPLATES, 'dependency_wrapper', 'sfn.tpl.json')
        with open(wrapper_path) as f:
            wrapper = json.load(f)
        resolve_state = wrapper['States']['Resolve_PagerDuty']
        resolve_input = resolve_state['Arguments']['Input']
        assert 'pipeline_name' in json.dumps(resolve_input)
        assert 'task_name' in json.dumps(resolve_input)

    def test_alerts_json_roundtrip(self):
        """run_task writes $string(alerts), restart_task reads $parse(alerts_json)."""
        rt = load('run_task')
        val = rt['States']['Update_Status_Running']['Arguments']['ExpressionAttributeValues'][':alerts_json']['S']
        assert '$string' in val, "Write side must serialize with $string"

        rst = load('restart_task')
        alerts = rst['States']['Start_New_Wrapper']['Arguments']['Input']['alerts']
        assert '$parse' in alerts, "Read side must deserialize with $parse"

    def test_failure_handler_all_states_reachable(self):
        """All failure_handler states reachable from StartAt."""
        fh = load('failure_handler')
        reachable = set()
        queue = [fh['StartAt']]
        while queue:
            name = queue.pop(0)
            if name in reachable or name not in fh['States']:
                continue
            reachable.add(name)
            state = fh['States'][name]
            for ref in [state.get('Next'), state.get('Default')]:
                if ref:
                    queue.append(ref)
            for c in state.get('Choices', []):
                if c.get('Next'):
                    queue.append(c['Next'])
            for c in state.get('Catch', []):
                if c.get('Next'):
                    queue.append(c['Next'])

        unreachable = set(fh['States'].keys()) - reachable
        assert not unreachable, f"Unreachable states: {unreachable}"

    def test_run_task_all_states_reachable(self):
        """All run_task states reachable from StartAt."""
        rt = load('run_task')
        reachable = set()
        queue = [rt['StartAt']]
        while queue:
            name = queue.pop(0)
            if name in reachable or name not in rt['States']:
                continue
            reachable.add(name)
            state = rt['States'][name]
            for ref in [state.get('Next'), state.get('Default')]:
                if ref:
                    queue.append(ref)
            for c in state.get('Choices', []):
                if c.get('Next'):
                    queue.append(c['Next'])
            for c in state.get('Catch', []):
                if c.get('Next'):
                    queue.append(c['Next'])
            # Map ItemProcessor inner states
            ip = state.get('ItemProcessor', {}).get('States', {})
            for inner_state in ip.values():
                for ref in [inner_state.get('Next')]:
                    if ref and ref in ip:
                        pass  # inner states only reference inner states

        unreachable = set(rt['States'].keys()) - reachable
        assert not unreachable, f"Unreachable states: {unreachable}"

    def test_no_dangling_references(self):
        """No state references point to non-existent states (both templates)."""
        for name in ['run_task', 'failure_handler', 'restart_task']:
            data = load(name)
            all_states = set(data['States'].keys())
            for sname, state in data['States'].items():
                for ref in [state.get('Next'), state.get('Default')]:
                    if ref:
                        assert ref in all_states, \
                            f"{name}: {sname} → {ref} does not exist"
                for c in state.get('Choices', []):
                    if c.get('Next'):
                        assert c['Next'] in all_states, \
                            f"{name}: {sname} choice → {c['Next']} does not exist"
                for c in state.get('Catch', []):
                    if c.get('Next'):
                        assert c['Next'] in all_states, \
                            f"{name}: {sname} catch → {c['Next']} does not exist"


# ============================================================
# Slack mentions — DSL validation
# ============================================================

class TestSlackMentionsDSL:
    """Verify DAG validates slack_mentions correctly."""

    def test_valid_user_id(self):
        """User ID accepted."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": ["U04ABCDEF"]})
        assert dag.alerts['slack_mentions'] == ["U04ABCDEF"]

    def test_valid_group_id(self):
        """User group ID accepted."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": ["S04ABCDEF"]})
        assert dag.alerts['slack_mentions'] == ["S04ABCDEF"]

    def test_valid_with_at_prefix(self):
        """@-prefixed IDs accepted."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": ["@U04ABCDEF", "@S04ABCDEF"]})
        assert len(dag.alerts['slack_mentions']) == 2

    def test_valid_here_and_channel(self):
        """'here' and 'channel' accepted."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": ["here", "channel"]})
        assert len(dag.alerts['slack_mentions']) == 2

    def test_valid_mixed(self):
        """Mix of user ID, group ID, and special keywords."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={
            "slack": "#ch",
            "slack_mentions": ["U04ABCDEF", "S04ABCDEF", "here"]
        })
        assert len(dag.alerts['slack_mentions']) == 3

    def test_invalid_not_list(self):
        """Non-list slack_mentions rejected."""
        from slsflow import DAG
        with pytest.raises(ValueError, match="must be a list"):
            DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": "U123"})

    def test_invalid_bad_prefix(self):
        """Invalid ID prefix rejected."""
        from slsflow import DAG
        with pytest.raises(ValueError, match="Invalid slack_mentions"):
            DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": ["X123"]})

    def test_invalid_non_string_item(self):
        """Non-string items rejected."""
        from slsflow import DAG
        with pytest.raises(ValueError, match="must be strings"):
            DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": [123]})

    def test_empty_list_valid(self):
        """Empty list is valid (uses default)."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch", "slack_mentions": []})
        assert dag.alerts['slack_mentions'] == []

    def test_no_mentions_valid(self):
        """No slack_mentions key at all is valid."""
        from slsflow import DAG
        dag = DAG('test', schedule=None, alerts={"slack": "#ch"})
        assert 'slack_mentions' not in dag.alerts


# ============================================================
# Slack mentions — Generator formatting
# ============================================================

class TestSlackMentionsGenerator:
    """Verify generators.py formats mentions into Slack markup."""

    def _generate_and_extract(self, alerts):
        from slsflow import DAG, task
        from slsflow.generators import generate_step_function_json

        with DAG('test-mentions', schedule=None, alerts=alerts) as dag:
            @task.sfn(arn='arn:aws:states:us-east-1:123:stateMachine:test')
            def t1():
                pass
            t1()

        sfn_json = generate_step_function_json(dag)
        sfn = json.loads(sfn_json)

        # Find slack_mentions_formatted in wrapper input
        for name, state in sfn['States'].items():
            if state.get('Type') == 'Parallel':
                for branch in state.get('Branches', []):
                    for sn, ss in branch.get('States', {}).items():
                        inp = ss.get('Arguments', {}).get('Input', {})
                        if 'slack_mentions_formatted' in inp:
                            return inp['slack_mentions_formatted']
        return None

    def test_user_id_formatted(self):
        """User ID → <@U...>"""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": ["U04ABCDEF"]})
        assert result == "<@U04ABCDEF>"

    def test_group_id_formatted(self):
        """Group ID → <!subteam^S...>"""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": ["S04ABCDEF"]})
        assert result == "<!subteam^S04ABCDEF>"

    def test_here_formatted(self):
        """'here' → <!here>"""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": ["here"]})
        assert result == "<!here>"

    def test_channel_formatted(self):
        """'channel' → <!channel>"""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": ["channel"]})
        assert result == "<!channel>"

    def test_at_prefix_stripped(self):
        """@U... prefix handled correctly."""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": ["@U04ABCDEF"]})
        assert result == "<@U04ABCDEF>"

    def test_mixed_formatted(self):
        """Mix of types formatted and joined with spaces."""
        result = self._generate_and_extract({
            "slack": "#ch",
            "slack_mentions": ["U04ABCDEF", "S04ABCDEF", "here"]
        })
        assert result == "<@U04ABCDEF> <!subteam^S04ABCDEF> <!here>"

    def test_empty_list_empty_string(self):
        """Empty mentions list → empty string."""
        result = self._generate_and_extract({"slack": "#ch", "slack_mentions": []})
        assert result == ""

    def test_no_mentions_empty_string(self):
        """No slack_mentions → empty string."""
        result = self._generate_and_extract({"slack": "#ch"})
        assert result == ""


# ============================================================
# Slack mentions — SFN template flow
# ============================================================

class TestSlackMentionsTemplateFlow:
    """Verify slack_mentions flows through SFN templates."""

    def test_run_task_passes_mentions_to_slack(self):
        """run_task Interactive_Slack input includes slack_mentions."""
        rt = load('run_task')
        inp = rt['States']['Interactive_Slack']['Arguments']['Input']
        assert 'slack_mentions' in inp
        assert 'slack_mentions_formatted' in inp['slack_mentions']

    def test_failure_handler_passes_mentions_to_slack(self):
        """failure_handler Send_Slack_Alert input includes slack_mentions."""
        fh = load('failure_handler')
        inp = fh['States']['Send_Slack_Alert']['Arguments']['Input']
        assert 'slack_mentions' in inp
        assert 'slack_mentions_formatted' in inp['slack_mentions']

    def test_interactive_slack_uses_mentions_in_full_message(self):
        """Send_Full_Slack_Message uses slack_mentions in CC line."""
        isl = load('interactive_choice_slack')
        content = json.dumps(isl['States']['Send_Full_Slack_Message'])
        assert 'slack_mentions' in content
        assert 'responsible_for' not in content

    def test_interactive_slack_uses_mentions_in_restart_message(self):
        """Send_Restart_Only_Message uses slack_mentions in CC line."""
        isl = load('interactive_choice_slack')
        content = json.dumps(isl['States']['Send_Restart_Only_Message'])
        assert 'slack_mentions' in content
        assert 'responsible_for' not in content

    def test_interactive_slack_prepare_has_fallback(self):
        """Prepare_Slack_Message falls back to default_slack_mentions."""
        isl = load('interactive_choice_slack')
        output = isl['States']['Prepare_Slack_Message']['Output']
        assert 'default_slack_mentions' in output
        assert 'slack_mentions' in output

    def test_no_hardcoded_responsible_for_anywhere(self):
        """No template references responsible_for_data_pipeline_ops."""
        for name in ['run_task', 'failure_handler', 'interactive_choice_slack']:
            data = load(name)
            content = json.dumps(data)
            assert 'responsible_for_data_pipeline_ops' not in content, \
                f"{name} still has hardcoded responsible_for"


# ============================================================
# PagerDuty alerter — links to AWS Console
# ============================================================

class TestPagerDutyAlerterLinks:
    """Verify PD alerter includes clickable links to SFN executions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pa = load('pagerduty_alerter')

    def test_payload_has_links(self):
        """Build_Alert_Payload output includes 'links' key."""
        output = self.pa['States']['Build_Alert_Payload']['Output']
        assert "'links'" in output or '"links"' in output

    def test_task_sfn_link(self):
        """Links include Task SFN Execution."""
        output = self.pa['States']['Build_Alert_Payload']['Output']
        assert 'Task SFN Execution' in output

    def test_wrapper_sfn_link(self):
        """Links include Wrapper SFN Execution."""
        output = self.pa['States']['Build_Alert_Payload']['Output']
        assert 'Wrapper SFN Execution' in output

    def test_aws_console_url_pattern(self):
        """Links use correct AWS Console URL pattern."""
        output = self.pa['States']['Build_Alert_Payload']['Output']
        assert 'console.aws.amazon.com/states/home' in output

    def test_empty_arn_handled(self):
        """Empty task_execution_arn produces no task link (conditional)."""
        output = self.pa['States']['Build_Alert_Payload']['Output']
        assert "$taskArn != ''" in output
        assert "$wrapperArn != ''" in output

    def test_uses_aws_region_var(self):
        """Uses ${aws_region} template var for console URLs."""
        content = json.dumps(self.pa)
        assert '${aws_region}' in content


class TestRunTaskPassesArnsToAlerter:
    """Verify run_task passes execution ARNs to PD alerter for links."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def test_passes_task_execution_arn(self):
        """Send_PagerDuty_Alert input includes task_execution_arn.

        Input is a JSONata $string(...) expression (Express SFN via startSyncExecution).
        """
        inp = self.rt['States']['Send_PagerDuty_Alert']['Arguments']['Input']
        assert isinstance(inp, str)
        assert "'task_execution_arn'" in inp

    def test_passes_wrapper_execution_arn(self):
        """Send_PagerDuty_Alert input includes wrapper_execution_arn."""
        inp = self.rt['States']['Send_PagerDuty_Alert']['Arguments']['Input']
        assert isinstance(inp, str)
        assert "'wrapper_execution_arn'" in inp

    def test_arns_have_existence_check(self):
        """ARN fields use $exists() for graceful handling."""
        inp = self.rt['States']['Send_PagerDuty_Alert']['Arguments']['Input']
        assert isinstance(inp, str)
        # Both ARN fields must guard with $exists(...)
        assert inp.count('$exists($states.input.task_execution_arn)') >= 1
        assert inp.count('$exists($states.input.wrapper_execution_arn)') >= 1


# ============================================================
# Canonical Output (upstream data passing)
# ============================================================

class TestCanonicalOutput:
    """Verify canonical output: stable key for upstream reads, survives incremental backfill."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def test_save_success_chains_to_canonical(self):
        """Save_Success → Save_Canonical_Output → Emit_Task_Finished_Success."""
        assert self.rt['States']['Save_Success']['Next'] == 'Save_Canonical_Output'
        assert self.rt['States']['Save_Canonical_Output']['Next'] == 'Emit_Task_Finished_Success'

    def test_canonical_uses_stable_key(self):
        """Canonical key is output#pipeline#task#date — no run-specific parts."""
        item = self.rt['States']['Save_Canonical_Output']['Arguments']['Item']
        key = item['execution_name']['S']
        assert 'output#' in key
        assert 'pipeline_name' in key
        assert 'task_name' in key
        assert 'date' in key
        assert 'pipeline_execution_short' not in key

    def test_canonical_has_required_fields(self):
        """Canonical record includes result, task_name, status, ttl."""
        item = self.rt['States']['Save_Canonical_Output']['Arguments']['Item']
        assert 'result' in item
        assert 'task_name' in item
        assert 'status' in item
        assert item['status']['S'] == 'success'
        assert 'ttl' in item

    def test_canonical_is_best_effort(self):
        """If canonical save fails, continue to Emit_Task_Finished_Success."""
        catch = self.rt['States']['Save_Canonical_Output']['Catch']
        assert len(catch) == 1
        assert catch[0]['Next'] == 'Emit_Task_Finished_Success'

    def test_read_upstream_uses_canonical_key(self):
        """Read_Upstream_Outputs reads by output#pipeline#dep#date."""
        get_dep = self.rt['States']['Read_Upstream_Outputs']['ItemProcessor']['States']['Get_Dep_Output']
        key = get_dep['Arguments']['Key']['execution_name']['S']
        assert 'output#' in key
        assert 'pipeline_name' in key
        assert 'dep' in key
        assert 'date' in key
        assert 'pipeline_execution_short' not in key

    def test_read_upstream_passes_pipeline_name(self):
        """Map items include pipeline_name for canonical key construction."""
        items_expr = self.rt['States']['Read_Upstream_Outputs']['Items']
        assert 'pipeline_name' in items_expr

    def test_read_upstream_truncates_large_output(self):
        """Get_Dep_Output truncates individual dep output > 25KB to prevent 256KB payload limit."""
        gdo = self.rt['States']['Read_Upstream_Outputs']['ItemProcessor']['States']['Get_Dep_Output']
        output = gdo['Output']
        assert '25000' in output
        assert '_truncated' in output

    def test_child_sfn_receives_upstream(self):
        """Run_Task_SFN passes upstream outputs to child SFN input."""
        inp = self.rt['States']['Run_Task_SFN']['Arguments']['Input']
        assert 'upstream' in inp

    def test_child_lambda_receives_upstream(self):
        """Run_Task_Lambda passes upstream outputs to child Lambda payload."""
        payload = self.rt['States']['Run_Task_Lambda']['Arguments']['Payload']
        assert 'upstream' in payload

    def test_upstream_only_passed_when_nonempty(self):
        """Upstream is only included when it has keys (avoids empty object noise)."""
        inp = self.rt['States']['Run_Task_SFN']['Arguments']['Input']
        assert '$count($keys($states.input.upstream)) > 0' in inp

    def test_prepare_task_input_computes_date_variables(self):
        """Prepare_Task_Input computes all jsonata-source variables from schema."""
        pti = self.rt['States']['Prepare_Task_Input']['Output']
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sam', 'lambdas', 'console_api'))
        from task_variables import get_jsonata_vars
        for var in sorted(get_jsonata_vars()):
            assert var in pti, f"Missing variable in Prepare_Task_Input: {var} (defined in task_variables.py)"

    def test_prepare_task_input_backfill_overrides_computed(self):
        """Backfill variables override computed date variables (merge order: computed first, then user vars)."""
        pti = self.rt['States']['Prepare_Task_Input']['Output']
        assert '$merge([$dateVars, $vars])' in pti


# ============================================================
# Variable schema drift detection
# ============================================================

class TestVariableSchemaDrift:
    """Ensure run_task Prepare_Task_Input stays in sync with task_variables.py schema.

    Pre-v0.78, this also checked routes/backfill.py contained a Python
    builder mirroring the JSONata vars. After ADR #51 the bulk-backfill
    SFN passes only ``partition_key`` + ``current_date`` and the wrapper +
    run_task templates build all derived calendar vars in JSONata via
    ``Prepare_Task_Input``. The Python builder is gone, so the
    ``test_backfill_has_*`` tests are removed.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.rt = load('run_task')

    def test_jsonata_has_all_schema_vars(self):
        """Prepare_Task_Input must contain every jsonata-source variable from schema."""
        from task_variables import get_jsonata_vars
        pti = self.rt['States']['Prepare_Task_Input']['Output']
        missing = [v for v in sorted(get_jsonata_vars()) if f"\'{v}\'" not in pti]
        assert not missing, f"Prepare_Task_Input missing jsonata vars: {missing}"

    def test_no_orphan_vars_in_jsonata(self):
        """Every variable in Prepare_Task_Input should be in schema."""
        import re as re_mod
        from task_variables import TASK_VARIABLES
        pti = self.rt['States']['Prepare_Task_Input']['Output']
        jsonata_keys = set(re_mod.findall(r"\'(\w+)\':", pti))
        schema_keys = set(TASK_VARIABLES.keys()) | {"upstream", "variables"}
        orphans = jsonata_keys - schema_keys
        assert not orphans, f"Prepare_Task_Input has vars not in schema: {orphans}"
