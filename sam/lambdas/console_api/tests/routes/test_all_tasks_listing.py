"""get_all_tasks: the no-date/no-pipeline scan must work (unused #p bug), and
output-store / task_name-less rows must not appear as task instances.
"""
import json

from routes.tasks import get_all_tasks


def _event(pipeline=None):
    q = {}
    if pipeline:
        q["pipeline"] = pipeline
    return {"queryStringParameters": q}


def _mixed_rows():
    return [
        {"execution_name": "extract-2026-07-08-abc", "task_name": "extract",
         "pipeline_name": "sales", "status": "success", "date": "2026-07-08"},
        {"execution_name": "output#sales#extract#2026-07-08", "task_name": "extract",
         "status": "success"},                      # canonical output store — must be skipped
        {"execution_name": "sales-registration", "pipeline_name": "sales"},  # no task_name — skip
    ]


def test_no_pipeline_filter_lists_tasks(mocker):
    scan = mocker.patch("routes.tasks.executions_repo.scan", return_value=_mixed_rows())
    resp = get_all_tasks(_event())          # NO pipeline filter (the bug case)
    body = json.loads(resp["body"])
    names = [t["task_name"] for t in body["tasks"]]
    assert names == ["extract"]             # only the real execution, not output#/registration
    # the scan must not have been passed an unused #p ExpressionAttributeName
    names_arg = scan.call_args.kwargs.get("ExpressionAttributeNames", {})
    assert "#p" not in names_arg


def test_pipeline_filter_adds_p_name(mocker):
    scan = mocker.patch("routes.tasks.executions_repo.scan", return_value=_mixed_rows())
    get_all_tasks(_event(pipeline="sales"))
    names_arg = scan.call_args.kwargs.get("ExpressionAttributeNames", {})
    assert names_arg.get("#p") == "pipeline_name"   # added only when used
