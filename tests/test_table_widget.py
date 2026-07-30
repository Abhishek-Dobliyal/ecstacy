from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.config import defaults
from ecstacy.widgets.table import filter_frame, sort_frame_multi


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["us", "eu", "us", "eu"],
            "value": [10.0, 15.0, 12.0, 8.0],
            "count": [3, 5, 4, 2],
        }
    )


def test_filter_frame_no_search_returns_all():
    result = filter_frame(_sample(), "")
    assert len(result) == 4


def test_filter_frame_substring_match():
    result = filter_frame(_sample(), "eu")
    assert len(result) == 2
    assert set(result["region"]) == {"eu"}


def test_filter_frame_case_insensitive():
    result = filter_frame(_sample(), "US")
    assert len(result) == 2


def test_filter_frame_no_match():
    result = filter_frame(_sample(), "xyz")
    assert len(result) == 0


def test_sort_frame_multi_ascending():
    result = sort_frame_multi(_sample(), [("value", True)])
    assert list(result["value"]) == [8.0, 10.0, 12.0, 15.0]


def test_sort_frame_multi_descending():
    result = sort_frame_multi(_sample(), [("value", False)])
    assert list(result["value"]) == [15.0, 12.0, 10.0, 8.0]


def test_filter_then_sort():
    filtered = filter_frame(_sample(), "us")
    result = sort_frame_multi(filtered, [("value", False)])
    assert list(result["value"]) == [12.0, 10.0]


def test_sort_frame_multi_covers_all_rows_not_just_head():
    rows = []
    for i in range(2000):
        rows.append({"region": "r" + str(i), "value": float(2000 - i)})
    frame = pd.DataFrame(rows)
    sorted_frame = sort_frame_multi(frame, [("value", True)])
    capped = sorted_frame.head(defaults.DEFAULT_MAX_ROWS)
    assert capped.iloc[0]["value"] == 1.0
    assert capped.iloc[-1]["value"] == float(defaults.DEFAULT_MAX_ROWS)


def test_sort_frame_multi_two_columns():
    frame = pd.DataFrame(
        {"region": ["us", "eu", "us", "eu"], "value": [10, 15, 5, 20]}
    )
    result = sort_frame_multi(frame, [("region", True), ("value", False)])
    assert list(result["region"]) == ["eu", "eu", "us", "us"]
    assert list(result["value"]) == [20, 15, 10, 5]


def test_sort_frame_multi_empty_returns_unchanged():
    frame = _sample()
    result = sort_frame_multi(frame, [])
    assert len(result) == 4


def test_sort_frame_multi_missing_column_ignored():
    frame = _sample()
    result = sort_frame_multi(frame, [("missing", True), ("value", True)])
    assert list(result["value"]) == [8.0, 10.0, 12.0, 15.0]


def test_table_get_current_view_applies_sort_and_filter():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    tv._sort_cols = [("value", False)]
    tv._search_value = "us"
    view = tv._get_current_view()
    assert list(view["value"]) == [12.0, 10.0]
    assert "region" in view.columns


def test_table_get_current_view_respects_hidden_columns():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    tv._hidden_columns = {"count"}
    view = tv._get_current_view()
    assert "count" not in view.columns
    assert "value" in view.columns


def test_filter_cached_matches_filter_frame():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    expected = filter_frame(_sample(), "US")
    result = tv._filter_cached(tv._frame, "US")
    assert list(result["value"]) == list(expected["value"])


def test_filter_cached_reuses_cached_strings():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    first = tv._filter_cached(tv._frame, "us")
    assert len(first) == 2
    cached = tv._string_frame
    assert cached is not None
    second = tv._filter_cached(tv._frame, "eu")
    assert len(second) == 2
    assert tv._string_frame is cached


def test_filter_cached_respects_sorted_index():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    sorted_frame = sort_frame_multi(tv._frame, [("value", False)])
    result = tv._filter_cached(sorted_frame, "us")
    assert list(result["value"]) == [12.0, 10.0]


