"""
slsflow deploy — CloudFormation-based pipeline deployment.

CloudFormation-based pipeline deployment.

Usage:
    # From pipeline directory
    cd pipelines/acme/daily
    slsflow-deploy

    # Or with options
    slsflow-deploy --stage prod
    slsflow-deploy --dry-run
    slsflow-deploy --destroy

Workflow:
    1. Reads dag.py (imports DAG)
    2. Reads infra config from SSM (/slsflow/{stage}/)
    3. Generates ASL JSON
    4. Generates CloudFormation template
    5. aws cloudformation deploy
    6. Calls SFN with register_only=true (pipeline registration)
"""

import json
import os
import sys
import subprocess
import importlib.util
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import boto3

from .generators import (
    generate_step_function_json,
    generate_dag_hash,
    generate_eventbridge_schedule,
)
from .dag import DAG
from .config import config as slsflow_config


# =============================================================================
# CFN Template Generation
# =============================================================================

def _check_glue_granularity_drift(dag: DAG, *, region: Optional[str], profile: Optional[str]) -> None:
    """Advisory check: compare each Glue-backed asset's declared granularity
    to what its Glue PartitionKeys suggest (ADR #50).

    Prints warnings on mismatch but never fails — the declared value always
    wins. Users with naming conventions that don't match the inference
    heuristics (or who know their data better than the heuristics) are
    expected to ignore the warning.
    """
    try:
        from .adapters.glue import (
            fetch_glue_partition_keys,
            infer_granularity_from_partition_keys,
        )
    except ImportError:
        return  # boto3 missing — skip silently

    seen: dict = {}
    for task in getattr(dag, "tasks", []):
        for outlet in getattr(task, "outlets", []) or []:
            glue_table = getattr(outlet, "glue_table", "")
            if not glue_table or "." not in glue_table:
                continue
            seen.setdefault(outlet.name, outlet)

    if not seen:
        return

    print("\nChecking Glue-declared granularity for assets...")
    for asset_name, asset in seen.items():
        glue_table = asset.glue_table
        db, _, tbl = glue_table.partition(".")
        declared = getattr(asset, "granularity", "daily")
        try:
            keys = fetch_glue_partition_keys(
                db, tbl,
                catalog_id=getattr(asset, "glue_catalog", "") or None,
                region=getattr(asset, "glue_region", "") or region,
            )
        except Exception as e:
            print(f"  ? {asset_name}: could not read Glue ({type(e).__name__})")
            continue

        inferred = infer_granularity_from_partition_keys(keys)
        if inferred is None:
            print(f"  • {asset_name}: declared {declared}, Glue keys "
                  f"{keys or '(none)'} (no inference)")
            continue

        if inferred == declared:
            print(f"  ✓ {asset_name}: declared {declared}, Glue confirms")
        else:
            print(
                f"  ⚠ {asset_name}: declared {declared} but Glue partition "
                f"keys {keys} suggest {inferred}. "
                f"If your declaration is correct, ignore this. Otherwise "
                f"update granularity={inferred!r} in your Asset(...)."
            )


