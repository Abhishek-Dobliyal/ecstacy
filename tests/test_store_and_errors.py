from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.core.store import Store
from ecstacy.sources.base import SourceSpec


def _make_dataset(source_id: str = "s", rows: int = 3) -> DataSet:
    df = pd.DataFrame({"a": list(range(rows))})
    return DataSet.from_dataframe(df, source_id=source_id, kind="test")


def test_store_set_and_get():
    store = Store()
    ds = _make_dataset("metrics")
    store.set("metrics", ds)
    assert store.get("metrics") is ds
    assert store.get("missing") is None


def test_store_ids():
    store = Store()
    store.set("a", _make_dataset("a"))
    store.set("b", _make_dataset("b"))
    assert set(store.ids()) == {"a", "b"}


def test_store_subscribe_receives_updates():
    store = Store()
    received: list[tuple[str, DataSet]] = []
    store.subscribe(lambda sid, ds: received.append((sid, ds)))
    store.set("metrics", _make_dataset("metrics"))
    assert len(received) == 1
    assert received[0][0] == "metrics"


def test_store_unsubscribe_stops_notifications():
    store = Store()
    received: list[tuple[str, DataSet]] = []
    unsub = store.subscribe(lambda sid, ds: received.append((sid, ds)))
    unsub()
    store.set("metrics", _make_dataset("metrics"))
    assert len(received) == 0


def test_store_set_overwrites_previous():
    store = Store()
    store.set("metrics", _make_dataset("metrics", rows=2))
    store.set("metrics", _make_dataset("metrics", rows=5))
    assert store.get("metrics").meta.rows == 5


@pytest.mark.asyncio
async def test_app_error_ui_missing_file():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config

    app = EcstacyApp(
        load_app_config(),
        open_spec=SourceSpec(
            kind="file", id="missing", params={"path": "/does/not/exist.csv"}
        ),
        show_splash=False,
    )
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(5):
            await pilot.pause()


@pytest.mark.asyncio
async def test_app_error_ui_bad_rest_url():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config

    app = EcstacyApp(
        load_app_config(),
        open_spec=SourceSpec(
            kind="rest",
            id="bad",
            params={"url": "http://127.0.0.1:1/nope"},
        ),
        show_splash=False,
    )
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(5):
            await pilot.pause()
