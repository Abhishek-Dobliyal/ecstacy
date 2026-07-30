from __future__ import annotations

import pytest

from ecstacy.app import EcstacyApp
from ecstacy.config.loader import load_app_config, load_dashboard
from ecstacy.core.dataset import DataSet
from ecstacy.screens.chart import ChartScreen
from ecstacy.screens.dashboard import DashboardScreen


@pytest.mark.asyncio
async def test_app_opens_dashboard():
    dashboard = load_dashboard("dashboards/ops.yaml")
    app = EcstacyApp(
        load_app_config(),
        dashboard=dashboard,
        show_splash=False,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_app_opens_source_with_refresh():
    config = load_app_config({"refresh": "2s"})
    app = EcstacyApp(
        config,
        open_spec=__import__(
            "ecstacy.sources.base", fromlist=["SourceSpec"]
        ).SourceSpec(
            kind="file", id="sample.csv", params={"path": "tests/data/sample.csv"}
        ),
        show_splash=False,
    )
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert isinstance(app.screen, ChartScreen)
        assert app.screen.refresh_interval == 2.0
        app.screen._stop_refresh()


@pytest.mark.asyncio
async def test_dashboard_panels_populate_after_fetch():
    dashboard = load_dashboard("dashboards/ops.yaml")
    app = EcstacyApp(
        load_app_config(),
        dashboard=dashboard,
        show_splash=False,
    )
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, DashboardScreen)
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert len(screen._datasets) == 1
        assert "metrics" in screen._datasets
        dataset = screen._datasets["metrics"]
        assert dataset.meta.rows > 0


@pytest.mark.asyncio
async def test_dashboard_refresh_re_renders():
    dashboard = load_dashboard("dashboards/ops.yaml")
    app = EcstacyApp(
        load_app_config(),
        dashboard=dashboard,
        show_splash=False,
    )
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, DashboardScreen)
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert len(screen._datasets) == 1
        await screen.action_refresh()
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert len(screen._datasets) == 1
        assert screen._datasets["metrics"].meta.rows > 0