def test_string_cache_invalidates_on_frame_swap():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    frame_a = _sample()
    tv._frame = frame_a
    tv._filter_cached(frame_a, "us")
    assert tv._string_frame is not None
    assert tv._string_frame_source is frame_a
    # new frame object (as on refresh) → identity check invalidates cache
    frame_b = _sample()
    tv._frame = frame_b
    tv._filter_cached(frame_b, "us")
    assert tv._string_frame_source is frame_b


def test_set_data_preserves_sort_and_hidden_on_same_columns():
    from ecstacy.core.dataset import DataSet
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._columns_signature = tuple(str(c) for c in _sample().columns)
    tv._sort_cols = [("value", True)]
    tv._hidden_columns = {"region"}
    ds = DataSet.from_dataframe(_sample(), source_id="s", kind="test")
    tv.set_data(ds)
    assert tv._sort_cols == [("value", True)]
    assert tv._hidden_columns == {"region"}


def test_set_data_resets_sort_and_hidden_on_column_change():
    from ecstacy.core.dataset import DataSet
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._columns_signature = ("a", "b")
    tv._sort_cols = [("a", True)]
    tv._hidden_columns = {"a"}
    ds = DataSet.from_dataframe(_sample(), source_id="s", kind="test")
    tv.set_data(ds)
    assert tv._sort_cols == []
    assert tv._hidden_columns == set()


def test_fmt_blanks_nan_and_nat():
    from ecstacy.widgets.table import _fmt

    assert _fmt(float("nan")) == ""
    assert _fmt(pd.NaT) == ""
    assert _fmt(pd.NA) == ""
    assert _fmt("x") == "x"
    assert _fmt(12.5) == "12.5"


def test_footer_text_shows_display_cap():
    from ecstacy.widgets.table import _footer_text

    assert (
        _footer_text("", 50000, 50000, 1000, [])
        == "showing 1000 of 50000 rows  ·  scroll for more"
    )
    text = _footer_text("us", 4, 10, 4, [("value", True)])
    assert "4 rows (of 10)" in text
    assert "sorted by value ↑" in text


def test_filter_cached_skips_hidden_columns():
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    tv._hidden_columns = {"region"}
    assert len(tv._filter_cached(tv._frame, "us")) == 0
    assert len(tv._filter_cached(tv._frame, "10")) == 1


@pytest.mark.asyncio
async def test_table_column_selected_sorts_rows():
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from textual.widgets._data_table import ColumnKey

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"name": ["b", "a", "c"], "value": [2.0, 3.0, 1.0]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        table_view = app.screen.query_one("TableView")
        dt = table_view.query_one("#table-data", DataTable)
        # Columns are added without keys, so Textual posts a ColumnKey whose
        # value is None; selection must resolve by visual column index.
        dt.post_message(DataTable.ColumnSelected(dt, 1, ColumnKey(None)))
        for _ in range(6):
            await pilot.pause()
        assert table_view._sort_cols == [("value", True)]
        assert dt.get_cell_at(Coordinate(0, 0)) == "c"
        # selecting again toggles direction
        dt.post_message(DataTable.ColumnSelected(dt, 1, ColumnKey(None)))
        for _ in range(6):
            await pilot.pause()
        assert table_view._sort_cols == [("value", False)]
        assert dt.get_cell_at(Coordinate(0, 0)) == "a"


@pytest.mark.asyncio
async def test_table_column_picker_hides_columns():
    from textual.app import App
    from textual.widgets import DataTable

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        table_view = app.screen.query_one("TableView")
        table_view._hidden_columns = {"b"}
        table_view._populate()
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        dt = table_view.query_one("#table-data", DataTable)
        col_names = [str(col.label) for col in dt.columns.values()]
        assert "a" in col_names
        assert "c" in col_names
        assert "b" not in col_names


# -----------------------------------------------------------------------
# Table virtualization (item 23b)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_table_loads_first_page_only():
    """A large frame loads only _PAGE_SIZE rows initially."""
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.table import _PAGE_SIZE

    df = pd.DataFrame({"a": range(5000), "b": range(5000, 10000)})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(8):
            await pilot.pause()
        tv = app.screen._active_widget
        assert tv._full_view is not None
        assert len(tv._full_view) == 5000
        assert tv._loaded_count == _PAGE_SIZE


