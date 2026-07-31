from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import (
    _category_columns,
    _decorate,
    _hex_rgb,
    _numeric_columns,
)
from ecstacy.widgets.charts._payloads import _ProportionPayload


@registry.viz.register("proportion")
class ProportionChart(PlotWidget):
    viz_name = "proportion"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        category = mapping.category or mapping.x
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        if not category:
            cats = _category_columns(frame)
            category = cats[0] if cats else None
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not category or not value:
            return _ProportionPayload(
                title="proportion chart needs a category and a numeric column"
            )
        if category == value:
            return _ProportionPayload(
                title="proportion chart needs distinct category and value columns"
            )
        work = frame[[category, value]].copy()
        work[value] = numeric(work[value])
        work = work.dropna(subset=[category, value])
        if work.empty:
            return _ProportionPayload(title="proportion chart has no data after removing NaNs")
        grouped = work.groupby(category)[value].sum().sort_values(ascending=False).head(20)
        labels = [str(i) for i in grouped.index]
        total_cats = work[category].nunique()
        note = None
        if len(grouped) < total_cats:
            note = f"top {len(grouped)} of {total_cats} categories"
        return _ProportionPayload(
            labels=labels,
            values=grouped.tolist(),
            title=f"{value} by {category}",
            note=note,
        )

    def _paint(self, plt, payload: _ProportionPayload, theme) -> None:
        if not payload.labels:
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        colors = [_hex_rgb(palette[i % len(palette)]) for i in range(len(payload.labels))]
        plt.bar(
            payload.labels, payload.values,
            orientation="horizontal", color=colors, marker="braille",
        )
        _decorate(plt, payload.title)
