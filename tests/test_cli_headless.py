from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ecstacy.cli import app

runner = CliRunner()


def _data_dir() -> Path:
    return Path(__file__).parent / "data"


def test_headless_head_prints_rows():
    result = runner.invoke(app, ["file", str(_data_dir() / "sample.csv"), "--head", "2"])
    assert result.exit_code == 0
    assert "region" in result.stdout
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert len(lines) == 3


def test_headless_tail_prints_rows():
    result = runner.invoke(app, ["file", str(_data_dir() / "sample.csv"), "--tail", "1"])
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert len(lines) == 2


def test_headless_head_precedence_over_tail():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--head", "1", "--tail", "1"]
    )
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert len(lines) == 2


def test_headless_export_csv():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--export", "csv"]
    )
    assert result.exit_code == 0
    assert result.stdout.startswith("date,region,value,count")
    assert "us" in result.stdout


def test_headless_export_json():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--export", "json"]
    )
    assert result.exit_code == 0
    assert '"region":' in result.stdout
    assert '"value":' in result.stdout


def test_headless_export_markdown():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--export", "markdown"]
    )
    assert result.exit_code == 0
    assert "| region |" in result.stdout or "region" in result.stdout
    assert "---" in result.stdout


def test_headless_export_with_head():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--export", "csv", "--head", "1"]
    )
    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2


def test_headless_sqlite_export():
    result = runner.invoke(
        app, ["sqlite", "SELECT 1 AS a, 2 AS b", "--export", "csv"]
    )
    assert result.exit_code == 0
    assert "a,b" in result.stdout
    assert "1,2" in result.stdout


def test_headless_sql_headless():
    result = runner.invoke(app, ["sql", "SELECT 1 AS a", "--head", "5"])
    assert result.exit_code == 0
    assert "a" in result.stdout


def test_headless_open_command_csv():
    result = runner.invoke(app, ["open", str(_data_dir() / "sample.csv"), "--head", "2"])
    assert result.exit_code == 0
    assert "region" in result.stdout


def test_headless_export_invalid_format():
    result = runner.invoke(
        app, ["file", str(_data_dir() / "sample.csv"), "--export", "xml"]
    )
    assert result.exit_code != 0


def test_headless_missing_file_errors():
    result = runner.invoke(app, ["file", "/does/not/exist.csv", "--head", "2"])
    assert result.exit_code == 1


def test_open_max_rows_applied():
    result = runner.invoke(
        app, ["open", str(_data_dir() / "sample.csv"), "--max-rows", "2", "--head", "10"]
    )
    assert result.exit_code == 0
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    assert len(lines) == 3