def _generate_cfn_template(
    dag: DAG,
    namespace: str,
    stage: str,
    region: str,
    role_arn: str,
    wrapper_arn: str,
    registry_table: str,
    tokens_table: str,
    log_retention_days: int = 30,
    log_level: str = "ERROR",
) -> dict:
    """Generate CloudFormation template for a single pipeline."""

    full_name = f"{namespace}-{stage}-slsflow-{dag.dag_id}"
    asl_json = generate_step_function_json(
        dag,
        wrapper_arn=wrapper_arn,
        registry_table=registry_table,
        tokens_table=tokens_table,
    )

    resources = {}
    outputs = {}

    # Log Group
    resources["PipelineLogGroup"] = {
        "Type": "AWS::Logs::LogGroup",
        "Properties": {
            "LogGroupName": f"/{namespace}/{stage}/slsflow/{dag.dag_id}",
            "RetentionInDays": log_retention_days,
            "Tags": [
                {"Key": "Pipeline", "Value": dag.dag_id},
                {"Key": "Stage", "Value": stage},
                {"Key": "Namespace", "Value": namespace},
                {"Key": "ManagedBy", "Value": "slsflow-deploy"},
            ],
        },
    }

    # Step Function
    resources["PipelineStateMachine"] = {
        "Type": "AWS::StepFunctions::StateMachine",
        "Properties": {
            "StateMachineName": full_name,
            "RoleArn": role_arn,
            "DefinitionString": asl_json,
            "LoggingConfiguration": {
                "Level": log_level,
                "IncludeExecutionData": False,
                "Destinations": [
                    {
                        "CloudWatchLogsLogGroup": {
                            "LogGroupArn": {
                                "Fn::GetAtt": ["PipelineLogGroup", "Arn"]
                            }
                        }
                    }
                ],
            },
            "Tags": [
                {"Key": "Name", "Value": full_name},
                {"Key": "Pipeline", "Value": dag.dag_id},
                {"Key": "Stage", "Value": stage},
                {"Key": "Namespace", "Value": namespace},
                {"Key": "ManagedBy", "Value": "slsflow-deploy"},
            ],
        },
        "DependsOn": "PipelineLogGroup",
    }

    # EventBridge schedule (time-based)
    if dag.schedule and not dag.is_asset_triggered:
        schedule_expr = dag._eventbridge_schedule
        resources["PipelineScheduleRule"] = {
            "Type": "AWS::Events::Rule",
            "Properties": {
                "Name": f"{full_name}-schedule",
                "Description": f"Schedule for {dag.dag_id}",
                "ScheduleExpression": schedule_expr,
                "State": "ENABLED",
                "Targets": [
                    {
                        "Id": "PipelineTarget",
                        "Arn": {"Ref": "PipelineStateMachine"},
                        "RoleArn": role_arn,
                        "Input": json.dumps({
                            "triggered_by": "schedule",
                            "schedule": schedule_expr,
                        }),
                    }
                ],
            },
            "DependsOn": "PipelineStateMachine",
        }

    outputs["StateMachineArn"] = {
        "Description": f"ARN of {dag.dag_id} Step Function",
        "Value": {"Ref": "PipelineStateMachine"},
        "Export": {"Name": f"{namespace}-{stage}-slsflow-{dag.dag_id}-arn"},
    }

    outputs["DagHash"] = {
        "Description": "DAG hash for change detection",
        "Value": generate_dag_hash(dag),
    }

    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": (
            f"SLSFlow pipeline: {dag.dag_id}. "
            f"{dag.description or ''} "
            "Managed by slsflow-deploy."
        ).strip(),
        "Resources": resources,
        "Outputs": outputs,
    }


# =============================================================================
# Registration
# =============================================================================

def _register_pipeline(
    sfn_arn: str,
    dag_id: str,
    region: str,
    profile: Optional[str] = None,
):
    """Trigger pipeline registration via Step Function."""
    session = boto3.Session(profile_name=profile, region_name=region)
    sfn = session.client("stepfunctions")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    print(f"  Registering pipeline {dag_id}...")
    sfn.start_execution(
        stateMachineArn=sfn_arn,
        name=f"{dag_id}-register-{ts}",
        input=json.dumps({"register_only": True}),
    )
    print("  ✅ Registration triggered")


# =============================================================================
# Main deploy function
# =============================================================================

