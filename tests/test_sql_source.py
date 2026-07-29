from __future__ import annotations

import pytest

from ecstacy.sources.base import SourceError, SourceSpec, create_source


def test_sql_source_runs_duckdb_query():
    spec = SourceSpec(kind="sql", id="sql", params={"query": "select 1 as a, 2 as b"})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 1
    assert "a" in dataset.frame.columns
    assert "b" in dataset.frame.columns


def test_sql_source_invalid_query():
    spec = SourceSpec(kind="sql", id="sql", params={"query": "select * from missing_table"})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_sql_source_limits_rows():
    spec = SourceSpec(
        kind="sql",
        id="t",
        params={"query": "select * from range(10)", "max_rows": 3},
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 3
