"""Step-state generation tests — the per-service ASL builders.

Constructs each ``Step`` subclass from ``polyris.steps`` and runs it through
``_generate_step_state`` (the dispatcher in ``polyris.generators``), asserting
the emitted ASL ``Resource`` and key ``Arguments``. This covers two modules at
once (CLAUDE.md #13): the Step dataclasses' construction/post-init and every
``_gen_<type>_state`` builder — including the service integrations that have no
public ``@task`` decorator (sns / sqs / s3 / dynamodb / eventbridge / bedrock /
http).
"""
from __future__ import annotations

from polyris.steps import (
    Step,
    Wait,
    Pass,
    Succeed,
    LambdaTask,
    DynamoDBTask,
    SNSTask,
    SQSTask,
    S3Task,
    GlueTask,
    AthenaTask,
    ECSTask,
    EventBridgeTask,
    BedrockTask,
    HttpTask,
)
from polyris.generators import _generate_step_state


# ============================================================ #
# control-flow states
# ============================================================ #
class TestControlFlowStates:
    def test_wait_seconds(self):
        s = _generate_step_state(Wait(seconds=20))
        assert s == {"Type": "Wait", "Seconds": 20}

    def test_wait_timestamp(self):
        s = _generate_step_state(Wait(timestamp="2024-01-01T09:00:00Z"))
        assert s["Type"] == "Wait"
        assert s["Timestamp"] == "2024-01-01T09:00:00Z"

    def test_wait_timestamp_path(self):
        s = _generate_step_state(Wait(timestamp_path="$.scheduled_time"))
        assert s["TimestampPath"] == "$.scheduled_time"

    def test_pass_with_output(self):
        s = _generate_step_state(Pass(output={"k": "v"}))
        assert s["Type"] == "Pass"
        assert s["Output"] == {"k": "v"}

    def test_pass_bare(self):
        assert _generate_step_state(Pass()) == {"Type": "Pass"}

    def test_succeed(self):
        assert _generate_step_state(Succeed())["Type"] == "Succeed"

    def test_unknown_step_type_falls_back_to_pass(self):
        assert _generate_step_state(Step(step_id="x", step_type="mystery")) == {"Type": "Pass"}


# ============================================================ #
# service-task states
# ============================================================ #
class TestServiceStates:
    def test_lambda(self):
        s = _generate_step_state(LambdaTask(function_arn="arn:aws:lambda:us-east-1:1:function:fn"))
        assert s["Resource"] == "arn:aws:states:::lambda:invoke"
        assert s["Arguments"]["FunctionName"].endswith(":fn")
        assert "Retry" not in s

    def test_lambda_with_retries_adds_retry(self):
        s = _generate_step_state(LambdaTask(function_arn="arn:fn", retries=3, retry_interval=5))
        assert s["Retry"][0]["MaxAttempts"] == 3

    def test_dynamodb_put(self):
        s = _generate_step_state(DynamoDBTask(operation="put_item", table_name="T", item={"id": {"S": "1"}}))
        assert s["Resource"] == "arn:aws:states:::dynamodb:putItem"
        assert s["Arguments"]["TableName"] == "T"
        assert s["Arguments"]["Item"] == {"id": {"S": "1"}}

    def test_dynamodb_query(self):
        s = _generate_step_state(DynamoDBTask(operation="query", table_name="T", key_condition="id = :v"))
        assert s["Resource"] == "arn:aws:states:::aws-sdk:dynamodb:query"
        assert s["Arguments"]["KeyConditionExpression"] == "id = :v"

    def test_sns(self):
        s = _generate_step_state(SNSTask(topic_arn="arn:topic", message="hi", subject="subj"))
        assert s["Resource"] == "arn:aws:states:::sns:publish"
        assert s["Arguments"]["TopicArn"] == "arn:topic"
        assert s["Arguments"]["Subject"] == "subj"

    def test_sqs(self):
        s = _generate_step_state(SQSTask(queue_url="https://q", message_body="body", delay_seconds=5))
        assert s["Resource"] == "arn:aws:states:::sqs:sendMessage"
        assert s["Arguments"]["QueueUrl"] == "https://q"
        assert s["Arguments"]["DelaySeconds"] == 5

    def test_s3_put(self):
        s = _generate_step_state(S3Task(operation="put_object", bucket="b", key="k", body="data"))
        assert s["Resource"] == "arn:aws:states:::aws-sdk:s3:putObject"
        assert s["Arguments"]["Bucket"] == "b"
        assert s["Arguments"]["Body"] == "data"

    def test_s3_unknown_operation_defaults_to_get(self):
        s = _generate_step_state(S3Task(operation="frobnicate", bucket="b", key="k"))
        assert s["Resource"] == "arn:aws:states:::aws-sdk:s3:getObject"

    def test_glue_async_when_no_wait(self):
        s = _generate_step_state(GlueTask(job_name="job", wait_for_completion=False))
        assert s["Resource"] == "arn:aws:states:::glue:startJobRun"
        assert s["Arguments"]["JobName"] == "job"

    def test_glue_sync_is_default(self):
        # wait_for_completion defaults to True → .sync variant.
        s = _generate_step_state(GlueTask(job_name="job"))
        assert s["Resource"] == "arn:aws:states:::glue:startJobRun.sync"

    def test_athena(self):
        # Default waits for completion → .sync.
        s = _generate_step_state(AthenaTask(query_string="SELECT 1", database="db"))
        assert s["Resource"] == "arn:aws:states:::athena:startQueryExecution.sync"
        assert s["Arguments"]["QueryString"] == "SELECT 1"
        assert s["Arguments"]["QueryExecutionContext"]["Database"] == "db"

    def test_ecs_fargate_networking(self):
        s = _generate_step_state(ECSTask(
            cluster="c", task_definition="td", launch_type="FARGATE", subnets=["subnet-1"],
        ))
        # Default waits for completion → .sync.
        assert s["Resource"] == "arn:aws:states:::ecs:runTask.sync"
        net = s["Arguments"]["NetworkConfiguration"]["AwsvpcConfiguration"]
        assert net["Subnets"] == ["subnet-1"]

    def test_ecs_async_when_no_wait(self):
        s = _generate_step_state(ECSTask(cluster="c", task_definition="td", wait_for_completion=False))
        assert s["Resource"] == "arn:aws:states:::ecs:runTask"

    def test_eventbridge(self):
        s = _generate_step_state(EventBridgeTask(
            event_bus="default", source="my.app", detail_type="OrderPlaced", detail="{}",
        ))
        assert s["Resource"] == "arn:aws:states:::events:putEvents"
        entry = s["Arguments"]["Entries"][0]
        assert entry["Source"] == "my.app"
        assert entry["DetailType"] == "OrderPlaced"

    def test_bedrock(self):
        s = _generate_step_state(BedrockTask(
            model_id="anthropic.claude", body={"prompt": "hi"},
            content_type="application/json", accept="application/json",
        ))
        assert s["Resource"] == "arn:aws:states:::bedrock:invokeModel"
        assert s["Arguments"]["ModelId"] == "anthropic.claude"

    def test_http(self):
        s = _generate_step_state(HttpTask(
            url="https://api.example.com", method="POST",
            headers={"X-Key": "1"}, connection_arn="arn:conn",
        ))
        assert s["Resource"] == "arn:aws:states:::http:invoke"
        assert s["Arguments"]["ApiEndpoint"] == "https://api.example.com"
        assert s["Arguments"]["Method"] == "POST"
        assert s["Arguments"]["Authentication"]["ConnectionArn"] == "arn:conn"
