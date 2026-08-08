from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.core.stream import consume_stream
from ecstacy.sources.base import StreamableSource


class _FakeStream(StreamableSource):
    kind = "fake"

    def __init__(self, n: int, pre_yield=None) -> None:
        super().__init__(id="fake")
        self._n = n
        self._pre_yield = pre_yield

    def fetch(self, keep_raw: bool = False, force: bool = False) -> DataSet:
        return DataSet.from_dataframe(pd.DataFrame({"v": [0]}), "s", "fake")

    async def stream(self, keep_raw: bool = False, on_status=None):
        for i in range(self._n):
            if self._pre_yield is not None:
                self._pre_yield(i)
            yield DataSet.from_dataframe(pd.DataFrame({"v": [i]}), "s", "fake")


@pytest.mark.asyncio
async def test_consume_stream_flushes_pending_on_resume():
    """Batches arriving while the screen is inactive are held and flushed on
    resume, instead of being silently dropped."""
    state = {"active": True}
    delivered: list[DataSet] = []

    def pre_yield(i: int) -> None:
        # batch 0 live, batch 1 inactive, batch 2 live (triggers resume).
        state["active"] = i != 1

    source = _FakeStream(3, pre_yield=pre_yield)
    await consume_stream(
        source,
        screen=None,
        on_data=delivered.append,
        on_error=lambda e: None,
        is_active=lambda: state["active"],
    )
    values = [ds.frame["v"].iloc[0] for ds in delivered]
    # batch 0 delivered live; batch 1 buffered then flushed on resume;
    # batch 2 delivered live. Without buffering, batch 1 would be lost.
    assert values == [0, 1, 2]


@pytest.mark.asyncio
async def test_consume_stream_drops_nothing_when_active():
    """With the screen always active, every batch is delivered in order."""
    delivered: list[DataSet] = []
    source = _FakeStream(3)
    await consume_stream(
        source,
        screen=None,
        on_data=delivered.append,
        on_error=lambda e: None,
        is_active=lambda: True,
    )
    values = [ds.frame["v"].iloc[0] for ds in delivered]
    assert values == [0, 1, 2]
