from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import _decorate, _hex_rgb, _numeric_columns
from ecstacy.widgets.charts._payloads import _BoxPayload


@registry.viz.register("box")
class BoxPlot(PlotWidget):
    viz_name = "box"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        category = mapping.category or mapping.x
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not value:
            return _BoxPayload(title="box plot needs a numeric column")
        if not category or category not in frame.columns:
            category = None
        if category:
            grouped = frame.dropna(subset=[value, category]).groupby(category)[value]
            labels: list[str] = []
            data: list[list[float]] = []
            total_values = 0
            shown_values = 0
            for cat, group in grouped:
                vals = numeric(group).dropna()
                total_values += len(vals)
                if len(vals) > budget:
                    vals = vals.tail(budget)
                vals = vals.tolist()
                shown_values += len(vals)
                if not vals:
                    continue
                labels.append(str(cat))
                data.append(vals)
            if not data:
                return _BoxPayload(title=f"no data for {value}")
            note = None
            if total_values > shown_values:
                note = f"last {shown_values:,} of {total_values:,} values"
            return _BoxPayload(
                labels=labels,
                data=data,
                title=f"{value} by {category}",
                ylabel=value,
                note=note,
            )
        else:
            series = numeric(frame[value]).dropna()
            total = len(series)
            if total > budget:
                series = series.tail(budget)
            if series.empty:
                return _BoxPayload(title=f"no data for {value}")
            note = f"last {len(series):,} of {total:,} values" if total > budget else None
            return _BoxPayload(
                labels=[value],
                data=[series.tolist()],
                title=f"distribution of {value}",
                ylabel=value,
                note=note,
            )

    def _paint(self, plt, payload: _BoxPayload, theme) -> None:
        if not payload.data:
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        colors = [_hex_rgb(palette[0]), _hex_rgb(palette[1])]
        plt.box(payload.labels, payload.data, colors=colors)
        _decorate(plt, payload.title, ylabel=payload.ylabel)
