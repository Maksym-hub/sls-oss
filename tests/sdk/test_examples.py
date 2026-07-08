"""The shipped example pipelines must generate valid ASL.

These examples are documentation *and* a regression net for the DSL (task types,
dependencies, xcom data-passing). If one stops compiling, this fails.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from polyris.generators import generate_step_function_json, validate_asl

_EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*/dag.py"))


@pytest.mark.parametrize("dag_file", _EXAMPLES, ids=lambda p: p.parent.name)
def test_example_generates_valid_asl(dag_file):
    spec = importlib.util.spec_from_file_location(f"ex_{dag_file.parent.name}", dag_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    asl = generate_step_function_json(module.dag)
    if isinstance(asl, str):
        asl = json.loads(asl)

    valid, errors, _warnings = validate_asl(asl)
    assert valid, f"{dag_file.parent.name} produced invalid ASL: {errors}"


def test_all_examples_discovered():
    # Guard against the glob silently matching nothing.
    assert len(_EXAMPLES) >= 5
