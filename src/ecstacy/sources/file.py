from __future__ import annotations

import sys
from itertools import islice
from pathlib import Path
from typing import Any

import duckdb
import orjson
import pandas as pd
from pandas.api import types as pdt

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.core.dataset import deduplicate_columns as _deduplicate_columns
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

_DUCKDB_FORMATS = {"csv", "tsv", "parquet", "json", "ndjson"}


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
    ) -> None:
        super().__init__(id=id)
        self.is_stdin = path == _STDIN_SENTINEL
        self.supports_progressive = not self.is_stdin
        self.path = Path(path).expanduser() if not self.is_stdin else Path(path)
        self.fmt = fmt or (
            _READERS.get(self.path.suffix.lower(), "csv") if not self.is_stdin else "csv"
        )
        self.max_rows = max_rows
        # "--sheet 0" means index 0, not a sheet literally named "0"
        self.sheet = int(sheet) if isinstance(sheet, str) and sheet.isdigit() else sheet
        # Re-parse only known date columns on refresh.
        self._date_columns: list[str] | None = None

    def describe(self) -> str:
        return "file:<stdin>" if self.is_stdin else f"file:{self.path.name}"

    def _parse_dates(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self._date_columns is None:
            frame = _autoparse_dates(frame)
            self._date_columns = [
                str(c) for c in frame.columns if pdt.is_datetime64_any_dtype(frame[c])
            ]
            return frame
        import warnings

        for name in self._date_columns:
            if name not in frame.columns or pdt.is_datetime64_any_dtype(frame[name]):
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                frame[name] = pd.to_datetime(frame[name], errors="coerce")
        return frame

    def fetch(self, keep_raw: bool = False, force: bool = False) -> DataSet:
        if self.is_stdin:
            return self._fetch_stdin(keep_raw=keep_raw)
        if not self.path.exists():
            raise SourceError(f"no such file: {self.path}", source_id=self.id)
        raw: Any = None
        try:
            if self.fmt in _DUCKDB_FORMATS:
                frame, raw = _read_duckdb(self.path, self.fmt, self.max_rows, keep_raw)
            elif self.fmt == "excel":
                frame = _read_excel(self.path, self.sheet, self.max_rows)
            elif self.fmt == "log":
                frame = _read_log(self.path, self.max_rows)
            else:
                raise SourceError(
                    f"unknown format {self.fmt!r}; expected one of: "
                    "csv, tsv, json, ndjson, parquet, excel, log",
                    source_id=self.id,
                )
        except pd.errors.EmptyDataError as exc:
            raise SourceError(f"empty file: {self.path}", source_id=self.id) from exc
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError(
                f"failed to read {self.path} as {self.fmt}: {exc}", source_id=self.id
            ) from exc
        frame = _deduplicate_columns(frame)
        frame = self._parse_dates(frame)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind, raw=raw)

    def _fetch_stdin(self, keep_raw: bool = False) -> DataSet:
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
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        if self.fmt == "json" and not keep_raw:
            raw = None
        frame = _deduplicate_columns(frame)
        frame = self._parse_dates(frame)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind, raw=raw)


def _read_duckdb(
    path: Path, fmt: str, max_rows: int | None, keep_raw: bool = False
) -> tuple[pd.DataFrame, Any]:
    """Read a file via DuckDB's native parsers. Returns (frame, raw_json_or_None)."""
    limit = f" LIMIT {max_rows}" if max_rows is not None else ""
    path_str = str(path).replace("'", "''")
    if fmt == "csv":
        query = f"SELECT * FROM read_csv_auto('{path_str}'){limit}"
    elif fmt == "tsv":
        query = f"SELECT * FROM read_csv_auto('{path_str}', delim='\\t'){limit}"
    elif fmt == "parquet":
        query = f"SELECT * FROM '{path_str}'{limit}"
    elif fmt == "json":
        query = f"SELECT * FROM read_json_auto('{path_str}'){limit}"
    elif fmt == "ndjson":
        query = f"SELECT * FROM read_json_auto('{path_str}', format='newline_delimited'){limit}"
    else:
        raise ValueError(f"unsupported DuckDB format: {fmt}")
    conn = duckdb.connect()
    try:
        frame = conn.sql(query).df()
    finally:
        conn.close()
    # DuckDB emits a dummy column0 for zero-byte files; surface as EmptyDataError.
    if frame.empty and list(frame.columns) == ["column0"]:
        raise pd.errors.EmptyDataError(str(path))
    # Unnest JSON envelope frames (e.g. {"data": [...]}) to flat records.
    raw: Any = None
    if fmt == "json":
        if _looks_like_envelope(frame):
            frame = _unnest_json_envelope(path, max_rows)
        if keep_raw:
            raw = orjson.loads(path.read_bytes())
    return frame, raw


def _looks_like_envelope(frame: pd.DataFrame) -> bool:
    """True when a JSON frame is a single row with a single column whose
    value is a numpy array / list of dicts (i.e. an unwrapped envelope)."""
    if len(frame) != 1 or len(frame.columns) != 1:
        return False
    val = frame.iloc[0, 0]
    return isinstance(val, (list,)) or (
        hasattr(val, "__iter__") and not isinstance(val, (str, bytes, dict))
    )


def _unnest_json_envelope(path: Path, max_rows: int | None) -> pd.DataFrame:
    """Unnest a JSON envelope (e.g. {"data": [...]}) by picking the first
    list-valued top-level field, expanding each element into a row."""
    raw = orjson.loads(path.read_bytes())
    records = raw
    if isinstance(raw, dict):
        records = next((v for v in raw.values() if isinstance(v, list)), [raw])
    frame = pd.json_normalize(records)
    if max_rows is not None:
        frame = frame.head(max_rows)
    return frame


def _read_log(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    with path.open(errors="replace") as handle:
        lines = [line.rstrip("\n") for line in islice(handle, max_rows)]
    return pd.DataFrame({"line_no": range(1, len(lines) + 1), "line": lines})


def _read_excel(
    path: Path, sheet: str | int | None, max_rows: int | None
) -> pd.DataFrame:
    sheet_name = sheet if sheet is not None else 0
    return pd.read_excel(path, sheet_name=sheet_name, nrows=max_rows)


def _autoparse_dates(frame: pd.DataFrame) -> pd.DataFrame:
    import warnings

    for name in frame.columns:
        series = frame[name]
        if pdt.is_numeric_dtype(series) or pdt.is_datetime64_any_dtype(series):
            continue
        if not pdt.is_string_dtype(series):
            continue
        sample = series.dropna().head(100)
        if sample.empty:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            sample_parsed = pd.to_datetime(sample, errors="coerce")
        if sample_parsed.notna().mean() <= 0.8:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().mean() > 0.8:
            frame[name] = parsed
    return frame
