from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.widgets.gauge import _render
from ecstacy.widgets.json_tree import JsonTree, _add


@pytest.mark.asyncio
async def test_gauge_view_renders_with_numeric_column():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"value": [10.0, 20.0, 30.0, 25.0]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "gauge"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_gauge_view_no_numeric_column():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "gauge"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


def test_gauge_render_shows_value_and_delta():
    text = _render("cpu", 75.0, 5.0, 10.0, 100.0, 18)
    assert "cpu" in text
    assert "75.00" in text
    assert "+5.00" in text
    assert "10.00" in text
    assert "100.00" in text


@pytest.mark.asyncio
async def test_json_tree_renders_with_raw_data():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"a": [1]})
            raw = {"items": [{"x": 1}, {"x": 2}], "count": 2}
            ds = DataSet.from_dataframe(df, source_id="s", kind="rest", raw=raw)
            self.push_screen(ChartScreen(ds, "json"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_json_tree_renders_without_raw_falls_back_to_records():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="file")
            self.push_screen(ChartScreen(ds, "json"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


def test_json_tree_add_dict():
    from textual.widgets import Tree

    tree = Tree("root")
    _add(tree.root, {"name": "test", "value": 42})
    assert tree.root.children is not None


def test_json_tree_add_list():
    from textual.widgets import Tree

    tree = Tree("root")
    _add(tree.root, [1, 2, {"key": "val"}])
    assert tree.root.children is not None


def test_json_tree_truncates_large_list():
    widget = JsonTree()
    # Simulate set_data with a large raw list
    large_raw = [{"i": i} for i in range(50)]
    ds = DataSet.from_dataframe(
        pd.DataFrame({"a": [1]}), source_id="s", kind="rest", raw=large_raw
    )
    widget.set_data(ds)
    # Tree should have 20 data nodes + 1 truncation leaf
    children = widget.root.children
    assert children is not None
    assert len(children) == 21
    last = children[-1]
    assert not last.allow_expand
    assert "30 more" in last.label.plain


def test_json_tree_no_truncation_for_small_list():
    widget = JsonTree()
    small_raw = [{"x": 1}, {"x": 2}]
    ds = DataSet.from_dataframe(
        pd.DataFrame({"a": [1]}), source_id="s", kind="rest", raw=small_raw
    )
    widget.set_data(ds)
    children = widget.root.children
    assert children is not None
    assert len(children) == 2


@pytest.mark.asyncio
async def test_heatmap_renders_with_numeric_columns():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame(
                {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]}
            )
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "heatmap"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_heatmap_renders_with_insufficient_numeric_columns():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "heatmap"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_summary_card_renders_with_numeric_data():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame(
                {"value": [10.0, 20.0, 30.0, 40.0, 50.0], "count": [1, 2, 3, 4, 5]}
            )
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "summary"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_summary_card_no_numeric_columns():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu", "ap"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "summary"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_summary_card_empty_frame():
    from textual.app import App

    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame()
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "summary"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


def test_summary_stat_blanks_nan():
    from ecstacy.widgets.summary import _stat

    assert _stat(float("nan")).strip() == ""
    assert _stat(3.14159) == f"{3.14159:>12.2f}"
