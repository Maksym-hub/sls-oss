"""polyris-deploy must validate the DAG before touching AWS.

Deploying an invalid DAG otherwise only fails later in CloudFormation (or ships a
broken pipeline), so deploy_pipeline runs the same check as polyris-validate first.
"""
import pytest

from polyris import deploy


def test_deploy_rejects_invalid_dag_before_aws(mocker):
    dag = mocker.MagicMock()
    dag.dag_id = "broken"
    mocker.patch(
        "polyris.validation.validate_asl_from_dag",
        return_value=(False, ["Cycle detected: a -> b -> a"], []),
    )
    boto = mocker.patch("polyris.deploy.boto3")

    with pytest.raises(SystemExit) as exc:
        deploy.deploy_pipeline(dag)

    assert exc.value.code == 1
    boto.Session.assert_not_called()  # the gate fired before any AWS work


def test_deploy_proceeds_past_gate_when_valid(mocker):
    dag = mocker.MagicMock()
    dag.dag_id = "ok"
    mocker.patch(
        "polyris.validation.validate_asl_from_dag",
        return_value=(True, [], []),
    )
    # Make the next step (credentials) exit so we don't reach real AWS, but prove
    # the validation gate did not block a valid DAG.
    boto = mocker.patch("polyris.deploy.boto3")
    boto.Session.side_effect = SystemExit(2)

    with pytest.raises(SystemExit) as exc:
        deploy.deploy_pipeline(dag)

    assert exc.value.code == 2  # passed the gate, failed later (as arranged)
    boto.Session.assert_called_once()
