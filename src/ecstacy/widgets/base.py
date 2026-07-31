from __future__ import annotations

import threading
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

    Rendering happens entirely on a worker thread:

    * ``_prepare`` — pure pandas/numpy work (downsample, groupby, dropna);
      skipped when ``(dataset identity, mapping, budget)`` is unchanged.
    * ``_paint`` + plotext ``build()`` + ``Text.from_ansi`` — the expensive
      rasterization (~100ms+ at typical terminal sizes).  Also off-thread;
      the worker delivers a ready-made ``Text`` and the UI thread just
      swaps it in.  ``render()`` never touches the plotext figure, so the
      UI never blocks on rasterization.

    While a rebuild is in flight ``render()`` keeps returning the previous
    (stale) build — no blank flicker.  A ``(size, theme)`` keyed cache
    makes unrelated repaints (focus, borders, display toggles) free; a
    resize or theme change re-paints from the cached payload without
    re-running ``_prepare``.  A generation counter plus a lock around
    figure access discard stale/cancelled worker results.
    """

    viz_name = "plot"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dataset: DataSet | None = None
        self._mapping: ColumnMapping | None = None
        self._render_data: object | None = None
        self._render_key: tuple | None = None
        self._render_gen = 0
        self._paint_gen = 0
        self._needs_redraw = False
        self._build_cache: Text | None = None
        self._build_cache_key: tuple | None = None
        self._build_in_flight: tuple[tuple, tuple | None, bool] | None = None
        self._paint_lock = threading.Lock()
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

    def _theme_name(self) -> str:
        return self._get_plotext_theme_name(self.app.theme)

    def _on_theme_changed(self, _theme) -> None:
        if not self.display:
            # Hidden pooled widget — re-painted lazily on show (the theme
            # name is part of the build cache key).
            return
        if self.is_mounted:
            self._ensure_build()

    def redraw(self) -> None:
        """Dispatch a prepare+paint+build worker (UI thread, dispatch only)."""
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
            # Data unchanged — the cached build may still be stale
            # (resize/theme change); rebuild from the cached payload.
            self._ensure_build()
            return
        self._render_key = key
        self._dispatch(do_prepare=True)

    def _ensure_build(self) -> None:
        """Re-paint + rebuild from the cached payload when size/theme moved."""
        if self._render_data is None and self._build_in_flight is None:
            return
        target = (self.size.width, self.size.height, self._theme_name())
        if target == self._build_cache_key and self._build_cache is not None:
            return  # cached build is current
        in_flight = self._build_in_flight
        if in_flight is not None:
            f_target, f_content_key, f_prepare = in_flight
            if f_target == target:
                return  # this exact build is already on its way
            if f_prepare and f_content_key == self._render_key:
                # Fresh data is inbound; let it land first — render() will
                # request a rebuild for the new size/theme afterwards.
                return
        self._dispatch(do_prepare=False)

    def _dispatch(self, do_prepare: bool) -> None:
        assert self._dataset is not None and self._mapping is not None
        self._render_gen += 1
        gen = self._render_gen
        frame = self._dataset.frame
        mapping = self._mapping
        budget = self._budget()
        size = (self.size.width, self.size.height)
        theme = self.app.current_theme
        theme_name = self._theme_name()
        payload = self._render_data  # reused when do_prepare is False
        self._build_in_flight = ((*size, theme_name), self._render_key, do_prepare)

        def _work() -> None:
            nonlocal payload
            try:
                if do_prepare:
                    payload = self._prepare(frame, mapping, budget)
                # Read the worker ref AFTER _prepare so the assignment in
                # _dispatch has landed (it races with the thread start).
                worker = self._worker
                # Serialize figure access: a superseded worker's in-flight
                # build cannot be interrupted, so the gen check must happen
                # after the lock is acquired (never before painting).
                with self._paint_lock:
                    if gen != self._render_gen or (
                        worker is not None and getattr(worker, "is_cancelled", False)
                    ):
                        return
                    plt = self._plot
                    plt.clear_figure()
                    plt.plotsize(*size)
                    plt._set_size(*size)
                    plt.theme(theme_name)
                    try:
                        self._paint(plt, payload, theme)
                    except Exception as error:
                        plt.title(f"cannot render: {error}")
                    text = Text.from_ansi(plt.build())
            except Exception:
                return  # keep the previous build on screen
            try:
                self.app.call_from_thread(
                    self._deliver, gen, payload, text, (*size, theme_name)
                )
            except RuntimeError:
                pass

        self._worker = self.run_worker(
            _work, thread=True, exclusive=True, exit_on_error=False
        )

    def _deliver(self, gen: int, payload: object, text: Text, target: tuple) -> None:
        if gen != self._render_gen or not self.is_mounted:
            return
        self._worker = None
        self._build_in_flight = None
        self._render_data = payload
        note = getattr(payload, "note", None)
        if note != self._last_note:
            self._last_note = note
            if self._on_note is not None:
                self._on_note(note)
        self._paint_gen += 1
        self._build_cache = text
        self._build_cache_key = target
        self.refresh()

    # Textual render hook

    def render(self) -> RenderResult:
        if self._needs_redraw:
            # Consume a redraw deferred while the widget had no size; at a
            # real width this either early-returns (cache hit) or dispatches
            # the worker, whose delivery refreshes us again.
            self.redraw()
        elif self._render_data is not None:
            self._ensure_build()
        key = (self.size.width, self.size.height, self._theme_name())
        if key == self._build_cache_key and self._build_cache is not None:
            return self._build_cache
        # Nothing current to show yet — return the stale build (Textual
        # crops/pads it for a frame) or blank on first mount.  The worker
        # dispatched above refreshes us with the fresh build when done.
        return self._build_cache if self._build_cache is not None else Text("")

    # subclass hooks

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int) -> object:
        raise NotImplementedError

    def _paint(self, plt, payload, theme) -> None:
        raise NotImplementedError
