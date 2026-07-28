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


def test_file_source_reads_xlsx(sample_xlsx):
    spec = SourceSpec(kind="file", id="sample", params={"path": str(sample_xlsx)})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4
    assert "region" in dataset.schema.category_columns
    assert "value" in dataset.schema.value_columns


def test_file_source_xlsx_sheet_by_name(sample_xlsx):
    spec = SourceSpec(
        kind="file", id="sample", params={"path": str(sample_xlsx), "sheet": "data"}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 4


def test_file_source_xlsx_limits_rows(sample_xlsx):
    spec = SourceSpec(
        kind="file", id="sample", params={"path": str(sample_xlsx), "max_rows": 2}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2


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


def test_file_source_json_limits_rows(sample_json):
    spec = SourceSpec(
        kind="file", id="sample", params={"path": str(sample_json), "max_rows": 2}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2


def test_file_source_log_limits_rows(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("line1\nline2\nline3\nline4\nline5\n")
    spec = SourceSpec(
        kind="file", id="log", params={"path": str(log_file), "max_rows": 3}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 3


def test_file_source_stdin_csv(monkeypatch):
    import io

    data = "date,region,value\n2024-01-01,us,10\n2024-01-02,eu,15\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    spec = SourceSpec(kind="file", id="stdin", params={"path": "-"})
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2
    assert "region" in dataset.schema.category_columns
    assert "value" in dataset.schema.value_columns


def test_file_source_stdin_ndjson(monkeypatch):
    import io

    data = '{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n'
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    spec = SourceSpec(
        kind="file", id="stdin", params={"path": "-", "fmt": "ndjson"}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 2
    assert "a" in dataset.schema.value_columns


def test_file_source_stdin_json(monkeypatch):
    import io

    data = '{"items": [{"a": 1}, {"a": 2}, {"a": 3}]}'
    monkeypatch.setattr("sys.stdin", io.StringIO(data))
    spec = SourceSpec(
        kind="file", id="stdin", params={"path": "-", "fmt": "json"}
    )
    dataset = create_source(spec).fetch()
    assert dataset.meta.rows == 3


def test_file_source_stdin_empty(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    spec = SourceSpec(kind="file", id="stdin", params={"path": "-"})
    with pytest.raises(SourceError):
        create_source(spec).fetch()


def test_file_source_stdin_unsupported_format(monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    spec = SourceSpec(
        kind="file", id="stdin", params={"path": "-", "fmt": "parquet"}
    )
    with pytest.raises(SourceError):
        create_source(spec).fetch()
