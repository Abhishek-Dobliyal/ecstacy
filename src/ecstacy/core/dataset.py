from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from pandas.api import types as pdt

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
    status: str = "ok"
    detail: str = ""
    raw: Any = None


@dataclass
class DataSet:
    frame: pd.DataFrame
    schema: Schema
    meta: Meta

    @classmethod
    def from_dataframe(
        cls, frame: pd.DataFrame, source_id: str, kind: str, raw: Any = None
    ) -> DataSet:
        schema = infer_schema(frame)
        meta = Meta(source_id=source_id, kind=kind, rows=len(frame), raw=raw)
        return cls(frame=frame, schema=schema, meta=meta)


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