def deploy_pipeline(
    dag: DAG,
    stage: Optional[str] = None,
    region: Optional[str] = None,
    dry_run: bool = False,
    destroy: bool = False,
    log_level: str = "ERROR",
    log_retention_days: int = 30,
    profile: Optional[str] = None,
):
    """Deploy a single DAG via CloudFormation."""

    stage = stage or slsflow_config.stage
    region = region or slsflow_config.region
    namespace = slsflow_config.namespace
    profile = profile or slsflow_config.profile

    # Read infra config from SSM
    print(f"\nReading infra config from SSM /slsflow/{stage}/...")
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        # Verify credentials work
        caller_identity = session.client("sts").get_caller_identity()
    except Exception as e:
        err = str(e)
        if "credentials" in err.lower() or "access" in err.lower() or "AuthFailure" in err:
            print(f"❌ AWS credentials error: {err}")
            if not profile:
                print("   Tip: try slsflow-deploy --profile <your-profile>")
                print("   Available profiles: check ~/.aws/credentials or ~/.aws/config")
            sys.exit(1)
        session = boto3.Session(region_name=region)
        caller_identity = None

    # Guard: verify we're deploying to the expected account
    stage_config = slsflow_config.for_stage(stage)
    expected_account = stage_config.get("account_id")
    if expected_account and caller_identity:
        actual_account = caller_identity["Account"]
        if actual_account != expected_account:
            print(f"❌ Account mismatch for stage '{stage}':")
            print(f"   Expected: {expected_account} (from config.py)")
            print(f"   Actual:   {actual_account} (from credentials)")
            print("   Check your --profile or AWS credentials.")
            sys.exit(1)
    ssm = session.client("ssm")

    def get_ssm(name: str) -> Optional[str]:
        try:
            return ssm.get_parameter(
                Name=f"/slsflow/{stage}/{name}"
            )["Parameter"]["Value"]
        except ssm.exceptions.ParameterNotFound:
            return None

    wrapper_arn = get_ssm("wrapper_arn")
    role_arn = get_ssm("pipeline_execution_role_arn")
    registry_table = get_ssm("pipeline_registry_table")
    tokens_table = get_ssm("pipeline_tokens_table")
    results_bucket = get_ssm("results_bucket")

    if not wrapper_arn or not role_arn:
        print("❌ SSM parameters not found. Run `sam deploy` first.")
        print(f"   Missing: /slsflow/{stage}/wrapper_arn or /slsflow/{stage}/pipeline_execution_role_arn")
        if not profile:
            print("   Tip: if you have multiple AWS profiles, try: slsflow-deploy --profile <your-profile>")
        sys.exit(1)

    stack_name = f"{namespace}-{stage}-slsflow-{dag.dag_id}"

    # Destroy
    if destroy:
        print(f"\nDestroying stack: {stack_name}")
        if not dry_run:
            cmd = [
                "aws", "cloudformation", "delete-stack",
                "--stack-name", stack_name,
                "--region", region,
            ]
            if profile:
                cmd += ["--profile", profile]
            subprocess.run(cmd, check=True)
            print(f"✅ Stack deletion initiated: {stack_name}")
        else:
            print(f"[dry-run] Would delete stack: {stack_name}")
        return

    # Generate template
    print(f"\nGenerating CloudFormation template for: {dag.dag_id}")
    template = _generate_cfn_template(
        dag=dag,
        namespace=namespace,
        stage=stage,
        region=region,
        role_arn=role_arn,
        wrapper_arn=wrapper_arn,
        registry_table=registry_table or "",
        tokens_table=tokens_table or "",
        log_level=log_level,
        log_retention_days=log_retention_days,
    )

    # Write template to temp file
    template_path = Path(f"/tmp/slsflow-{dag.dag_id}-{stage}.json")
    template_path.write_text(json.dumps(template, indent=2))
    print(f"  Template: {template_path}")

    if dry_run:
        print(f"\n[dry-run] Would deploy stack: {stack_name}")
        print(f"  Resources: {list(template['Resources'].keys())}")
        print(f"  DAG hash: {generate_dag_hash(dag)}")
        return

    # Deploy via CloudFormation
    print(f"\nDeploying stack: {stack_name}")
    cmd = [
        "aws", "cloudformation", "deploy",
        "--template-file", str(template_path),
        "--stack-name", stack_name,
        "--region", region,
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--no-fail-on-empty-changeset",
    ]
    if profile:
        cmd += ["--profile", profile]
    if results_bucket:
        cmd += ["--s3-bucket", results_bucket, "--s3-prefix", "cfn-pipeline-templates"]
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print("\n❌ CloudFormation deploy failed")
        sys.exit(1)

    # Get SFN ARN from stack outputs
    cfn = session.client("cloudformation")
    stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    sfn_arn = outputs.get("StateMachineArn")

    # Register pipeline
    if sfn_arn and registry_table:
        _register_pipeline(sfn_arn, dag.dag_id, region, profile=profile)

    print("\n✅ Pipeline deployed successfully!")
    print(f"   Stack:   {stack_name}")
    print(f"   SFN ARN: {sfn_arn}")


