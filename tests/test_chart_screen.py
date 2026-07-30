from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.screens.chart import ChartScreen


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
async def test_box_proportion_heatmap_render_without_errors():
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
        for viz in ("box", "proportion", "heatmap"):
            idx = screen.names.index(viz)
            while screen.index != idx:
                await screen.action_next_viz()
            await _settle(pilot)
            widget = screen._active_widget
            rendered = widget.plt.build()
            assert "cannot render" not in rendered, f"{viz} failed to render"
            assert rendered.strip(), f"{viz} rendered empty output"


def test_transform_query_bound_to_ctrl_f():
    from ecstacy.screens.chart import ChartScreen

    keys = [binding[0] for binding in ChartScreen.BINDINGS]
    assert "ctrl+f" in keys
    assert "slash" in keys


@pytest.mark.asyncio
async def test_escape_exits_search_not_screen():
    """Pressing escape while the search input is focused unfocuses it
    instead of popping the screen back to home."""
    from textual.widgets import Input

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # Focus the table search input (via the slash binding)
        await pilot.press("/")
        await _settle(pilot)
        assert isinstance(screen.focused, Input)
        # Press escape — should unfocus the input, not pop the screen
        await pilot.press("escape")
        await _settle(pilot)
        assert app.screen is screen
        assert not isinstance(screen.focused, Input)
        # Press escape again — now it should pop back to home
        await pilot.press("escape")
        await _settle(pilot)
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_escape_exits_transform_bar_not_screen():
    """Pressing escape while the transform-bar is focused unfocuses it
    instead of popping the screen."""
    from textual.widgets import Input

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        # Focus the transform bar via ctrl+f
        await pilot.press("ctrl+f")
        await _settle(pilot)
        assert isinstance(screen.focused, Input)
        # Press escape — should unfocus, not pop
        await pilot.press("escape")
        await _settle(pilot)
        assert app.screen is screen
        assert not isinstance(screen.focused, Input)


@pytest.mark.asyncio
async def test_viz_switch_does_not_remount_widget():
    """Cycling n then p back to the same viz reuses the pooled widget."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        table_widget = screen._active_widget
        await pilot.press("n")  # line
        await _settle(pilot)
        await pilot.press("p")  # back to table
        await _settle(pilot)
        assert screen._active_widget is table_widget


@pytest.mark.asyncio
async def test_pooled_hidden_widget_display_none():
    """After switching away from a viz, its pooled widget is hidden."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        table_widget = screen._active_widget
        await pilot.press("n")  # line
        await _settle(pilot)
        assert table_widget.display is False
        assert screen._active_widget.display is True


@pytest.mark.asyncio
async def test_transform_submit_reuses_widget():
    """Submitting a transform query does not remount the active widget."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        table_widget = screen._active_widget
        screen._transform_query = "where value > 1"
        await screen._render_current()
        await _settle(pilot)
        assert screen._active_widget is table_widget


@pytest.mark.asyncio
async def test_search_bar_visible_on_table_view():
    """The search bar is visible when the table view is active."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        search_bar = screen.query_one("#search-bar")
        assert search_bar.display is True


@pytest.mark.asyncio
async def test_search_bar_hidden_on_chart_view():
    """The search bar is hidden when a non-table viz is active."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        await pilot.press("n")  # line chart
        await _settle(pilot)
        search_bar = screen.query_one("#search-bar")
        assert search_bar.display is False


@pytest.mark.asyncio
async def test_search_routed_to_table_view():
    """Typing in the search bar updates the TableView's search value."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        table = screen._active_widget
        assert hasattr(table, "set_search")
        # Focus and type in the search bar
        await pilot.press("/")
        await _settle(pilot)
        await pilot.press("a")
        await pilot.press("b")
        await _settle(pilot)
        assert table._search_value == "ab"


