from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pandas as pd

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source, SourceError


def _records_to_frame(records: list[Any]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    if all(isinstance(r, dict) for r in records):
        return pd.json_normalize(records)
    return pd.DataFrame({"value": records})


@registry.sources.register("socket")
class SocketSource(Source):
    kind = "socket"
    supports_stream = True

    def __init__(
        self,
        id: str,
        url: str,
        max_messages: int = 100,
        timeout: float = 5.0,
        **params: Any,
    ) -> None:
        super().__init__(id=id, url=url, **params)
        self.url = url
        self.max_messages = max_messages
        self.timeout = timeout

    def describe(self) -> str:
        return f"socket:{self.url}"

    def fetch(self) -> DataSet:
        try:
            records = asyncio.run(self._collect())
        except Exception as exc:
            raise SourceError(
                f"failed to read from {self.url}: {exc}", source_id=self.id
            ) from exc
        if not records:
            raise SourceError(f"no messages received from {self.url}", source_id=self.id)
        frame = _records_to_frame(records)
        return DataSet.from_dataframe(
            frame, source_id=self.id, kind=self.kind, raw=records
        )

    async def stream(self) -> AsyncIterator[DataSet]:
        import orjson
        import websockets

        try:
            async with websockets.connect(
                self.url, open_timeout=self.timeout
            ) as ws:
                records: list[Any] = []
                while True:
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=self.timeout
                        )
                    except TimeoutError:
                        if records:
                            yield DataSet.from_dataframe(
                                _records_to_frame(records),
                                source_id=self.id,
                                kind=self.kind,
                                raw=list(records),
                            )
                            records.clear()
                        continue
                    except websockets.ConnectionClosed:
                        break
                    records.append(_parse_message(raw, orjson))
                    if len(records) >= self.max_messages:
                        yield DataSet.from_dataframe(
                            _records_to_frame(records),
                            source_id=self.id,
                            kind=self.kind,
                            raw=list(records),
                        )
                        records.clear()
        except Exception as exc:
            raise SourceError(
                f"stream failed for {self.url}: {exc}", source_id=self.id
            ) from exc

    async def _collect(self) -> list[Any]:
        import orjson
        import websockets

        records: list[Any] = []
        async with websockets.connect(self.url, open_timeout=self.timeout) as ws:
            while len(records) < self.max_messages:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                except TimeoutError:
                    break
                except websockets.ConnectionClosed:
                    break
                records.append(_parse_message(raw, orjson))
        return records


def _parse_message(raw: Any, orjson) -> Any:
    if isinstance(raw, (bytes, bytearray)):
        try:
            return orjson.loads(raw)
        except Exception:
            return raw.decode(errors="replace")
    if isinstance(raw, str):
        try:
            return orjson.loads(raw)
        except Exception:
            return raw
    return raw