@pytest.mark.asyncio
async def test_table_loads_more_on_demand():
    """Calling _load_next_page appends the next page."""
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.table import _PAGE_SIZE

    df = pd.DataFrame({"a": range(1000), "b": range(1000, 2000)})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(8):
            await pilot.pause()
        tv = app.screen._active_widget
        assert tv._loaded_count == _PAGE_SIZE
        tv._load_next_page()
        assert tv._loaded_count == _PAGE_SIZE * 2
        tv._load_next_page()
        assert tv._loaded_count == _PAGE_SIZE * 3


@pytest.mark.asyncio
async def test_table_export_ignores_pagination():
    """Export returns the full sorted+filtered frame, not just loaded rows."""
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    df = pd.DataFrame({"a": range(5000), "b": range(5000, 10000)})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(8):
            await pilot.pause()
        tv = app.screen._active_widget
        assert tv._loaded_count < 5000
        exported = tv._get_current_view()
        assert len(exported) == 5000


@pytest.mark.asyncio
async def test_search_clears_old_rows():
    """After a search, the DataTable shows only filtered rows, not the
    original rows appended on top."""
    from textual.app import App
    from textual.widgets import DataTable

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.table import _PAGE_SIZE

    df = pd.DataFrame(
        {"region": ["us"] * 300 + ["eu"] * 300, "value": list(range(600))}
    )
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(8):
            await pilot.pause()
        tv = app.screen._active_widget
        table = tv.query_one("#table-data", DataTable)
        # Initially loaded _PAGE_SIZE rows
        assert tv._loaded_count == _PAGE_SIZE
        initial_row_count = table.row_count
        # Trigger a search for "eu"
        tv.set_search("eu")
        # Wait for debounce + worker + delivery
        await app.workers.wait_for_complete()
        for _ in range(8):
            await pilot.pause()
        # The DataTable should now show only filtered rows (300 "eu" rows),
        # capped at _PAGE_SIZE.  It must NOT show initial_row_count + 200.
        assert table.row_count <= _PAGE_SIZE
        assert table.row_count <= initial_row_count


# -----------------------------------------------------------------------
# Offloaded populate (P1.1): filter+sort run on a worker thread
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_offloads_to_worker():
    """A large frame's filter/sort runs on a worker; only _PAGE_SIZE rows
    land after the worker completes (no UI-thread blocking)."""
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.table import _PAGE_SIZE

    df = pd.DataFrame({"a": range(50000), "b": range(50000, 100000)})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        for _ in range(8):
            await pilot.pause()
        tv = app.screen._active_widget
        assert tv._full_view is not None
        assert len(tv._full_view) == 50000
        assert tv._loaded_count == _PAGE_SIZE


@pytest.mark.asyncio
async def test_populate_respects_sort_offloaded():
    """Sorting via column selection re-populates on a worker and the rows
    arrive in sorted order."""
    from textual.app import App
    from textual.coordinate import Coordinate
    from textual.widgets import DataTable
    from textual.widgets._data_table import ColumnKey

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    df = pd.DataFrame({"name": ["b", "a", "c"], "value": [2.0, 3.0, 1.0]})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        table_view = app.screen.query_one("TableView")
        dt = table_view.query_one("#table-data", DataTable)
        dt.post_message(DataTable.ColumnSelected(dt, 1, ColumnKey(None)))
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        assert table_view._sort_cols == [("value", True)]
        assert dt.get_cell_at(Coordinate(0, 0)) == "c"


@pytest.mark.asyncio
async def test_populate_invalidates_stale_worker():
    """Two rapid _populate calls only deliver the latest result (gen counter)."""
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.table import _PAGE_SIZE

    df = pd.DataFrame({"a": range(1000), "b": range(1000, 2000)})
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        tv = app.screen._active_widget
        gen_before = tv._search_gen
        # Rapidly dispatch two populates; the first is superseded.
        tv._populate()
        first_gen = tv._search_gen
        tv._populate()
        assert tv._search_gen == first_gen + 1
        await app.workers.wait_for_complete()
        for _ in range(8):
            await pilot.pause()
        # Latest generation wins; table shows a full page.
        assert tv._loaded_count == _PAGE_SIZE
        assert tv._search_gen == gen_before + 2