@pytest.mark.asyncio
async def test_late_open_does_not_push_chart(monkeypatch):
    import time

    import pandas as pd

    from ecstacy.core.dataset import DataSet
    from ecstacy.sources.base import SourceSpec

    class _SlowSource:
        id = "slow"

        def fetch(self) -> DataSet:
            time.sleep(0.3)
            return DataSet.from_dataframe(
                pd.DataFrame({"a": [1]}), source_id="slow", kind="test"
            )

        def describe(self) -> str:
            return "test:slow"

    monkeypatch.setattr("ecstacy.app.create_source", lambda spec: _SlowSource())

    app = EcstacyApp(load_app_config(), show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        home = app.screen
        app.open_source(
            SourceSpec(kind="file", id="slow", params={"path": "x.csv"})
        )
        # Navigate away to a modal while the fetch is still running.
        from ecstacy.screens.help import HelpScreen

        app.push_screen(HelpScreen())
        await pilot.pause()
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        # The fetch completed, but the user navigated to a help modal, so no
        # ChartScreen should have been pushed on top of it.
        assert app.screen is not home
        assert not isinstance(app.screen, ChartScreen)


# -----------------------------------------------------------------------
# Progressive loading
# -----------------------------------------------------------------------

def _write_large_csv(tmp_path, rows: int = 5000):
    import pandas as pd

    path = tmp_path / "large.csv"
    pd.DataFrame(
        {"a": range(rows), "b": range(rows, rows * 2)}
    ).to_csv(path, index=False)
    return path


@pytest.mark.asyncio
async def test_progressive_loading_shows_first_batch_then_full(tmp_path):
    from ecstacy.sources.base import SourceSpec

    path = _write_large_csv(tmp_path, 5000)
    spec = SourceSpec(kind="file", id=path.name, params={"path": str(path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        # Wait for both fetches (first batch + full) to complete.
        await app.workers.wait_for_complete()
        for _ in range(12):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # After progressive loading completes, the dataset should have all
        # 5000 rows, not just the 1000-row first batch.
        assert screen.dataset.meta.rows == 5000
        screen._stop_refresh()


@pytest.mark.asyncio
async def test_progressive_loading_skipped_for_small_max_rows(tmp_path):
    from ecstacy.sources.base import SourceSpec

    path = _write_large_csv(tmp_path, 5000)
    spec = SourceSpec(
        kind="file", id=path.name, params={"path": str(path), "max_rows": 500}
    )
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # max_rows=500 < 1000 → single fetch, no progressive expansion.
        assert screen.dataset.meta.rows == 500
        screen._stop_refresh()


@pytest.mark.asyncio
async def test_progressive_loading_skipped_for_non_progressive_sources(monkeypatch):
    from httpx import Request, Response

    from ecstacy.sources.base import SourceSpec

    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200,
            request=Request("GET", "https://api.example.com/items"),
            json=[{"value": i} for i in range(2000)],
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest", id="api", params={"url": "https://api.example.com/items"}
    )
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # REST doesn't support progressive loading → single fetch, all rows.
        assert screen.dataset.meta.rows == 2000
        screen._stop_refresh()


@pytest.mark.asyncio
async def test_progressive_update_dropped_if_user_navigated_away(tmp_path):
    from ecstacy.sources.base import SourceSpec

    path = _write_large_csv(tmp_path, 5000)
    spec = SourceSpec(kind="file", id=path.name, params={"path": str(path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Pop the ChartScreen before the full fetch completes.
        # We need to wait for the first batch to arrive, then pop.
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        screen = app.screen
        if isinstance(screen, ChartScreen):
            screen.app.pop_screen()
        await pilot.pause()
        # No crash — the progressive update was silently dropped because
        # the screen is no longer the ChartScreen for this spec.
        assert not isinstance(app.screen, ChartScreen)


# -----------------------------------------------------------------------
# Dashboard streaming (item 7)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_stream_updates_panels(monkeypatch):
    import pandas as pd

    from ecstacy.config.schema import (
        DashboardConfig,
        PanelConfig,
    )
    from ecstacy.config.schema import (
        SourceSpec as SchemaSourceSpec,
    )
    from ecstacy.sources.base import Source

    class FakeStreamSource(Source):
        kind = "socket"
        supports_stream = True

        def __init__(self, id, **kwargs):
            super().__init__(id=id)
            self._call = 0

        def fetch(self, keep_raw: bool = False, force: bool = False):
            self._call += 1
            return DataSet.from_dataframe(
                pd.DataFrame({"v": [self._call]}), source_id="s", kind="socket"
            )

        async def stream(self, keep_raw: bool = False):
            for value in (10, 20, 30):
                yield DataSet.from_dataframe(
                    pd.DataFrame({"v": [value]}), source_id="s", kind="socket"
                )

    monkeypatch.setattr(
        "ecstacy.screens.dashboard.create_source", lambda spec: FakeStreamSource(id=spec.id)
    )

    dashboard = DashboardConfig(
        refresh="5s",
        sources=[SchemaSourceSpec(kind="socket", id="stream", params={})],
        panels=[PanelConfig(source="stream", viz="table")],
    )
    app = EcstacyApp(load_app_config(), dashboard=dashboard, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(12):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DashboardScreen)
        assert "stream" in screen._datasets
        # The stream should have delivered the last batch (30).
        assert screen._datasets["stream"].frame["v"].tolist() == [30]
        assert "stream" in screen._stream_sources


@pytest.mark.asyncio
async def test_dashboard_stream_and_poll_coexist(monkeypatch):
    import pandas as pd

    from ecstacy.config.schema import (
        DashboardConfig,
        PanelConfig,
    )
    from ecstacy.config.schema import (
        SourceSpec as SchemaSourceSpec,
    )
    from ecstacy.sources.base import Source

    class FakeStreamSource(Source):
        kind = "socket"
        supports_stream = True

        def __init__(self, id, **kwargs):
            super().__init__(id=id)

        def fetch(self, keep_raw: bool = False, force: bool = False):
            return DataSet.from_dataframe(
                pd.DataFrame({"v": [1]}), source_id="stream", kind="socket"
            )

        async def stream(self, keep_raw: bool = False):
            for value in (2, 3):
                yield DataSet.from_dataframe(
                    pd.DataFrame({"v": [value]}), source_id="stream", kind="socket"
                )

    monkeypatch.setattr(
        "ecstacy.screens.dashboard.create_source",
        lambda spec: FakeStreamSource(id=spec.id) if spec.kind == "socket" else _RealSource(spec),
    )

    dashboard = DashboardConfig(
        refresh="5s",
        sources=[
            SchemaSourceSpec(kind="socket", id="stream", params={}),
            SchemaSourceSpec(
                kind="file", id="sample", params={"path": "tests/data/sample.csv"}
            ),
        ],
        panels=[
            PanelConfig(source="stream", viz="table"),
            PanelConfig(source="sample", viz="table"),
        ],
    )
    app = EcstacyApp(load_app_config(), dashboard=dashboard, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(12):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DashboardScreen)
        # Both sources should have data.
        assert "stream" in screen._datasets
        assert "sample" in screen._datasets
        # Stream source went through the stream path.
        assert "stream" in screen._stream_sources
        # File source went through the poll path.
        assert len(screen._jobs) >= 1


class _RealSource:
    """Fallback for non-socket sources in the coexist test."""

    def __init__(self, spec):
        from ecstacy.sources.base import create_source as real_create

        self._real = real_create(spec)

    def fetch(self, keep_raw=False, force=False):
        return self._real.fetch(keep_raw=keep_raw)

    @property
    def id(self):
        return self._real.id

