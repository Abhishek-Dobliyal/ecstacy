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
    from ecstacy.sources.base import StreamableSource

    class FakeStreamSource(StreamableSource):
        kind = "socket"

        def __init__(self, id, **kwargs):
            super().__init__(id=id)
            self._call = 0

        def fetch(self, keep_raw: bool = False, force: bool = False):
            self._call += 1
            return DataSet.from_dataframe(
                pd.DataFrame({"v": [self._call]}), source_id="s", kind="socket"
            )

        async def stream(self, keep_raw: bool = False, on_status=None):
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
    from ecstacy.sources.base import StreamableSource

    class FakeStreamSource(StreamableSource):
        kind = "socket"

        def __init__(self, id, **kwargs):
            super().__init__(id=id)

        def fetch(self, keep_raw: bool = False, force: bool = False):
            return DataSet.from_dataframe(
                pd.DataFrame({"v": [1]}), source_id="stream", kind="socket"
            )

        async def stream(self, keep_raw: bool = False, on_status=None):
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


# -----------------------------------------------------------------------
# Dashboard per-panel transform cache (item 32)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_panel_cache_hits_on_same_dataset():
    """Two ticks with the same dataset object → transform runs once."""
    import pandas as pd

    from ecstacy.config.schema import (
        DashboardConfig,
        PanelConfig,
    )
    from ecstacy.config.schema import (
        SourceSpec as SchemaSourceSpec,
    )
    from ecstacy.core.dataset import DataSet
    from ecstacy.sources.base import Source

    call_count = 0

    class _CountingSource(Source):
        kind = "file"

        def __init__(self, id, **kwargs):
            super().__init__(id=id)

        def fetch(self, keep_raw=False, force=False):
            nonlocal call_count
            call_count += 1
            return DataSet.from_dataframe(
                pd.DataFrame({"region": ["us", "eu"], "value": [10, 20]}),
                source_id="s", kind="file",
            )

    from unittest import mock

    mock_source = _CountingSource(id="s")

    dashboard = DashboardConfig(
        refresh="0s",
        sources=[SchemaSourceSpec(kind="file", id="s", params={})],
        panels=[
            PanelConfig(source="s", viz="table", group_by=["region"], agg="sum"),
        ],
    )
    app = EcstacyApp(load_app_config(), dashboard=dashboard, show_splash=False)
    # Patch create_source so the dashboard uses our counting source
    with mock.patch("ecstacy.screens.dashboard.create_source", return_value=mock_source):
        async with app.run_test() as pilot:
            await app.workers.wait_for_complete()
            for _ in range(10):
                await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            assert "s" in screen._datasets
            # Initial build populates cache
            assert 0 in screen._panel_cache
            cached_id, cached_ds = screen._panel_cache[0]
            assert cached_id == screen._datasets["s"]._id
            # Manually trigger _update_panels_for with the same dataset
            screen._update_panels_for("s")
            await app.workers.wait_for_complete()
            for _ in range(6):
                await pilot.pause()
            # Cache should still hit (same dataset object)
            assert screen._panel_cache[0][0] == screen._datasets["s"]._id
            assert screen._panel_cache[0][1] is cached_ds