# =============================================================================
# CLI entry point
# =============================================================================

def _load_dag_from_file(path: Path) -> list:
    """Load DAG(s) from a dag.py file.

    Imports pipeline file purely for DAG extraction.
    Pipeline files should not contain AWS calls at module level.
    """
    spec = importlib.util.spec_from_file_location("pipeline", path)
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except SystemExit:
        pass
    except Exception as e:
        print(f"❌ Error loading pipeline: {e}")
        sys.exit(1)

    # Collect all DAGs defined in the file
    dags = [obj for obj in module.__dict__.values() if isinstance(obj, DAG)]
    return dags


def main():
    parser = argparse.ArgumentParser(
        description="Deploy SLSFlow pipeline via CloudFormation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  slsflow-deploy                    # Deploy from current directory
  slsflow-deploy --stage prod       # Deploy to prod
  slsflow-deploy --dry-run          # Preview without deploying
  slsflow-deploy --destroy          # Remove pipeline stack
  slsflow-deploy --file my_dag.py   # Deploy specific file
        """,
    )
    parser.add_argument("--stage", help="Deployment stage (default: from config.py DEFAULT_STAGE)")
    parser.add_argument("--region", help="AWS region (default: from config.py ENVIRONMENTS)")
    parser.add_argument("--file", default="dag.py", help="Pipeline file (default: dag.py)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    parser.add_argument("--destroy", action="store_true", help="Remove pipeline stack")
    parser.add_argument("--log-level", default="ERROR", choices=["ALL", "ERROR", "FATAL", "OFF"])
    parser.add_argument("--log-retention", type=int, default=30, help="Log retention in days")
    parser.add_argument("--select", help="Select specific DAG by ID (for multi-DAG files)")
    parser.add_argument("--profile", help="AWS profile name (from ~/.aws/credentials)")

    args = parser.parse_args()

    # Find pipeline file
    pipeline_file = Path(args.file)
    if not pipeline_file.exists():
        print(f"❌ Pipeline file not found: {pipeline_file}")
        sys.exit(1)

    # Load DAGs
    print(f"Loading pipeline: {pipeline_file}")
    dags = _load_dag_from_file(pipeline_file)

    if not dags:
        print("❌ No DAG found in pipeline file")
        sys.exit(1)

    # Select DAG
    if args.select:
        dags = [d for d in dags if d.dag_id == args.select]
        if not dags:
            print(f"❌ DAG '{args.select}' not found")
            sys.exit(1)

    if len(dags) > 1 and not args.select:
        print(f"Found {len(dags)} DAGs: {[d.dag_id for d in dags]}")
        print("Deploying all...")

    # Deploy each DAG
    for dag in dags:
        deploy_pipeline(
            dag=dag,
            stage=args.stage,
            region=args.region,
            dry_run=args.dry_run,
            destroy=args.destroy,
            log_level=args.log_level,
            log_retention_days=args.log_retention,
            profile=args.profile,
        )


if __name__ == "__main__":
    main()
