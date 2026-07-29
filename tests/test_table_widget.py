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


def test_set_data_invalidates_string_cache():
    from ecstacy.core.dataset import DataSet
    from ecstacy.widgets.table import TableView

    tv = TableView()
    tv._frame = _sample()
    tv._filter_cached(tv._frame, "us")
    assert tv._string_frame is not None
    ds = DataSet.from_dataframe(_sample(), source_id="s", kind="test")
    tv.set_data(ds)
    assert tv._string_frame is None


def test_fmt_blanks_nan_and_nat():
    from ecstacy.widgets.table import _fmt

    assert _fmt(float("nan")) == ""
    assert _fmt(pd.NaT) == ""
    assert _fmt(pd.NA) == ""
    assert _fmt("x") == "x"
    assert _fmt(12.5) == "12.5"


def test_footer_text_shows_display_cap():
    from ecstacy.widgets.table import _footer_text

    assert _footer_text("", 50000, 50000, 1000, []) == "showing 1000 of 50000 rows"
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
        dt = table_view.query_one("#table-data", DataTable)
        col_names = [str(col.label) for col in dt.columns.values()]
        assert "a" in col_names
        assert "c" in col_names
        assert "b" not in col_names