@pytest.mark.asyncio
async def test_populate_empty_frame_clears_synchronously():
    """An empty frame short-circuits on the UI thread without dispatching
    a worker."""
    from textual.app import App
    from textual.widgets import DataTable

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    ds = DataSet.from_dataframe(pd.DataFrame(), source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        tv = app.screen._active_widget
        dt = tv.query_one("#table-data", DataTable)
        assert dt.row_count == 0
        assert tv._full_view is None
        assert tv._rendered_columns == ()


# -----------------------------------------------------------------------
# Cursor preservation across async rebuild (multi-column sort fix)
# -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_preserves_cursor_column():
    """After a sort-triggered rebuild, the DataTable's column cursor stays
    where the user left it instead of snapping back to 0."""
    from textual.app import App
    from textual.widgets import DataTable
    from textual.widgets._data_table import ColumnKey

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    df = pd.DataFrame(
        {"name": ["b", "a", "c"], "value": [2.0, 3.0, 1.0], "count": [3, 5, 4]}
    )
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        tv = app.screen._active_widget
        dt = tv.query_one("#table-data", DataTable)
        # Move cursor to column index 1 ("value") and sort it.
        dt.move_cursor(row=0, column=1)
        dt.post_message(DataTable.ColumnSelected(dt, 1, ColumnKey(None)))
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        # The cursor must still be on column 1, not reset to 0.
        assert dt.cursor_column == 1
        assert tv._sort_cols == [("value", True)]


@pytest.mark.asyncio
async def test_multicolumn_sort_via_cursor():
    """Sorting column A then moving to column B and sorting it yields a
    multi-column sort, because the cursor survives the first rebuild."""
    from textual.app import App
    from textual.widgets import DataTable
    from textual.widgets._data_table import ColumnKey

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    df = pd.DataFrame(
        {"region": ["us", "eu", "us", "eu"], "value": [10, 15, 5, 20], "count": [3, 5, 4, 2]}
    )
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        tv = app.screen._active_widget
        dt = tv.query_one("#table-data", DataTable)
        # Sort column 1 ("value") ascending.
        dt.move_cursor(row=0, column=1)
        dt.post_message(DataTable.ColumnSelected(dt, 1, ColumnKey(None)))
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        assert tv._sort_cols == [("value", True)]
        # Cursor survived on column 1; move to column 0 ("region") and sort.
        dt.move_cursor(row=0, column=0)
        dt.post_message(DataTable.ColumnSelected(dt, 0, ColumnKey(None)))
        await app.workers.wait_for_complete()
        for _ in range(6):
            await pilot.pause()
        # Both columns are now in the sort list.
        assert tv._sort_cols == [("value", True), ("region", True)]
        # Rows ordered by value ascending then region ascending:
        # value sorted -> [5(us), 10(us), 15(eu), 20(eu)]
        # adding region asc (already satisfied within equal... here values are
        # distinct so region order follows value order).
        assert list(tv._full_view["value"]) == [5, 10, 15, 20]


@pytest.mark.asyncio
async def test_search_preserves_cursor_column():
    """A filter (search) rebuild also preserves the column cursor."""
    from textual.app import App
    from textual.widgets import DataTable

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    df = pd.DataFrame(
        {"region": ["us"] * 300 + ["eu"] * 300, "value": list(range(600))}
    )
    ds = DataSet.from_dataframe(df, source_id="s", kind="test")

    class _App(App):
        def on_mount(self):
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        tv = app.screen._active_widget
        dt = tv.query_one("#table-data", DataTable)
        dt.move_cursor(row=0, column=1)
        assert dt.cursor_column == 1
        tv.set_search("eu")
        await app.workers.wait_for_complete()
        for _ in range(8):
            await pilot.pause()
        # Cursor column survived the search rebuild.
        assert dt.cursor_column == 1
