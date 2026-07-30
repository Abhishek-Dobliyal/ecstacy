from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd
from rich.text import Text
from textual.app import RenderResult
from textual_plotext import PlotextPlot

from ecstacy.core.dataset import DataSet

_BUDGET_FALLBACK = 1000
_BUDGET_CAP = 2000


@dataclass
class ColumnMapping:
    x: str | None = None
    y: list[str] = field(default_factory=list)
    category: str | None = None
    value: str | None = None
    bins: int = 20


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def auto_mapping(dataset: DataSet, viz_name: str) -> ColumnMapping:
    schema = dataset.schema
    values = schema.value_columns
    times = schema.time_columns
    cats = schema.category_columns
    mapping = ColumnMapping()
    mapping.value = values[0] if values else None
    mapping.category = cats[0] if cats else (times[0] if times else None)
    if viz_name == "scatter":
        mapping.x = values[0] if values else None
        mapping.y = values[1:2] if len(values) > 1 else []
    else:
        mapping.x = times[0] if times else (cats[0] if cats else None)
        mapping.y = values[:4]
    return mapping


class PlotWidget(PlotextPlot):
    """Base class for plotext-backed visualizations.

    Rendering is split into two phases:

    * ``_prepare`` — pure pandas/numpy work (downsample, groupby, dropna).
      Runs on a worker thread so the UI stays responsive on large frames.
    * ``_paint`` — plotext calls using the prepared payload + current theme.
      Runs on the UI thread.

    A render-data cache keyed on ``(dataset identity, mapping, budget)``
    ensures theme toggles only re-paint (colors) without recomputing the
    series.  A generation counter discards stale worker results.

    ``render()`` caches the built ``Text`` keyed on
    ``(size, paint generation, theme)`` so unrelated repaints (focus
    changes, border-title updates, display toggles) don't re-run plotext's
    expensive rasterizer.  Only a real paint, resize, or theme change
    rebuilds the plot.
    """

    viz_name = "plot"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dataset: DataSet | None = None
        self._mapping: ColumnMapping | None = None
        self._render_data: object | None = None
        self._render_key: tuple | None = None
        self._render_gen = 0
        self._render_size: tuple[int, int] | None = None
        self._paint_gen = 0
        self._needs_redraw = False
        self._build_cache: Text | None = None
        self._build_cache_key: tuple | None = None
        self._auto_mapping_cache: ColumnMapping | None = None
        self._auto_mapping_key: tuple | None = None
        self._on_note: Callable[[str | None], None] | None = None
        self._last_note: str | None = None
        self._worker: object | None = None

    # public API

    def set_on_note(self, callback: Callable[[str | None], None] | None) -> None:
        """Set a callback that fires when the chart's data-note changes."""
        self._on_note = callback

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        self._dataset = dataset
        if mapping is not None:
            self._mapping = mapping
        else:
            am_key = (id(dataset), self.viz_name)
            if self._auto_mapping_key == am_key and self._auto_mapping_cache is not None:
                self._mapping = self._auto_mapping_cache
            else:
                self._mapping = auto_mapping(dataset, self.viz_name)
                self._auto_mapping_cache = self._mapping
                self._auto_mapping_key = am_key
        if self.is_mounted:
            self.redraw()

    def on_mount(self) -> None:
        super().on_mount()
        self.app.theme_changed_signal.subscribe(self, self._on_theme_changed)
        if self._dataset is not None and self._render_data is None:
            # set_data ran before the widget was mounted (e.g. dashboard
            # panels), so redraw() was skipped — kick it off now or the
            # plot would stay empty until the next data change.
            self.redraw()

    # budget

    def _budget(self) -> int:
        """Downsample target, clamped to [200, 2000]."""
        w = self.size.width
        if w <= 0:
            return _BUDGET_FALLBACK
        return min(max(w * 2, 200), _BUDGET_CAP)

    # render cache & worker dispatch

    def _content_key(self) -> tuple:
        m = self._mapping
        if m is None:
            return ()
        return (
            id(self._dataset),
            m.x,
            tuple(m.y),
            m.category,
            m.value,
            m.bins,
            self._budget(),
        )

    def _on_theme_changed(self, _theme) -> None:
        if self._render_data is not None:
            self._paint_from_cache()

    def redraw(self) -> None:
        if self._dataset is None or self._mapping is None:
            self._needs_redraw = False
            return
        if self.size.width <= 0:
            # Hidden (display: none) or not laid out yet — the budget depends
            # on the real width, so preparing now would key the cache on the
            # fallback budget and miss again once laid out.  Defer until
            # render() runs at a real size.
            self._needs_redraw = True
            return
        self._needs_redraw = False
        key = self._content_key()
        if key == self._render_key and self._render_data is not None:
            return
        self._render_key = key
        self._render_gen += 1
        gen = self._render_gen
        frame = self._dataset.frame
        mapping = self._mapping
        budget = self._budget()

        def _work() -> None:
            payload = self._prepare(frame, mapping, budget)
            worker = self._worker
            if worker is not None and getattr(worker, "is_cancelled", False):
                return
            try:
                self.app.call_from_thread(self._deliver, gen, payload)
            except RuntimeError:
                pass

        self._worker = self.run_worker(
            _work, thread=True, exclusive=True, exit_on_error=False
        )

    def _deliver(self, gen: int, payload: object) -> None:
        if gen != self._render_gen or not self.is_mounted:
            return
        self._worker = None
        self._render_data = payload
        note = getattr(payload, "note", None)
        if note != self._last_note:
            self._last_note = note
            if self._on_note is not None:
                self._on_note(note)
        self._paint_from_cache()

    def _paint_from_cache(self) -> None:
        if self._render_data is None:
            return
        self._paint_gen += 1  # invalidate the built-renderable cache
        plt = self.plt
        plt.clear_figure()
        self._render_size = None
        try:
            self._paint(plt, self._render_data, self.app.current_theme)
        except Exception as error:
            plt.title(f"cannot render: {error}")
        self.refresh()

    # Textual render hook

    def render(self) -> RenderResult:
        if self._needs_redraw:
            # Consume a redraw deferred while the widget had no size; at a
            # real width this either early-returns (cache hit) or dispatches
            # the prepare worker, whose delivery refreshes us again.
            self.redraw()
        w, h = self.size.width, self.size.height
        key = (w, h, self._paint_gen, self.app.theme)
        if key == self._build_cache_key and self._build_cache is not None:
            return self._build_cache
        if self._render_size != (w, h):
            self._plot.plotsize(w, h)
            self._plot._set_size(w, h)
            self._render_size = (w, h)
        self._plot.theme(self._get_plotext_theme_name(self.app.theme))
        text = Text.from_ansi(self._plot.build())
        self._build_cache = text
        self._build_cache_key = key
        return text

    # subclass hooks

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int) -> object:
        raise NotImplementedError

    def _paint(self, plt, payload, theme) -> None:
        raise NotImplementedError