@pytest.mark.asyncio
async def test_search_value_survives_viz_cycle():
    """Search text persists when cycling away from table and back."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        # Type a search
        await pilot.press("/")
        await _settle(pilot)
        await pilot.press("b")
        await _settle(pilot)
        table = screen._active_widget
        assert table._search_value == "b"
        # Cycle to line chart and back
        await pilot.press("escape")  # unfocus search
        await _settle(pilot)
        await pilot.press("n")  # line
        await _settle(pilot)
        await pilot.press("p")  # back to table
        await _settle(pilot)
        search_bar = screen.query_one("#search-bar")
        assert search_bar.value == "b"
        assert screen._active_widget._search_value == "b"


@pytest.mark.asyncio
async def test_refresh_keeps_transform_query_applied():
    frame = pd.DataFrame({"region": ["us", "eu", "ap"], "value": [10.0, 150.0, 200.0]})
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
        screen._transform_query = "where value > 100"
        await screen._update_current_widget()
        await _settle(pilot)
        table_view = screen.query_one("TableView")
        assert len(table_view._frame) == 2
        assert "2 rows" in screen.query_one("#viz-holder").border_subtitle


@pytest.mark.asyncio
async def test_streaming_source_updates_dataset(monkeypatch):
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen
    from ecstacy.sources.base import Source, SourceSpec

    class FakeStreamSource(Source):
        kind = "socket"
        supports_stream = True

        def fetch(self, keep_raw: bool = False):
            raise NotImplementedError

        async def stream(self, keep_raw: bool = False):
            for value in (1, 2):
                yield DataSet.from_dataframe(
                    pd.DataFrame({"v": [value]}), source_id="s", kind="socket"
                )

    monkeypatch.setattr(
        "ecstacy.screens.chart.create_source", lambda spec: FakeStreamSource(id="s")
    )
    spec = SourceSpec(kind="socket", id="s", params={"url": "ws://example"})
    ds = DataSet.from_dataframe(pd.DataFrame({"v": [0]}), source_id="s", kind="socket")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table", spec=spec, refresh=5.0))

    app = _App()
    async with app.run_test() as pilot:
        await _settle(pilot, rounds=10)
        assert app.screen.dataset.frame["v"].tolist() == [2]


@pytest.mark.asyncio
async def test_dashboard_updates_panels_in_place():
    from textual.app import App

    from ecstacy.config.schema import DashboardConfig, PanelConfig, SourceSpec
    from ecstacy.screens.dashboard import DashboardScreen
    from ecstacy.widgets.table import TableView

    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="s", params={"path": "x.csv"})],
        panels=[PanelConfig(viz="table", source="s")],
    )

    class _App(App):
        def on_mount(self):
            self.push_screen(DashboardScreen(dashboard))

    app = _App()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        v1 = DataSet.from_dataframe(pd.DataFrame({"a": [1, 2]}), source_id="s", kind="test")
        screen._on_data("s")(v1)
        await _settle(pilot, rounds=10)
        widget = screen._panel_widgets[0]
        assert isinstance(widget, TableView)
        assert len(widget._frame) == 2
        v2 = DataSet.from_dataframe(
            pd.DataFrame({"a": [1, 2, 3]}), source_id="s", kind="test"
        )
        screen._on_data("s")(v2)
        await app.workers.wait_for_complete()
        await _settle(pilot, rounds=10)
        assert screen._panel_widgets[0] is widget  # updated in place, not rebuilt
        assert len(widget._frame) == 3


@pytest.mark.asyncio
async def test_dashboard_render_leaves_focus_clear():
    from textual.app import App

    from ecstacy.config.schema import DashboardConfig, PanelConfig, SourceSpec
    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="s", params={"path": "x.csv"})],
        panels=[PanelConfig(viz="line", source="s")],
    )

    class _App(App):
        def on_mount(self):
            self.push_screen(DashboardScreen(dashboard))

    app = _App()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        screen._datasets["s"] = _dataset()
        await screen._render_panels()
        await _settle(pilot)
        assert screen.focused is None
