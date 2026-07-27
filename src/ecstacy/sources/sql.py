from __future__ import annotations

from typing import Any

import duckdb

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError


@registry.sources.register("sql")
class SqlSource(Source):
    kind = "sql"

    def __init__(self, id: str, query: str, db: str = ":memory:", **params: Any) -> None:
        super().__init__(id=id, query=query, db=db, **params)
        self.query = query
        self.db = db

    def describe(self) -> str:
        return f"sql:{self.db}"

    def fetch(self) -> DataSet:
        try:
            connection = duckdb.connect(self.db)
            try:
                frame = connection.execute(self.query).df()
            finally:
                connection.close()
        except Exception as exc:
            raise SourceError(
                f"DuckDB query failed: {exc}", source_id=self.id
            ) from exc
        return DataSet.from_dataframe(frame, source_id=self.id, kind=self.kind)
