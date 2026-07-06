"""Multi-service pipeline — one of every task type.

polyris speaks to several AWS services from the same DAG: nested Step Functions
(`sfn`), Lambda, Glue, Athena, ECS/Fargate, EMR, and Batch. This pipeline wires
one of each so you can see how they compile side by side. It also shows
`default_args` (shared retry/timeout defaults for every task) and a cross-account
`role`.

Run it locally (no AWS):  polyris-validate -v
"""
from datetime import timedelta

from polyris import DAG, task

ACCOUNT = "000000000000"
REGION = "us-east-1"

with DAG(
    dag_id="multi-service-etl",
    schedule="cron(0 3 * * ? *)",           # 03:00 UTC daily
    description="One task per AWS service — a tour of the task types.",
    tags=["example", "reference", "multi-service"],
    doc_md="Reference pipeline exercising every polyris task type.",
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(hours=1),
        "orchestration_timeout": timedelta(hours=6),
    },
) as dag:

    @task.lambda_(function_name="ingest-raw-events")
    def ingest():
        """Kick off ingestion via a Lambda."""
        pass

    @task.glue(
        job_name="raw-to-bronze",
        glue_arguments={"--source": "events"},
        worker_type="G.1X",
        number_of_workers=5,
    )
    def to_bronze():
        """Glue job: raw → bronze."""
        pass

    @task.athena(
        query_string="INSERT INTO silver.events SELECT * FROM bronze.events",
        database="analytics",
        output_location=f"s3://{ACCOUNT}-athena-results/multi-service/",
    )
    def to_silver():
        """Athena CTAS/INSERT: bronze → silver."""
        pass

    @task.ecs(
        cluster="batch-jobs",
        task_definition="feature-builder:12",
        launch_type="FARGATE",
        subnets=["subnet-0aaa1111bbbb2222c"],
        security_groups=["sg-0abc123def456789a"],
        assign_public_ip="DISABLED",
        container_overrides={
            "containerOverrides": [{"name": "main", "cpu": 2048, "memory": 8192}]
        },
    )
    def build_features():
        """Containerized feature build on Fargate."""
        pass

    @task.emr(
        emr_cluster_id="j-1A2B3C4D5E6F7",
        emr_step={
            "Name": "aggregate",
            "ActionOnFailure": "CONTINUE",
            "HadoopJarStep": {
                "Jar": "command-runner.jar",
                "Args": ["spark-submit", "s3://jobs/aggregate.py"],
            },
        },
    )
    def aggregate():
        """Heavy Spark aggregation on an existing EMR cluster."""
        pass

    @task.batch(
        job_definition="report-render:3",
        job_queue="reporting-queue",
        batch_parameters={"date": "{% $states.input.current_date %}"},
    )
    def render_report():
        """Render the daily report via AWS Batch."""
        pass

    # A nested Step Function in another account (cross-account role).
    @task.sfn(
        arn=f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:publish",
        role="orchestration",
    )
    def publish():
        """Publish results through a nested, cross-account workflow."""
        pass

    # Dependencies — function-call style for the linear spine, `>>` for the fan-in.
    bronze = to_bronze(ingest())
    silver = to_silver(bronze)
    features = build_features(silver)
    agg = aggregate(silver)
    [features, agg] >> render_report() >> publish()
