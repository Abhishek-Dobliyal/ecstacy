from __future__ import annotations

import pytest

from ecstacy.app import EcstacyApp
from ecstacy.config.loader import load_app_config, load_dashboard
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

