"""Skip benchmark tests by default; opt in with ``--run-bench``.

Without this, the perf-budget tests in tests/benchmarks/ run as part of every
``pytest`` invocation (adding ~8s and large temp files). Run them explicitly:

    uv run pytest --run-bench
    uv run pytest tests/benchmarks/ --run-bench
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.getgroup("benchmark").addoption(
        "--run-bench",
        action="store_true",
        default=False,
        help="Run tests marked ``bench`` (skipped by default).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-bench"):
        return
    skip = pytest.mark.skip(reason="needs --run-bench to run")
    for item in items:
        if "bench" in item.keywords:
            item.add_marker(skip)
