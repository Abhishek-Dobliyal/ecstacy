from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import pandas as pd

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import SourceError, StreamableSource


def _records_to_frame(records: list[Any]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    if all(isinstance(r, dict) for r in records):
        return pd.json_normalize(records)
    return pd.DataFrame({"value": records})


@registry.sources.register("socket")
class SocketSource(StreamableSource):
    kind = "socket"

    def __init__(
        self,
        id: str,
        url: str,
        max_messages: int = 100,
        timeout: float = 5.0,
        reconnect: bool = True,
        reconnect_attempts: int | None = None,
        reconnect_base: float = 1.0,
        reconnect_max: float = 30.0,
    ) -> None:
        super().__init__(id=id)
        self.url = url
        self.max_messages = max_messages
        self.timeout = timeout
        self.reconnect = reconnect
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_base = reconnect_base
        self.reconnect_max = reconnect_max

    def describe(self) -> str:
        return f"socket:{self.url}"

    def fetch(self, keep_raw: bool = False, force: bool = False) -> DataSet:
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
            frame, source_id=self.id, kind=self.kind, raw=records if keep_raw else None
        )

    async def stream(
        self,
        keep_raw: bool = False,
        on_status: Callable[[str], None] | None = None,
    ) -> AsyncIterator[DataSet]:
        import orjson
        import websockets

        attempts = 0
        while True:
            try:
                async with websockets.connect(
                    self.url, open_timeout=self.timeout
                ) as ws:
                    attempts = 0  # a successful connect resets the backoff
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
                                    raw=list(records) if keep_raw else None,
                                )
                                records.clear()
                            continue
                        except websockets.ConnectionClosed:
                            break  # drop to reconnect logic below
                        records.append(_parse_message(raw, orjson))
                        if len(records) >= self.max_messages:
                            yield DataSet.from_dataframe(
                                _records_to_frame(records),
                                source_id=self.id,
                                kind=self.kind,
                                raw=list(records) if keep_raw else None,
                            )
                            records.clear()
                # Clean close of the connection: reconnect if enabled.
                if not self.reconnect:
                    return
                delay = min(self.reconnect_base, self.reconnect_max)
                if on_status:
                    on_status(f"reconnecting in {delay:.0f}s")
                await asyncio.sleep(delay)
                continue
            except asyncio.CancelledError:
                raise  # never retry on cancellation
            except Exception as exc:
                if not self.reconnect:
                    raise SourceError(
                        f"stream failed for {self.url}: {exc}", source_id=self.id
                    ) from exc
                attempts += 1
                if (
                    self.reconnect_attempts is not None
                    and attempts > self.reconnect_attempts
                ):
                    raise SourceError(
                        f"stream failed for {self.url} after "
                        f"{self.reconnect_attempts} reconnect attempt(s): {exc}",
                        source_id=self.id,
                    ) from exc
                delay = min(
                    self.reconnect_base * (2 ** (attempts - 1)), self.reconnect_max
                )
                if on_status:
                    on_status(
                        f"reconnecting in {delay:.0f}s (attempt {attempts})"
                    )
                await asyncio.sleep(delay)
                continue

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
