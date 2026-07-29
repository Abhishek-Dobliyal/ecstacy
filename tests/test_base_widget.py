from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import PlotWidget

_draw_calls = 0


class CountingPlot(PlotWidget):
    viz_name = "counting"

    def _draw(self, plt, frame, mapping) -> None:
        global _draw_calls
        _draw_calls += 1


def _dataset() -> DataSet:
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    return DataSet.from_dataframe(frame, source_id="s", kind="test")


@pytest.mark.asyncio
async def test_redraw_skipped_when_dataset_and_mapping_unchanged():
    global _draw_calls
    _draw_calls = 0
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        ds = _dataset()
        widget.set_data(ds)
        await pilot.pause()
        assert _draw_calls == 1
        # same dataset object + equivalent auto mapping -> no-op
        widget.set_data(ds)
        await pilot.pause()
        assert _draw_calls == 1
        # new dataset object -> redraw
        widget.set_data(_dataset())
        await pilot.pause()
        assert _draw_calls == 2


@pytest.mark.asyncio
async def test_theme_change_forces_redraw():
    global _draw_calls
    _draw_calls = 0
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        widget.set_data(_dataset())
        await pilot.pause()
        assert _draw_calls == 1
        widget._on_theme_changed(None)
        await pilot.pause()
        assert _draw_calls == 2


@pytest.mark.asyncio
async def test_explicit_mapping_change_redraws():
    global _draw_calls
    _draw_calls = 0
    from textual.app import App

    from ecstacy.widgets.base import ColumnMapping

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        ds = _dataset()
        widget.set_data(ds, ColumnMapping(x="x", y=["y"]))
        await pilot.pause()
        assert _draw_calls == 1
        widget.set_data(ds, ColumnMapping(x="y", y=["x"]))
        await pilot.pause()
        assert _draw_calls == 2
