from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.config import defaults
from ecstacy.widgets.table import filter_frame, sort_frame, sort_frame_multi


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


def test_sort_frame_ascending():
    result = sort_frame(_sample(), "value", ascending=True)
    assert list(result["value"]) == [8.0, 10.0, 12.0, 15.0]


def test_sort_frame_descending():
    result = sort_frame(_sample(), "value", ascending=False)
    assert list(result["value"]) == [15.0, 12.0, 10.0, 8.0]


def test_sort_frame_missing_column_returns_unchanged():
    frame = _sample()
    result = sort_frame(frame, "missing", ascending=True)
    assert len(result) == 4


def test_filter_then_sort():
    filtered = filter_frame(_sample(), "us")
    result = sort_frame(filtered, "value", ascending=False)
    assert list(result["value"]) == [12.0, 10.0]


def test_sort_frame_covers_all_rows_not_just_head():
    rows = []
    for i in range(2000):
        rows.append({"region": "r" + str(i), "value": float(2000 - i)})
    frame = pd.DataFrame(rows)
    sorted_frame = sort_frame(frame, "value", ascending=True)
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
