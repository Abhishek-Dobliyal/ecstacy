from __future__ import annotations

import sys
from itertools import islice
from pathlib import Path
from typing import Any

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
        # which columns the first fetch identified as dates; refresh ticks
        # re-parse only these instead of re-sampling every string column
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
                frame, raw = _read_json(self.path, self.max_rows)
            elif self.fmt == "excel":
                frame = _read_excel(self.path, self.sheet, self.max_rows)
            else:
                frame = _read_log(self.path, self.max_rows)
        except pd.errors.EmptyDataError as exc:
            raise SourceError(f"empty file: {self.path}", source_id=self.id) from exc
        except Exception as exc:
            raise SourceError(
                f"failed to read {self.path} as {self.fmt}: {exc}", source_id=self.id
            ) from exc
        frame = _deduplicate_columns(frame)
        frame = self._parse_dates(frame)
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
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        frame = _deduplicate_columns(frame)
        frame = self._parse_dates(frame)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind, raw=raw)


def _read_parquet(path: Path, max_rows: int | None) -> pd.DataFrame:
    if max_rows is None:
        return pd.read_parquet(path)
    import pyarrow.parquet as pq

    # stream the first batch only: memory stays O(max_rows) not O(file size)
    for batch in pq.ParquetFile(path).iter_batches(batch_size=max_rows):
        return batch.to_pandas().head(max_rows)
    return pd.read_parquet(path)  # 0-row file: keep the schema


def _read_json(path: Path, max_rows: int | None = None) -> tuple[pd.DataFrame, Any]:
    raw = orjson.loads(path.read_bytes())
    records = raw
    if isinstance(raw, dict):
        records = next((v for v in raw.values() if isinstance(v, list)), [raw])
    frame = pd.json_normalize(records)
    if max_rows is not None:
        frame = frame.head(max_rows)
    return frame, raw


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
