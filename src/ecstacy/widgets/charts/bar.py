from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget
from ecstacy.widgets.charts._helpers import (
    _decorate,
    _grouped_topn,
    _heat_colors,
)
from ecstacy.widgets.charts._payloads import _BarPayload


@registry.viz.register("bar")
class BarChart(PlotWidget):
    viz_name = "bar"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        result = _grouped_topn(frame, mapping, top_n=30, kind_label="bar chart")
        if isinstance(result, str):
            return _BarPayload(title=result)
        labels, values, title, note, category, value = result
        return _BarPayload(
            labels=labels,
            values=values,
            title=title,
            xlabel=category,
            ylabel=value,
            note=note,
        )

    def _paint(self, plt, payload: _BarPayload, theme) -> None:
        if not payload.labels:
            _decorate(plt, payload.title)
            return
        colors = _heat_colors(payload.values, theme)
        plt.bar(
            payload.labels,
            payload.values,
            orientation="vertical",
            color=colors,
            marker="braille",
        )
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)
