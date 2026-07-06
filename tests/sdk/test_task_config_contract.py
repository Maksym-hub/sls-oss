"""Contract: task_config keys are shared constants (CLAUDE.md #13).

The SDK writer (generators._build_task_branch / step wrapper path) and the
run_task wrapper template are two sides of one contract. The keys live once in
polyris.constants.TaskConfigKey; these tests pin that:
  1. every `task_config.<key>` the template reads is a declared constant,
  2. every key the writer produces (per task type, all params set) is exactly
     the constants-derived set — a literal-string key on either side fails here.

This is the structural fix for the ADR #106 class of bug (emr Step drift).
"""
import re
from datetime import timedelta
from pathlib import Path

from polyris.constants import TaskConfigKey

TEMPLATE = Path(__file__).parents[2] / "sam/sfn_templates/helpers/run_task/sfn.tpl.json"

ALL_KEYS = {k.value for k in TaskConfigKey}


def _wrapper_input_for(build):
    """Build a one-task DAG via the real SDK and return the wrapper Input
    (same proven pattern as tests/sdk/test_run_task_template.py)."""
    from polyris import DAG
    from polyris.generators import _build_task_branch

    with DAG(dag_id="contract_dag", schedule="@daily") as dag:
        build(dag)
    t = dag.tasks[0]
    branch = _build_task_branch(
        t, dag, "arn:aws:states:us-east-1:000000000000:stateMachine:run-task"
    )
    state = next(iter(branch["States"].values()))
    return state["Arguments"]["Input"]


class TestTemplateReadsOnlyDeclaredKeys:
    def test_every_template_task_config_ref_is_a_constant(self):
        """Reader side: each task_config.<key> in the wrapper template must be
        declared in TaskConfigKey — a template-only key is contract drift."""
        text = TEMPLATE.read_text()
        refs = set(re.findall(r"task_config\.([a-zA-Z_][a-zA-Z0-9_]*)", text))
        assert refs, "template should reference task_config keys"
        unknown = refs - ALL_KEYS
        assert not unknown, f"template reads undeclared task_config keys: {sorted(unknown)}"


class TestWriterProducesOnlyDeclaredKeys:
    """Writer side: per task type with ALL params set, the produced task_config
    keys must equal the constants-derived expectation."""

    RETRY = {k.value for k in (
        TaskConfigKey.RETRIES, TaskConfigKey.RETRY_DELAY, TaskConfigKey.RETRY_BACKOFF,
        TaskConfigKey.MAX_RETRY_DELAY, TaskConfigKey.RETRY_JITTER,
    )}
    COMMON = dict(retries=2, retry_delay=timedelta(seconds=10),
                  retry_exponential_backoff=True, max_retry_delay=timedelta(seconds=60),
                  retry_jitter=True)

    def _keys(self, build):
        return set(_wrapper_input_for(build)["task_config"].keys())

    def test_lambda(self):
        from polyris import task

        def build(dag):
            @task.lambda_(function_name="fn", payload={"k": "v"}, **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.FUNCTION_NAME.value, TaskConfigKey.PAYLOAD.value} | self.RETRY
        assert self._keys(build) == expected

    def test_glue(self):
        from polyris import task

        def build(dag):
            @task.glue(job_name="j", glue_arguments={"--a": "1"}, worker_type="G.1X",
                       number_of_workers=2, **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.JOB_NAME.value, TaskConfigKey.ARGUMENTS.value,
                    TaskConfigKey.WORKER_TYPE.value, TaskConfigKey.NUMBER_OF_WORKERS.value} | self.RETRY
        assert self._keys(build) == expected

    def test_ecs(self):
        from polyris import task

        def build(dag):
            @task.ecs(cluster="c", task_definition="td", launch_type="FARGATE",
                      subnets=["s-1"], security_groups=["sg-1"], assign_public_ip="ENABLED",
                      container_overrides={"o": 1}, **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.CLUSTER.value, TaskConfigKey.TASK_DEFINITION.value,
                    TaskConfigKey.LAUNCH_TYPE.value, TaskConfigKey.SUBNETS.value,
                    TaskConfigKey.SECURITY_GROUPS.value, TaskConfigKey.ASSIGN_PUBLIC_IP.value,
                    TaskConfigKey.OVERRIDES.value} | self.RETRY
        assert self._keys(build) == expected

    def test_athena(self):
        from polyris import task

        def build(dag):
            @task.athena(query_string="SELECT 1", database="db",
                         output_location="s3://b/", workgroup="wg", **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.QUERY_STRING.value, TaskConfigKey.DATABASE.value,
                    TaskConfigKey.OUTPUT_LOCATION.value, TaskConfigKey.WORKGROUP.value} | self.RETRY
        assert self._keys(build) == expected

    def test_emr(self):
        from polyris import task

        def build(dag):
            @task.emr(emr_cluster_id="j-1", emr_step={"Name": "s", "HadoopJarStep": {"Jar": "x.jar"}},
                      **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.CLUSTER_ID.value, TaskConfigKey.STEP.value} | self.RETRY
        assert self._keys(build) == expected

    def test_batch(self):
        from polyris import task

        def build(dag):
            @task.batch(job_definition="jd", job_queue="jq", batch_parameters={"p": "1"},
                        **self.COMMON)
            def t():
                pass
        expected = {TaskConfigKey.JOB_DEFINITION.value, TaskConfigKey.JOB_QUEUE.value,
                    TaskConfigKey.PARAMETERS.value} | self.RETRY
        assert self._keys(build) == expected

    def test_sfn_stays_empty(self):
        """The sfn contract is deliberately empty (ADR #106) — pin it."""
        from polyris import task

        def build(dag):
            @task.sfn(arn="arn:aws:states:us-east-1:1:stateMachine:x")
            def t():
                pass
        assert "task_config" not in _wrapper_input_for(build)


class TestNoLiteralKeysInWriter:
    def test_generators_uses_constants_not_literals(self):
        """Source guard: the two task_config builder regions in generators.py
        must key their dicts via TaskConfigKey, not bare string literals."""
        src = Path(__file__).parents[2].joinpath("polyris/generators.py").read_text()
        # every `task_config[...] =` write must index with TaskConfigKey
        bad_writes = re.findall(r'task_config\[\s*"', src)
        assert not bad_writes, "task_config[\"...\"] literal writes remain in generators.py"
