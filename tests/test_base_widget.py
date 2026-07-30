from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import PlotWidget

_prepare_calls = 0
_paint_calls = 0
_lock = threading.Lock()


class CountingPlot(PlotWidget):
    viz_name = "counting"

    def _prepare(self, frame, mapping, budget):
        global _prepare_calls
        with _lock:
            _prepare_calls += 1
        return "payload"

    def _paint(self, plt, payload, theme):
        global _paint_calls
        with _lock:
            _paint_calls += 1


class SlowPlot(PlotWidget):
    viz_name = "slow"

    def _prepare(self, frame, mapping, budget):
        time.sleep(0.3)
        return "slow-payload"

    def _paint(self, plt, payload, theme):
        global _paint_calls
        with _lock:
            _paint_calls += 1


def _dataset() -> DataSet:
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    return DataSet.from_dataframe(frame, source_id="s", kind="test")


async def _settle(app, pilot):
    """Wait for worker-prepare + call_from_thread-paint to complete."""
    await app.workers.wait_for_complete()
    for _ in range(8):
        await pilot.pause()


@pytest.mark.asyncio
async def test_redraw_skipped_when_dataset_and_mapping_unchanged():
    global _prepare_calls, _paint_calls
    _prepare_calls = 0
    _paint_calls = 0
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        ds = _dataset()
        widget.set_data(ds)
        await _settle(app, pilot)
        assert _prepare_calls == 1
        assert _paint_calls == 1
        # same dataset object + equivalent auto mapping -> no-op
        widget.set_data(ds)
        await _settle(app, pilot)
        assert _prepare_calls == 1
        assert _paint_calls == 1
        # new dataset object -> re-prepare + re-paint
        widget.set_data(_dataset())
        await _settle(app, pilot)
        assert _prepare_calls == 2
        assert _paint_calls == 2


@pytest.mark.asyncio
async def test_theme_change_repaints_without_reprepare():
    global _prepare_calls, _paint_calls
    _prepare_calls = 0
    _paint_calls = 0
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        widget.set_data(_dataset())
        await _settle(app, pilot)
        assert _prepare_calls == 1
        assert _paint_calls == 1
        # theme change → re-paint only, no re-prepare
        widget._on_theme_changed(None)
        for _ in range(4):
            await pilot.pause()
        assert _prepare_calls == 1
        assert _paint_calls == 2


@pytest.mark.asyncio
async def test_explicit_mapping_change_redraws():
    global _prepare_calls, _paint_calls
    _prepare_calls = 0
    _paint_calls = 0
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
        await _settle(app, pilot)
        assert _prepare_calls == 1
        widget.set_data(ds, ColumnMapping(x="y", y=["x"]))
        await _settle(app, pilot)
        assert _prepare_calls == 2


@pytest.mark.asyncio
async def test_plotwidget_clears_worker_ref_after_delivery():
    global _prepare_calls
    _prepare_calls = 0
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        widget.set_data(_dataset())
        await _settle(app, pilot)
        assert widget._worker is None


@pytest.mark.asyncio
async def test_render_caches_built_plot_until_next_paint():
    """Repaints without new data/size/theme reuse the cached renderable
    instead of re-running plotext's expensive build()."""
    from textual.app import App

    class _App(App):
        def compose(self):
            yield CountingPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(CountingPlot)
        widget.set_data(_dataset())
        await _settle(app, pilot)
        builds = 0
        real_build = widget._plot.build

        def counting_build():
            nonlocal builds
            builds += 1
            return real_build()

        widget._plot.build = counting_build
        # Unrelated repaints: cached renderable returned, no rebuild.
        for _ in range(3):
            widget.refresh()
            await pilot.pause()
        assert builds == 0
        # A new dataset → re-paint → exactly one rebuild.
        widget.set_data(_dataset())
        await _settle(app, pilot)
        assert builds == 1


@pytest.mark.asyncio
async def test_plotwidget_skips_delivery_when_cancelled():
    """A widget unmounted mid-prepare skips the paint delivery."""
    global _paint_calls
    _paint_calls = 0
    import asyncio

    from textual.app import App

    class _App(App):
        def compose(self):
            yield SlowPlot()

    app = _App()
    async with app.run_test() as pilot:
        widget = app.query_one(SlowPlot)
        widget.set_data(_dataset())
        # Let the worker start (thread begins sleeping 0.3s).
        await pilot.pause()
        # Unmount the widget — this triggers cancel_node on its workers.
        widget.remove()
        # Process the unmount message so cancel_node runs and sets _cancelled.
        for _ in range(4):
            await pilot.pause()
        # Wait for the thread to finish its 0.3s sleep; it should see
        # is_cancelled=True and skip the call_from_thread delivery.
        await asyncio.sleep(0.5)
        for _ in range(8):
            await pilot.pause()
        assert _paint_calls == 0
