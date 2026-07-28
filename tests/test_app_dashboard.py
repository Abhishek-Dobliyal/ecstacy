from __future__ import annotations

import pytest

from ecstacy.app import EcstacyApp
from ecstacy.config.loader import load_app_config, load_dashboard
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

