from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from textual.widgets import Input as _Input

from ecstacy.core.dataset import DataSet
from ecstacy.screens.modals.export import ExportScreen
from ecstacy.sources.base import SourceSpec


def _tmp_csv(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    f.write(content)
    f.flush()
    return Path(f.name)


def _dummy_dataset(rows: int = 3, source_id: str = "test") -> DataSet:
    return DataSet.from_dataframe(
        pd.DataFrame({"a": list(range(rows)), "b": list(range(rows))}),
        source_id=source_id,
        kind="file",
    )


@pytest.mark.asyncio
async def test_file_open_loads_chart_screen():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen

    csv_path = _tmp_csv("a,b\n1,2\n3,4\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert isinstance(app.screen, ChartScreen)
        assert app.screen.dataset.meta.rows == 2


@pytest.mark.asyncio
async def test_viz_cycle_pools_widgets():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen

    csv_path = _tmp_csv("a,b\n1,2\n3,4\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # Cycle forward through all viz types and back.
        start = screen.index
        await pilot.press("n")
        await pilot.pause()
        assert screen.index != start
        assert screen._active_widget is not None
        assert len(screen._viz_pool) >= 1


@pytest.mark.asyncio
async def test_search_bar_visible_only_on_table():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen

    csv_path = _tmp_csv("a,b\n1,2\n3,4\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, viz="line", show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        from textual.widgets import Input
        search_bar = screen.query_one("#search-bar", Input)
        assert search_bar.display is False


@pytest.mark.asyncio
async def test_export_modal_dismiss():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config

    csv_path = _tmp_csv("a,b\n1,2\n3,4\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        app.push_screen(ExportScreen())
        await pilot.pause()
        assert isinstance(app.screen, ExportScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen


@pytest.mark.asyncio
async def test_viz_cycle_full_loop():
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets import viz_names

    names = viz_names()
    csv_path = _tmp_csv("a,b\n1,2\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        start_idx = screen.index
        for _ in range(len(names)):
            await pilot.press("n")
            await pilot.pause(delay=0.05)
        assert screen.index == start_idx


@pytest.mark.asyncio
async def test_export_from_chart_screen(tmp_path):
    from ecstacy.app import EcstacyApp
    from ecstacy.config.loader import load_app_config

    csv_path = _tmp_csv("a,b\n1,2\n3,4\n")
    spec = SourceSpec(kind="file", id="test", params={"path": str(csv_path)})
    app = EcstacyApp(load_app_config(), open_spec=spec, show_splash=False)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ExportScreen)
        export_path = tmp_path / "out.csv"
        path_input = app.screen.query_one("#export-path", _Input)
        path_input.value = str(export_path)
        await pilot.press("enter")
        await pilot.pause()
        fmt_input = app.screen.query_one("#export-fmt", _Input)
        fmt_input.value = "csv"
        await pilot.press("enter")
        await pilot.pause()
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert export_path.exists()
        content = export_path.read_text()
        assert "a,b" in content
        assert "1,2" in content
