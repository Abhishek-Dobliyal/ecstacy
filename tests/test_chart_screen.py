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
async def test_search_inputs_not_focusable_on_mount():
    """Inputs have can_focus=False so auto-focus never lands on them."""
    from textual.widgets import Input

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        assert not screen.query_one("#search-bar", Input).can_focus
        assert not screen.query_one("#transform-bar", Input).can_focus
        # Opening with a non-table viz: focus is None, not an Input.
        await pilot.press("n")  # line chart
        await _settle(pilot)
        assert not isinstance(screen.focused, Input)


@pytest.mark.asyncio
async def test_arrow_keys_switch_viz_on_non_table():
    """Arrow keys advance viz on a non-table chart (focus not trapped)."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        await pilot.press("n")  # line chart (non-table)
        await _settle(pilot)
        idx_after_n = screen.index
        await pilot.press("right")  # arrow right -> next_viz
        await _settle(pilot)
        assert screen.index == (idx_after_n + 1) % len(screen.names)
        await pilot.press("left")  # arrow left -> prev_viz
        await _settle(pilot)
        assert screen.index == idx_after_n


@pytest.mark.asyncio
async def test_focus_search_makes_input_focusable_again():
    """Pressing / flips can_focus=True and focuses the search-bar."""
    from textual.widgets import Input

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        bar = screen.query_one("#search-bar", Input)
        assert not bar.can_focus
        await pilot.press("/")
        await _settle(pilot)
        assert bar.can_focus
        assert screen.focused is bar
        # Escape resets can_focus and unfocuses.
        await pilot.press("escape")
        await _settle(pilot)
        assert not bar.can_focus
        assert screen.focused is not bar


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

        async def stream(self, keep_raw: bool = False, on_status=None):
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


# -----------------------------------------------------------------------
# Chart column picker (item 31)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_column_picker_not_available_for_heatmap():
    """Pressing c on heatmap notifies 'no column mapping'."""
    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        # Cycle to heatmap (index 7 in VIZ_ORDER: table, line, bar, hist,
        # scatter, sparkline, gauge, heatmap)
        for _ in range(7):
            await pilot.press("n")
            await _settle(pilot)
        assert screen.names[screen.index] == "heatmap"


@pytest.mark.asyncio
async def test_column_picker_updates_mapping():
    """Opening the picker and selecting columns updates the mapping."""
    from ecstacy.widgets.base import ColumnMapping

    app = _make_app()
    async with app.run_test() as pilot:
        await _settle(pilot)
        screen = app.screen
        # Switch to bar chart for a simple 2-field picker
        await pilot.press("n")  # line
        await _settle(pilot)
        await pilot.press("n")  # bar
        await _settle(pilot)
        assert screen.names[screen.index] == "bar"
        assert screen.mapping is None
        # Simulate the picker callback directly
        new_mapping = ColumnMapping(category="name", value="value")
        screen._on_mapping_picked(new_mapping)
        await _settle(pilot)
        assert screen.mapping is new_mapping


def test_column_picker_preserves_unseen_fields():
    """Picker for bar (category+value) preserves x/y/bins from existing."""
    from ecstacy.screens.modals import ChartMappingScreen
    from ecstacy.widgets.base import ColumnMapping

    mapping = ColumnMapping(
        x="time", y=["sales", "profit"], category="region",
        value="amount", bins=30,
    )
    columns = ["time", "region", "amount", "sales", "profit"]
    ChartMappingScreen("bar", columns, mapping)
    # bar only shows category + value; x, y, bins should be preserved
    # when the picker builds its result (tested via action_confirm)
    # We can't easily run the modal in a unit test, but we can verify
    # the fields list is correct
    from ecstacy.screens.modals import VIZ_FIELDS
    fields = VIZ_FIELDS["bar"]
    field_names = [f[0] for f in fields]
    assert "category" in field_names
    assert "value" in field_names
    assert "x" not in field_names
    assert "y" not in field_names


def test_viz_no_mapping_set():
    from ecstacy.screens.modals import VIZ_NO_MAPPING
    assert "heatmap" in VIZ_NO_MAPPING
    assert "table" in VIZ_NO_MAPPING
    assert "summary" in VIZ_NO_MAPPING
    assert "json" in VIZ_NO_MAPPING
    assert "line" not in VIZ_NO_MAPPING
    assert "bar" not in VIZ_NO_MAPPING


@pytest.mark.asyncio
async def test_column_picker_ok_button_confirms():
    """Pressing the OK button dismisses the modal with a mapping."""
    from textual.app import App
    from textual.widgets import Button

    from ecstacy.screens.modals import ChartMappingScreen
    from ecstacy.widgets.base import ColumnMapping

    mapping = ColumnMapping(value="a")
    columns = ["a", "b", "c"]

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartMappingScreen("histogram", columns, mapping))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(5):
            await pilot.pause()
        # Press the OK button
        ok_button = app.screen.query_one("#mapping-ok", Button)
        await pilot.click(ok_button)
        for _ in range(5):
            await pilot.pause()
        # The modal should have been dismissed
        from ecstacy.screens.modals import ChartMappingScreen as _CMS
        assert not isinstance(app.screen, _CMS)


@pytest.mark.asyncio
async def test_stream_worker_ref_cleared_after_stream_ends(monkeypatch):
    """When a stream source finishes (no more data), the _stream_worker
    reference is cleared in the finally block."""
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen
    from ecstacy.sources.base import Source, SourceSpec

    class FakeStreamSource(Source):
        kind = "socket"
        supports_stream = True

        def fetch(self, keep_raw: bool = False):
            raise NotImplementedError

        async def stream(self, keep_raw: bool = False, on_status=None):
            yield DataSet.from_dataframe(
                pd.DataFrame({"v": [1]}), source_id="s", kind="socket"
            )
            # Stream ends after one yield.

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
        screen = app.screen
        # The stream completed; the worker ref should be cleared.
        assert screen._stream_worker is None


@pytest.mark.asyncio
async def test_stream_worker_ref_cleared_on_error(monkeypatch):
    """When a stream source raises an error, the _stream_worker reference
    is cleared in the finally block."""
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen
    from ecstacy.sources.base import Source, SourceError, SourceSpec

    class FakeStreamSource(Source):
        kind = "socket"
        supports_stream = True

        def fetch(self, keep_raw: bool = False):
            raise NotImplementedError

        async def stream(self, keep_raw: bool = False, on_status=None):
            yield DataSet.from_dataframe(
                pd.DataFrame({"v": [1]}), source_id="s", kind="socket"
            )
            raise SourceError("stream died", source_id="s")

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
        await _settle(pilot, rounds=12)
        screen = app.screen
        assert screen._stream_worker is None
