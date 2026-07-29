"""Profile ecstacy's load path: peak RSS and cProfile per source format.

Run from a repo checkout:

    uv run scripts/profile_load.py --rows 1_000_000 --format csv
    uv run scripts/profile_load.py --rows 1_000_000 --format json
    uv run scripts/profile_load.py --rows 1_000_000 --format parquet

Generates a synthetic frame, writes it to a temp file, then loads it through
the real source pipeline (FileSource.fetch) under cProfile + tracemalloc.
Reports wall time, peak RSS, and the top 20 cumulative hotspots.

This is a manual profiling tool, not a CI gate. The pytest-benchmark budgets
in tests/benchmarks/ are the enforceable side of the harness.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import resource
import tempfile
import tracemalloc
from pathlib import Path

import pandas as pd

from ecstacy.sources.base import SourceSpec, create_source


def _synthetic_frame(rows: int) -> pd.DataFrame:
    rng = pd.date_range("2024-01-01", periods=rows, freq="s")
    return pd.DataFrame(
        {
            "timestamp": rng,
            "region": pd.array(["us", "eu", "apac", "latam"] * (rows // 4 + 1))[:rows],
            "value": pd.array([float(i) for i in range(rows)]),
            "count": pd.array([i % 1000 for i in range(rows)]),
        }
    )


def _write(frame: pd.DataFrame, fmt: str, tmpdir: Path) -> Path:
    path = tmpdir / f"data.{fmt}"
    if fmt == "csv":
        frame.to_csv(path, index=False)
    elif fmt == "json":
        frame.to_json(path, orient="records", date_format="iso")
    elif fmt == "parquet":
        frame.to_parquet(path, index=False)
    else:
        raise ValueError(f"unsupported format: {fmt}")
    return path


def _peak_rss_kb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--format", choices=["csv", "json", "parquet"], default="csv")
    parser.add_argument("--top", type=int, default=20, help="cProfile rows to show")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmpdir = Path(raw_tmp)
        frame = _synthetic_frame(args.rows)
        path = _write(frame, args.format, tmpdir)
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"format={args.format} rows={args.rows} file={size_mb:.1f} MB")

        baseline_rss = _peak_rss_kb()
        spec = SourceSpec(kind="file", id=path.name, params={"path": str(path)})

        tracemalloc.start()
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            dataset = create_source(spec).fetch()
        finally:
            profiler.disable()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        peak_rss = _peak_rss_kb() - baseline_rss
        print(f"loaded rows={dataset.meta.rows}")
        print(f"tracemalloc peak={peak / 1024 / 1024:.1f} MB")
        print(f"peak RSS delta={peak_rss / 1024:.1f} MB")

        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
        stats.print_stats(args.top)
        print("\ntop cumulative hotspots:")
        print(stream.getvalue())


if __name__ == "__main__":
    main()
