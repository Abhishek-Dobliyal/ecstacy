from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget
from ecstacy.widgets.charts._helpers import (
    _decorate,
    _grouped_topn,
    _hex_rgb,
    _theme_palette,
)
from ecstacy.widgets.charts._payloads import _ProportionPayload


@registry.viz.register("proportion")
class ProportionChart(PlotWidget):
    viz_name = "proportion"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        result = _grouped_topn(
            frame, mapping, top_n=20, kind_label="proportion chart", prefer_value=True
        )
        if isinstance(result, str):
            return _ProportionPayload(title=result)
        labels, values, title, note, _, _ = result
        return _ProportionPayload(
            labels=labels,
            values=values,
            title=title,
            note=note,
        )

    def _paint(self, plt, payload: _ProportionPayload, theme) -> None:
        if not payload.labels:
            _decorate(plt, payload.title)
            return
        palette = _theme_palette(theme)
        colors = [_hex_rgb(palette[i % len(palette)]) for i in range(len(payload.labels))]
        plt.bar(
            payload.labels, payload.values,
            orientation="horizontal", color=colors, marker="braille",
        )
        _decorate(plt, payload.title)
