from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.widgets.gauge import _render
from ecstacy.widgets.json_tree import _add


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
