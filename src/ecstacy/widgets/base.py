from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
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
        # leave y empty with a single value column; plotting x against
        # itself would show a meaningless diagonal
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
    """

    viz_name = "plot"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dataset: DataSet | None = None
        self._mapping: ColumnMapping | None = None
        self._render_data: object | None = None
        self._render_key: tuple | None = None
        self._render_gen = 0
        self._auto_mapping_cache: ColumnMapping | None = None
        self._auto_mapping_key: tuple | None = None

    # -- public API --------------------------------------------------------

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
        self.redraw()
        self.app.theme_changed_signal.subscribe(self, self._on_theme_changed)

    # -- budget -----------------------------------------------------------

    def _budget(self) -> int:
        """Terminal-budget downsampling target: ~2x the widget width in
        x-positions, clamped to [200, 2000].  Falls back to 1000 before
        the widget is sized."""
        w = self.size.width
        if w <= 0:
            return _BUDGET_FALLBACK
        return min(max(w * 2, 200), _BUDGET_CAP)

    # -- render cache & worker dispatch -----------------------------------

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
        # Theme change only affects colors — re-paint the cached payload
        # without re-running _prepare.
        if self._render_data is not None:
            self._paint_from_cache()

    def redraw(self) -> None:
        if self._dataset is None or self._mapping is None:
            return
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
            try:
                self.app.call_from_thread(self._deliver, gen, payload)
            except RuntimeError:
                pass

        self.run_worker(_work, thread=True, exclusive=True, exit_on_error=False)

    def _deliver(self, gen: int, payload: object) -> None:
        if gen != self._render_gen or not self.is_mounted:
            return
        self._render_data = payload
        self._paint_from_cache()

    def _paint_from_cache(self) -> None:
        if self._render_data is None:
            return
        plt = self.plt
        plt.clear_figure()
        try:
            plt.theme("dark" if self.app.current_theme.dark else "pro")
        except Exception:
            plt.theme("dark")
        try:
            self._paint(plt, self._render_data, self.app.current_theme)
        except Exception as error:
            plt.title(f"cannot render: {error}")
        self.refresh()

    # -- subclass hooks ----------------------------------------------------

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int) -> object:
        raise NotImplementedError

    def _paint(self, plt, payload, theme) -> None:
        raise NotImplementedError
