from __future__ import annotations

from pathlib import Path

import pytest

from ecstacy.sources.base import SourceError, SourceSpec, create_source


def test_file_source_reads_csv_and_parses_dates(sample_csv):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_csv)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4
    assert "region" in dataset.schema.category_columns
    assert "date" in dataset.schema.time_columns


def test_file_source_reads_json(sample_json):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_json)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4
    assert "region" in dataset.schema.category_columns


def test_file_source_reads_ndjson(sample_ndjson):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_ndjson)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4


def test_file_source_reads_parquet(sample_parquet):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_parquet)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4


def test_file_source_limits_rows(sample_csv):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_csv), "max_rows": 2})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2


def test_file_source_missing_file():
    spec = SourceSpec(kind="file", id="missing", params={"path": "/does/not/exist.csv"})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_file_source_empty_file(empty_csv):
    spec = SourceSpec(kind="file", id="empty", params={"path": str(empty_csv)})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_file_source_duplicate_columns(duplicate_csv):
    spec = SourceSpec(kind="file", id="dup", params={"path": str(duplicate_csv)})
    dataset = create_source(spec).fetch()
    assert "value" in dataset.frame.columns
    assert "value.1" in dataset.frame.columns


def test_file_source_auto_detects_format(sample_json):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_json)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4
