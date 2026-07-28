from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import orjson
import pandas as pd
from pandas.api import types as pdt

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError

_READERS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".ndjson": "ndjson",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".log": "log",
    ".txt": "log",
    ".xlsx": "excel",
    ".xls": "excel",
}

_STDIN_SENTINEL = "-"


def _deduplicate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if len(set(frame.columns)) == len(frame.columns):
        return frame
    counts: dict[str, int] = {}
    new_columns = []
    for col in frame.columns:
        if col in counts:
            counts[col] += 1
            new_columns.append(f"{col}_{counts[col]}")
        else:
            counts[col] = 0
            new_columns.append(col)
    frame.columns = new_columns
    return frame


@registry.sources.register("file")
class FileSource(Source):
    kind = "file"

    def __init__(
        self,
        id: str,
        path: str,
        fmt: str | None = None,
        max_rows: int | None = None,
        sheet: str | int | None = None,
        **params: Any,
    ) -> None:
        super().__init__(id=id, path=path, fmt=fmt, max_rows=max_rows, **params)
        self.is_stdin = path == _STDIN_SENTINEL
        self.path = Path(path).expanduser() if not self.is_stdin else Path(path)
        self.fmt = fmt or (
            _READERS.get(self.path.suffix.lower(), "csv") if not self.is_stdin else "csv"
        )
        self.max_rows = max_rows
        self.sheet = sheet

    def describe(self) -> str:
        return "file:<stdin>" if self.is_stdin else f"file:{self.path.name}"

    def fetch(self) -> DataSet:
        if self.is_stdin:
            return self._fetch_stdin()
        if not self.path.exists():
            raise SourceError(f"no such file: {self.path}", source_id=self.id)
        raw: Any = None
        try:
            if self.fmt == "csv":
                frame = pd.read_csv(self.path, nrows=self.max_rows)
            elif self.fmt == "tsv":
                frame = pd.read_csv(self.path, sep="\t", nrows=self.max_rows)
            elif self.fmt == "parquet":
                frame = _read_parquet(self.path, self.max_rows)
            elif self.fmt == "ndjson":
                frame = pd.read_json(self.path, lines=True, nrows=self.max_rows)
            elif self.fmt == "json":
                frame, raw = _read_json(self.path)
            elif self.fmt == "excel":
                frame = _read_excel(self.path, self.sheet, self.max_rows)
            else:
                frame = _read_log(self.path)
        except pd.errors.EmptyDataError as exc:
            raise SourceError(f"empty file: {self.path}", source_id=self.id) from exc
        except Exception as exc:
            raise SourceError(
                f"failed to read {self.path} as {self.fmt}: {exc}", source_id=self.id
            ) from exc
        frame = _deduplicate_columns(frame)
        frame = _autoparse_dates(frame)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind, raw=raw)

    def _fetch_stdin(self) -> DataSet:
        raw: Any = None
        try:
            if self.fmt == "csv":
                frame = pd.read_csv(sys.stdin, nrows=self.max_rows)
            elif self.fmt == "tsv":
                frame = pd.read_csv(sys.stdin, sep="\t", nrows=self.max_rows)
            elif self.fmt == "ndjson":
                frame = pd.read_json(sys.stdin, lines=True, nrows=self.max_rows)
            elif self.fmt == "json":
                payload = sys.stdin.read()
                if not payload.strip():
                    raise pd.errors.EmptyDataError("empty stdin")
                raw = orjson.loads(payload)
                records = raw
                if isinstance(raw, dict):
                    records = next((v for v in raw.values() if isinstance(v, list)), [raw])
                frame = pd.json_normalize(records)
            elif self.fmt == "log":
                lines = sys.stdin.read().splitlines()
                frame = pd.DataFrame(
                    {"line_no": range(1, len(lines) + 1), "line": lines}
                )
            else:
                raise SourceError(
                    f"stdin does not support format {self.fmt!r}; "
                    "use --format csv|tsv|json|ndjson|log",
                    source_id=self.id,
                )
        except pd.errors.EmptyDataError as exc:
            raise SourceError("empty stdin", source_id=self.id) from exc
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(
                f"failed to read stdin as {self.fmt}: {exc}", source_id=self.id
            ) from exc
        if self.max_rows is not None and self.fmt == "json":
            frame = frame.head(self.max_rows)
        frame = _deduplicate_columns(frame)
        frame = _autoparse_dates(frame)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind, raw=raw)


def _read_parquet(path: Path, max_rows: int | None) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if max_rows is not None:
        frame = frame.head(max_rows)
    return frame


def _read_json(path: Path) -> tuple[pd.DataFrame, Any]:
    raw = orjson.loads(path.read_bytes())
    records = raw
    if isinstance(raw, dict):
        records = next((v for v in raw.values() if isinstance(v, list)), [raw])
    frame = pd.json_normalize(records)
    return frame, raw


def _read_log(path: Path) -> pd.DataFrame:
    lines = path.read_text(errors="replace").splitlines()
    return pd.DataFrame({"line_no": range(1, len(lines) + 1), "line": lines})


def _read_excel(
    path: Path, sheet: str | int | None, max_rows: int | None
) -> pd.DataFrame:
    sheet_name = sheet if sheet is not None else 0
    return pd.read_excel(path, sheet_name=sheet_name, nrows=max_rows)


def _autoparse_dates(frame: pd.DataFrame) -> pd.DataFrame:
    for name in frame.columns:
        series = frame[name]
        if pdt.is_numeric_dtype(series) or pdt.is_datetime64_any_dtype(series):
            continue
        if not pdt.is_string_dtype(series):
            continue
        sample = series.dropna().head(100)
        if sample.empty:
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().mean() > 0.8:
            frame[name] = parsed
    return frame
