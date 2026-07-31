from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import _decorate, _hex_rgb, _numeric_columns
from ecstacy.widgets.charts._payloads import _HistPayload


@registry.viz.register("histogram")
class Histogram(PlotWidget):
    viz_name = "histogram"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column:
            columns = _numeric_columns(frame)
            column = columns[0] if columns else None
        if not column:
            return _HistPayload(title="")
        series = frame[column]
        total = len(series)
        if total > budget:
            series = series.tail(budget)
        values = numeric(series).dropna().tolist()
        if not values:
            return _HistPayload(title=f"no numeric data for {column}")
        note = f"last {len(values):,} of {total:,} values" if total > budget else None
        return _HistPayload(
            values=values,
            bins=mapping.bins,
            title=f"distribution of {column}",
            xlabel=column,
            ylabel="count",
            note=note,
        )

    def _paint(self, plt, payload: _HistPayload, theme) -> None:
        if not payload.values:
            if payload.title:
                _decorate(plt, payload.title)
            return
        plt.hist(payload.values, payload.bins, color=_hex_rgb(theme.accent), marker="braille")
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)