@pytest.mark.asyncio
async def test_panel_cache_misses_on_new_dataset():
    """Second tick delivers a new dataset → cache misses, transform re-runs."""
    import pandas as pd

    from ecstacy.config.schema import (
        DashboardConfig,
        PanelConfig,
    )
    from ecstacy.config.schema import (
        SourceSpec as SchemaSourceSpec,
    )
    from ecstacy.core.dataset import DataSet
    from ecstacy.sources.base import Source

    class _ChangingSource(Source):
        kind = "file"

        def __init__(self, id, **kwargs):
            super().__init__(id=id)
            self._n = 0

        def fetch(self, keep_raw=False, force=False):
            self._n += 1
            return DataSet.from_dataframe(
                pd.DataFrame({"region": ["us", "eu"], "value": [self._n * 10, 20]}),
                source_id="s", kind="file",
            )

    mock_source = _ChangingSource(id="s")

    dashboard = DashboardConfig(
        refresh="0s",
        sources=[SchemaSourceSpec(kind="file", id="s", params={})],
        panels=[
            PanelConfig(source="s", viz="table", group_by=["region"], agg="sum"),
        ],
    )
    app = EcstacyApp(load_app_config(), dashboard=dashboard, show_splash=False)
    from unittest import mock

    with mock.patch("ecstacy.screens.dashboard.create_source", return_value=mock_source):
        async with app.run_test() as pilot:
            await app.workers.wait_for_complete()
            for _ in range(10):
                await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            first_cached = screen._panel_cache.get(0)
            assert first_cached is not None
            # Deliver a new dataset (simulating a refresh tick)
            new_ds = mock_source.fetch()
            screen._datasets["s"] = new_ds
            screen._update_panels_for("s")
            await app.workers.wait_for_complete()
            for _ in range(6):
                await pilot.pause()
            # Cache should have been updated with the new dataset id
            assert screen._panel_cache[0][0] == new_ds._id
            assert screen._panel_cache[0][1] is not first_cached[1]


def test_build_transformed_where_only_reuses_schema():
    """where-only transform should reuse the upstream schema."""
    import pandas as pd

    from ecstacy.config.schema import PanelConfig
    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.dashboard import DashboardScreen

    ds = DataSet.from_dataframe(
        pd.DataFrame({"region": ["us", "eu", "ap"], "value": [10.0, 20.0, 30.0]}),
        source_id="s", kind="test",
    )
    screen = DashboardScreen.__new__(DashboardScreen)
    panel = PanelConfig(source="s", viz="table", where="value > 15")
    from ecstacy.core.transforms import Transform

    frame = Transform(where="value > 15").apply(ds.frame)
    result = screen._build_transformed(panel, ds, frame)
    # Schema should be the same object as the upstream schema
    assert result.schema is ds.schema
    assert result.meta.rows == 2


def test_build_transformed_select_only_subsets_schema():
    """select-only transform should produce a schema subset."""
    import pandas as pd

    from ecstacy.config.schema import PanelConfig
    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.dashboard import DashboardScreen

    ds = DataSet.from_dataframe(
        pd.DataFrame({"region": ["us", "eu"], "value": [10.0, 20.0], "count": [1, 2]}),
        source_id="s", kind="test",
    )
    screen = DashboardScreen.__new__(DashboardScreen)
    panel = PanelConfig(source="s", viz="table", select=["region", "value"])
    from ecstacy.core.transforms import Transform

    frame = Transform(select=["region", "value"]).apply(ds.frame)
    result = screen._build_transformed(panel, ds, frame)
    assert result.schema.columns == ["region", "value"]
    assert "count" not in result.schema.columns
    assert result.schema.roles["region"] == ds.schema.roles["region"]
    assert result.schema.roles["value"] == ds.schema.roles["value"]


@pytest.mark.asyncio
async def test_dashboard_on_error_skipped_when_detached():
    """_on_error returns early when the screen is no longer attached,
    preventing notify on a popped screen."""
    from ecstacy.config.schema import DashboardConfig, PanelConfig, SourceSpec
    from ecstacy.sources.base import SourceError

    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="s", params={"path": "tests/data/sample.csv"})],
        panels=[PanelConfig(source="s", viz="table")],
    )
    app = EcstacyApp(load_app_config(), dashboard=dashboard, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, DashboardScreen)
        # Pop the screen so it's detached.
        app.pop_screen()
        for _ in range(4):
            await pilot.pause()
        notifications_before = len(app._notifications) if hasattr(app, "_notifications") else 0
        # Calling _on_error on a detached screen should be a no-op.
        screen._on_error("s")(SourceError("boom", source_id="s"))
        # No new notification was emitted.
        notifications_after = len(app._notifications) if hasattr(app, "_notifications") else 0
        assert notifications_after == notifications_before

