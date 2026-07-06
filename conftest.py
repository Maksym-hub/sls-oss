"""Session-wide pytest configuration.

EXPERIMENTAL-ASSETS: assets ship disabled in the v1 open-source release (see
``polyris/assets.py``). The test suite exercises the asset engine end to end, so
it opts in here. This affects tests only — the shipped default stays off.
"""
import os

os.environ.setdefault("POLYRIS_ENABLE_ASSETS", "1")
