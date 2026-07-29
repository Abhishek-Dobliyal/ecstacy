from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet


def _dataset() -> DataSet:
    frame = pd.DataFrame({"name": ["b", "a", "c"], "value": [2.0, 3.0, 1.0]})
    return DataSet.from_dataframe(frame, source_id="s", kind="test")


def _make_app():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(_dataset(), "table"))

    return _App()


async def _settle(pilot, rounds: int = 6) -> None:
    for _ in range(rounds):
        await pilot.pause()


@pytest.mark.asyncio
async def test_initial_focus_is_table_not_transform_input():
    from textual.widgets import DataTable

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        assert isinstance(app.screen.focused, DataTable)


@pytest.mark.asyncio
async def test_next_viz_keeps_screen_bindings_working():
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        assert screen.index == 0
        await pilot.press("n")
        await _settle(pilot)
        assert screen.index == 1
        # If focus were trapped in the transform-bar Input, "n" would be typed
        # into the input and the viz would not advance.
        await pilot.press("n")
        await _settle(pilot)
        assert screen.index == 2
        await pilot.press("p")
        await _settle(pilot)
        assert screen.index == 1


@pytest.mark.asyncio
async def test_chart_widget_does_not_hold_input_focus():
    from textual.widgets import Input

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        await pilot.press("n")  # line chart
        await _settle(pilot)
        assert not isinstance(app.screen.focused, Input)


@pytest.mark.asyncio
async def test_focus_returns_to_table_after_cycling_back():
    from textual.widgets import DataTable

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        await pilot.press("n")  # line
        await _settle(pilot)
        await pilot.press("p")  # back to table
        await _settle(pilot)
        assert screen.index == 0
        assert isinstance(screen.focused, DataTable)


@pytest.mark.asyncio
async def test_box_pie_heatmap_render_without_errors():
    frame = pd.DataFrame(
        {
            "region": ["us", "eu", "us", "eu", "latam", "latam"] * 4,
            "value": [10.0, 15.5, 12.0, 8.0, 20.0, 18.0] * 4,
            "count": [3, 5, 4, 2, 7, 6] * 4,
            "ratio": [0.1, 0.5, 0.3, 0.2, 0.7, 0.6] * 4,
        }
    )
    ds = DataSet.from_dataframe(frame, source_id="s", kind="test")

    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        for viz in ("box", "pie", "heatmap"):
            idx = screen.names.index(viz)
            while screen.index != idx:
                await screen.action_next_viz()
            await _settle(pilot)
            widget = screen.query_one("#viz-holder").children[0]
            rendered = widget.plt.build()
            assert "cannot render" not in rendered, f"{viz} failed to render"
            assert rendered.strip(), f"{viz} rendered empty output"


@pytest.mark.asyncio
async def test_dashboard_render_leaves_focus_clear():
    from textual.app import App

    from ecstacy.config.schema import DashboardConfig, PanelConfig, SourceSpec
    from ecstacy.core.store import Store
    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="s", params={"path": "x.csv"})],
        panels=[PanelConfig(viz="line", source="s")],
    )

    class _App(App):
        def on_mount(self):
            self.push_screen(DashboardScreen(dashboard, Store()))

    app = _App()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        screen._datasets["s"] = _dataset()
        await screen._render_panels()
        await _settle(pilot)
        assert screen.focused is None
