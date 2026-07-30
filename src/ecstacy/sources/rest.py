from __future__ import annotations

import time
from typing import Any

import httpx
import pandas as pd

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError


@registry.sources.register("rest")
class RestSource(Source):
    kind = "rest"

    def __init__(
        self,
        id: str,
        url: str,
        method: str = "GET",
        json_path: str | None = None,
        headers: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        timeout: float = 15.0,
        max_rows: int | None = None,
        ttl: float = 0.0,
    ) -> None:
        super().__init__(id=id)
        self.url = url
        self.method = method.upper()
        self.json_path = json_path
        self.headers = headers or {}
        self.query = query or {}
        self.timeout = timeout
        self.max_rows = max_rows
        self._ttl = ttl
        self._cache: tuple[float, DataSet] | None = None
        # built eagerly: lazy init races when fetches overlap on pool threads
        self._client: httpx.Client | None = httpx.Client(timeout=self.timeout)

    def describe(self) -> str:
        return f"rest:{self.url}"

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._cache = None

    def fetch(self, keep_raw: bool = False, force: bool = False) -> DataSet:
        if not force and self._ttl > 0 and self._cache is not None:
            expires_at, cached = self._cache
            if time.monotonic() < expires_at:
                # Serve from cache unless raw payload is needed and missing.
                if cached.meta.raw is not None or not keep_raw:
                    return cached
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        try:
            response = self._client.request(
                self.method, self.url, headers=self.headers, params=self.query
            )
            response.raise_for_status()
            try:
                raw = response.json()
            except Exception as exc:
                raise SourceError(
                    f"response is not valid JSON from {self.url}",
                    source_id=self.id,
                ) from exc
        except httpx.HTTPError as exc:
            raise SourceError(
                f"request failed for {self.url}: {exc}", source_id=self.id
            ) from exc
        records = _dig(raw, self.json_path)
        if records is None:
            raise SourceError(
                f"json_path {self.json_path!r} resolved to nothing", source_id=self.id
            )
        frame = _to_frame(records)
        if self.max_rows is not None:
            frame = frame.head(self.max_rows)
        dataset = DataSet.from_dataframe(
            frame,
            source_id=self.id,
            kind=self.kind,
            raw=raw if keep_raw else None,
        )
        if self._ttl > 0:
            self._cache = (time.monotonic() + self._ttl, dataset)
        return dataset


def _dig(payload: Any, path: str | None) -> Any:
    if not path:
        return payload
    current = payload
    for part in _path_parts(path):
        if isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else None
            except ValueError:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _path_parts(path: str) -> list[str]:
    parts = []
    for segment in path.replace("[", ".").replace("]", "").split("."):
        segment = segment.strip()
        if segment:
            parts.append(segment)
    return parts


def _to_frame(records: Any) -> pd.DataFrame:
    if isinstance(records, list):
        return pd.json_normalize(records)
    if isinstance(records, dict):
        return pd.json_normalize([records])
    return pd.DataFrame({"value": [records]})
