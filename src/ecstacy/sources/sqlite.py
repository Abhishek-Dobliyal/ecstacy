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
        self._conn: sqlite3.Connection | None = None

    def describe(self) -> str:
        return f"sqlite:{self.db}"

    def _get_connection(self) -> sqlite3.Connection:
        if self.db == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(self.db)
            return self._conn
        return sqlite3.connect(self.db)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch(self) -> DataSet:
        conn: sqlite3.Connection | None = None
        owns_connection = False
        try:
            if self.db == ":memory:":
                conn = self._get_connection()
            else:
                conn = self._get_connection()
                owns_connection = True
            frame = pd.read_sql_query(self.query, conn)
        except sqlite3.Error as exc:
            raise SourceError(
                f"SQLite query failed: {exc}", source_id=self.id
            ) from exc
        except Exception as exc:
            raise SourceError(
                f"SQLite read failed: {exc}", source_id=self.id
            ) from exc
        finally:
            if owns_connection and conn is not None:
                conn.close()
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind)
