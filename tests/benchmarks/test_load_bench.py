"""Performance budgets, opt-in via the ``bench`` marker.

Normal ``pytest`` runs skip these (they aren't collected into the default
suite because ``testpaths`` is ``tests/`` but the marker gates execution
too). Run explicitly with:

    uv run pytest -m bench --benchmark-only

Budgets are deliberately generous to start (1.5x of raw pandas) and should be
tightened as the native-reader / downsampling work lands. A budget failure is
a regression signal, not a hard CI block yet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ecstacy.sources.base import SourceSpec, create_source

pytestmark = pytest.mark.bench

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _write_csv(tmp_path: Path, rows: int) -> Path:
    path = tmp_path / "big.csv"
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=rows, freq="s"),
            "region": pd.array(["us", "eu", "apac", "latam"] * (rows // 4 + 1))[:rows],
            "value": pd.array([float(i) for i in range(rows)]),
        }
    ).to_csv(path, index=False)
    return path


@pytest.mark.benchmark
def test_csv_load_within_budget(tmp_path, benchmark):
    import time

    rows = 1_000_000
    path = _write_csv(tmp_path, rows)

    def load():
        return create_source(
            SourceSpec(kind="file", id=path.name, params={"path": str(path)})
        ).fetch()

    result = benchmark.pedantic(load, iterations=1, rounds=3, warmup_rounds=1)
    assert result.meta.rows == rows
    # Raw pd.read_csv on the same file is the baseline; load through the
    # source pipeline should stay within ~1.5x of it. Measured outside the
    # benchmark fixture (which can only be used once per test).
    times = []
    for _ in range(3):
        start = time.perf_counter()
        pd.read_csv(path)
        times.append(time.perf_counter() - start)
    baseline = sum(times) / len(times)
    ratio = benchmark.stats.stats.mean / baseline
    assert ratio <= 1.5, f"load is {ratio:.2f}x raw pd.read_csv (budget 1.5x)"


@pytest.mark.benchmark
def test_filter_transform_100k(tmp_path, benchmark):
    from ecstacy.core.transforms import parse_transform_query

    rows = 100_000
    path = _write_csv(tmp_path, rows)
    dataset = create_source(
        SourceSpec(kind="file", id=path.name, params={"path": str(path)})
    ).fetch()

    transform = parse_transform_query("where value > 50000 | group_by region | agg mean")

    def apply():
        return transform.apply(dataset.frame)

    result = benchmark.pedantic(apply, iterations=1, rounds=5, warmup_rounds=1)
    assert len(result) <= 4  # one row per region


@pytest.mark.benchmark
def test_line_downsample_under_budget(benchmark):
    from ecstacy.widgets.base import numeric
    from ecstacy.widgets.charts import MAX_CHART_POINTS

    series = pd.Series(range(1_000_000), dtype="float64")

    def downsample():
        work = series.tail(MAX_CHART_POINTS)
        return numeric(work).tolist()

    result = benchmark.pedantic(downsample, iterations=1, rounds=10, warmup_rounds=1)
    assert len(result) == MAX_CHART_POINTS
    # Target: <= 50 ms after downsample (the tail() + tolist() hot path).
    assert benchmark.stats.stats.mean <= 0.050
