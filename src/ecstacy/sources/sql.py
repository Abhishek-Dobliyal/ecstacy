from __future__ import annotations

from typing import Any

import duckdb

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError


@registry.sources.register("sql")
class SqlSource(Source):
    kind = "sql"

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
        self._conn: duckdb.DuckDBPyConnection | None = None

    def describe(self) -> str:
        return f"sql:{self.db}"

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        # Cache file-backed connections across refresh ticks. :memory:
        # databases intentionally stay fresh per fetch so self-contained
        # queries (incl. DDL) behave the same on every tick.
        if self.db == ":memory:":
            return duckdb.connect(self.db)
        if self._conn is None:
            self._conn = duckdb.connect(self.db)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch(self) -> DataSet:
        connection = self._get_connection()
        try:
            frame = connection.execute(self.query).df()
        except Exception as exc:
            raise SourceError(
                f"DuckDB query failed: {exc}", source_id=self.id
            ) from exc
        finally:
            if self.db == ":memory:":
                connection.close()
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind)
