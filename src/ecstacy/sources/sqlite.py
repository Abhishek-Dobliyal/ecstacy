from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError


@registry.sources.register("sqlite")
class SqliteSource(Source):
    kind = "sqlite"

    def __init__(
        self,
        id: str,
        query: str,
        db: str = ":memory:",
        max_rows: int | None = None,
        **params: Any,
    ) -> None:
        super().__init__(id=id, query=query, db=db, **params)
        self.query = query
        self.db = db
        self.max_rows = max_rows

    def describe(self) -> str:
        return f"sqlite:{self.db}"

    def fetch(self) -> DataSet:
        try:
            connection = sqlite3.connect(self.db)
            try:
                frame = pd.read_sql_query(self.query, connection)
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise SourceError(
                f"SQLite query failed: {exc}", source_id=self.id
            ) from exc
        except Exception as exc:
            raise SourceError(
                f"SQLite read failed: {exc}", source_id=self.id
            ) from exc
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind)
