from __future__ import annotations

import contextlib
import io

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget
from ecstacy.widgets.charts._helpers import _decorate
from ecstacy.widgets.charts._payloads import _HeatmapPayload


@registry.viz.register("heatmap")
class Heatmap(PlotWidget):
    viz_name = "heatmap"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        numbers = frame.select_dtypes("number")
        if numbers.shape[1] < 2:
            return _HeatmapPayload(title="heatmap needs at least two numeric columns")
        total = len(numbers)
        if total > budget:
            numbers = numbers.tail(budget)
        corr = numbers.corr().fillna(0.0).round(2)
        note = f"last {len(numbers):,} of {total:,} rows" if total > budget else None
        return _HeatmapPayload(corr=corr, title="correlation matrix", note=note)

    def _paint(self, plt, payload: _HeatmapPayload, theme) -> None:
        if payload.corr is None:
            _decorate(plt, payload.title)
            return
        with contextlib.redirect_stdout(io.StringIO()):
            plt.heatmap(payload.corr)
        _decorate(plt, payload.title)
