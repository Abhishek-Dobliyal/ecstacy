from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from typing import Any

import pandas as pd
from pandas.api import types as pdt

_instance_counter = count()

Role = str
TIME: Role = "time"
CATEGORY: Role = "category"
VALUE: Role = "value"


class EcstacyError(Exception):
    """Base exception for all Ecstacy errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Schema:
    columns: list[str] = field(default_factory=list)
    dtypes: dict[str, str] = field(default_factory=dict)
    roles: dict[str, Role] = field(default_factory=dict)

    def by_role(self, role: Role) -> list[str]:
        return [c for c in self.columns if self.roles.get(c) == role]

    @property
    def time_columns(self) -> list[str]:
        return self.by_role(TIME)

    @property
    def value_columns(self) -> list[str]:
        return self.by_role(VALUE)

    @property
    def category_columns(self) -> list[str]:
        return self.by_role(CATEGORY)


@dataclass
class Meta:
    source_id: str
    kind: str
    rows: int = 0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw: Any = None


@dataclass
class DataSet:
    frame: pd.DataFrame
    schema: Schema
    meta: Meta

    _id: int = field(default_factory=lambda: next(_instance_counter), init=False, repr=False)

    @classmethod
    def from_dataframe(
        cls,
        frame: pd.DataFrame,
        source_id: str,
        kind: str,
        raw: Any = None,
        diet: bool = True,
    ) -> DataSet:
        # Defensive dedupe for sources that produce duplicate column names.
        frame = deduplicate_columns(frame)
        if diet:
            frame = _diet_dtypes(frame)
        schema = infer_schema(frame)
        meta = Meta(source_id=source_id, kind=kind, rows=len(frame), raw=raw)
        return cls(frame=frame, schema=schema, meta=meta)


def deduplicate_columns(frame: pd.DataFrame) -> pd.DataFrame:
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


def infer_schema(frame: pd.DataFrame) -> Schema:
    columns = [str(c) for c in frame.columns]
    dtypes: dict[str, str] = {}
    roles: dict[str, Role] = {}
    for name in columns:
        series = frame[name]
        dtypes[name] = str(series.dtype)
        roles[name] = _infer_role(series)
    return Schema(columns=columns, dtypes=dtypes, roles=roles)


def _infer_role(series: pd.Series) -> Role:
    if pdt.is_datetime64_any_dtype(series):
        return TIME
    if pdt.is_bool_dtype(series):
        return CATEGORY
    if pdt.is_numeric_dtype(series):
        return VALUE
    return CATEGORY


def _diet_dtypes(frame: pd.DataFrame) -> pd.DataFrame:
    """Downcast integers/floats, convert low-cardinality objects to category."""
    if frame.empty:
        return frame
    changed = False
    new_cols: dict[str, pd.Series] = {}
    for name in frame.columns:
        series = frame[name]
        if pdt.is_datetime64_any_dtype(series) or pdt.is_bool_dtype(series):
            continue
        if pdt.is_integer_dtype(series):
            downcasted = pd.to_numeric(series, downcast="integer")
            if downcasted.dtype != series.dtype:
                new_cols[name] = downcasted
                changed = True
        elif pdt.is_float_dtype(series):
            downcasted = pd.to_numeric(series, downcast="float")
            if downcasted.dtype != series.dtype:
                new_cols[name] = downcasted
                changed = True
        elif pdt.is_object_dtype(series) or pdt.is_string_dtype(series):
            # Skip the cheap "is it all missing" case to avoid surprises.
            non_null = series.dropna()
            if len(non_null) > 0 and non_null.nunique() / len(non_null) < 0.5:
                new_cols[name] = series.astype("category")
                changed = True
    if not changed:
        return frame
    return frame.assign(**new_cols)
