from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ecstacy.sources.base import SourceError, SourceSpec, create_source


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TABLE metrics (region TEXT, value REAL);"
        "INSERT INTO metrics VALUES ('us', 10.0), ('eu', 15.0), ('ap', 12.0), ('us', 9.0);"
    )
    conn.commit()
    conn.close()
    return db_path


def test_sqlite_source_runs_query(sqlite_db: Path):
    spec = SourceSpec(
        kind="sqlite", id="sqlite", params={"query": "SELECT * FROM metrics", "db": str(sqlite_db)}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4
    assert "region" in dataset.schema.category_columns
    assert "value" in dataset.schema.value_columns


def test_sqlite_source_limits_rows(sqlite_db: Path):
    spec = SourceSpec(
        kind="sqlite",
        id="sqlite",
        params={"query": "SELECT * FROM metrics", "db": str(sqlite_db), "max_rows": 2},
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2


def test_sqlite_source_invalid_query(sqlite_db: Path):
    spec = SourceSpec(
        kind="sqlite",
        id="sqlite",
        params={"query": "SELECT * FROM missing_table", "db": str(sqlite_db)},
    )
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_sqlite_source_missing_db(tmp_path: Path):
    bad = tmp_path / "not_a.db"
    bad.write_text("this is not a sqlite database")
    spec = SourceSpec(
        kind="sqlite",
        id="sqlite",
        params={"query": "SELECT 1", "db": str(bad)},
    )
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_sqlite_source_in_memory():
    spec = SourceSpec(
        kind="sqlite", id="sqlite", params={"query": "SELECT 1 AS a, 2 AS b", "db": ":memory:"}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 1
    assert "a" in dataset.frame.columns


def test_sqlite_source_in_memory_persists_across_fetches():
    source = create_source(
        SourceSpec(
            kind="sqlite",
            id="sqlite",
            params={"query": "SELECT 1", "db": ":memory:"},
        )
    )
    conn = source._get_connection()
    conn.executescript(
        "CREATE TABLE temp_t(x INT); INSERT INTO temp_t VALUES (1), (2), (3);"
    )
    source.query = "SELECT * FROM temp_t"
    dataset = source.fetch()
    assert dataset.meta.rows == 3
    source.close()
