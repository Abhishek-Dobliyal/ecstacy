from __future__ import annotations

import pytest

from ecstacy.sources.base import SourceSpec


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


@pytest.mark.asyncio
async def test_app_open_max_rows_limits_in_tui():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen

    spec = SourceSpec(
        kind="file",
        id="sample.csv",
        params={"path": "tests/data/sample.csv", "max_rows": 2},
    )
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert isinstance(app.screen, ChartScreen)
        assert app.screen.dataset.meta.rows == 2
        app.screen._stop_refresh()


@pytest.mark.asyncio
async def test_app_open_rest_max_rows(monkeypatch):
    from httpx import Request, Response

    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen

    def mock_request(self, method, url, *, headers=None, params=None):
        return Response(
            200,
            request=Request("GET", "https://api.example.com/items"),
            json=[{"value": i} for i in range(10)],
        )

    monkeypatch.setattr("httpx.Client.request", mock_request)
    spec = SourceSpec(
        kind="rest",
        id="api",
        params={
            "url": "https://api.example.com/items",
            "max_rows": 3,
        },
    )
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert isinstance(app.screen, ChartScreen)
        assert app.screen.dataset.meta.rows == 3
        app.screen._stop_refresh()
