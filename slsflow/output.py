"""
slsflow-output — Generate pipeline artifacts.

Reads dag.py from current directory and outputs:
  --json      Step Functions ASL JSON
  --mermaid   Mermaid diagram
  --graph     ASCII DAG graph
  --assets    Asset registry JSON (for asset-triggered pipelines)
"""

import sys
import importlib.util
from pathlib import Path


def _load_dags(dag_file: str):
    """Load DAG(s) from file."""
    path = Path(dag_file)
    if not path.exists():
        print(f"❌ Pipeline file not found: {dag_file}")
        sys.exit(1)

    try:
        spec = importlib.util.spec_from_file_location("_dag", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        from slsflow.dag import DAG as SlsflowDAG
        dags = [v for v in vars(mod).values() if isinstance(v, SlsflowDAG)]

        if not dags:
            print(f"❌ No DAG found in {dag_file}")
            sys.exit(1)

        return dags, mod

    except Exception as e:
        print(f"❌ Failed to load {dag_file}: {e}")
        sys.exit(1)


def _select_dag(dags, select_id=None):
    """Select a single DAG from a list."""
    if select_id:
        matching = [d for d in dags if d.dag_id == select_id]
        if not matching:
            print(f"❌ DAG '{select_id}' not found")
            print(f"   Available: {[d.dag_id for d in dags]}")
            sys.exit(1)
        return matching[0]
    if len(dags) > 1:
        print(f"Multiple DAGs found: {[d.dag_id for d in dags]}")
        print("Use --select <dag_id> to choose one")
        sys.exit(1)
    return dags[0]


def main():
    """
    CLI entry point for slsflow-output command.

    Usage:
        slsflow-output --json       # Generate ASL JSON
        slsflow-output --mermaid    # Generate Mermaid diagram
        slsflow-output --graph      # Show ASCII DAG graph
        slsflow-output --assets     # Generate asset registry JSON
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="slsflow-output",
        description="Generate pipeline artifacts from dag.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  slsflow-output --json           # Generate ASL JSON for deployment
  slsflow-output --mermaid        # Generate Mermaid diagram
  slsflow-output --graph          # Show DAG as ASCII graph
  slsflow-output --assets         # Generate asset registry JSON
  slsflow-output --json --file my_pipeline.py   # Custom file
  slsflow-output --json --select my-dag         # Multi-DAG file"""
    )

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--json", action="store_true",
                              help="Generate Step Functions ASL JSON")
    output_group.add_argument("--mermaid", action="store_true",
                              help="Generate Mermaid diagram")
    output_group.add_argument("--graph", action="store_true",
                              help="Show DAG as ASCII graph")
    output_group.add_argument("--assets", action="store_true",
                              help="Generate asset registry JSON (for asset-triggered pipelines)")

    parser.add_argument("--file", "-f", default="dag.py",
                        help="Pipeline file (default: dag.py)")
    parser.add_argument("--select", help="Select specific DAG by ID (for multi-DAG files)")

    args = parser.parse_args()

    dags, mod = _load_dags(args.file)

    if args.assets:
        # Assets works on all DAGs in the file
        from slsflow.generators import generate_all_assets
        import json
        print(json.dumps(generate_all_assets(dags), indent=2))
        return

    dag = _select_dag(dags, args.select)

    if args.json:
        from slsflow.generators import generate_step_function_json
        print(generate_step_function_json(dag))

    elif args.mermaid:
        from slsflow.generators import generate_mermaid
        print(generate_mermaid(dag))

    elif args.graph:
        from slsflow.generators import render_dag_ascii
        print(render_dag_ascii(dag))


if __name__ == "__main__":
    main()
