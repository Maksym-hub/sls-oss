"""Adapters between slsflow's internal type system and external schema sources.

Each submodule is independently importable and lazily imports its peer
dependency (pyarrow, pydantic, boto3) so `import slsflow` stays cheap and
free of optional installs. Asking for an adapter without its dependency
installed raises a clear ImportError that names the extra to install.

Public adapters:
    slsflow.adapters.pyarrow_      — pyarrow.Schema  ↔  List[Column]
    slsflow.adapters.pydantic_     — pydantic.BaseModel  →  List[Column]
    slsflow.adapters.glue          — AWS Glue Catalog  →  List[Column]

The trailing underscore on `pyarrow_` and `pydantic_` avoids shadowing the
real `pyarrow` and `pydantic` packages when users do `from slsflow.adapters
import pyarrow_ as pa_adapter`. We could pick more descriptive names
(`from_pyarrow`, `from_pydantic`) but those clash with the `Asset.from_pyarrow`
classmethod and produce confusing call-site reading.

The canonical user-facing entry points are the `Asset.from_*` classmethods —
these adapter modules are for direct use only when you want columns alone,
without an Asset wrapper.
"""

from . import pyarrow_, pydantic_, glue

__all__ = ["pyarrow_", "pydantic_", "glue"]
