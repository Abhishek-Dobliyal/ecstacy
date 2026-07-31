from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import (
    _decorate,
    _downsample_xy,
    _hex_rgb,
    _numeric_columns,
    _to_numeric_or_timestamp,
)
from ecstacy.widgets.charts._payloads import _ScatterPayload


@registry.viz.register("scatter")
class Scatter(PlotWidget):
    viz_name = "scatter"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        x = mapping.x
        y = mapping.y[0] if mapping.y else mapping.value
        if not x or not y:
            nums = _numeric_columns(frame)
            if len(nums) >= 2:
                x, y = nums[0], nums[1]
        if not x or not y:
            return _ScatterPayload(title="scatter needs two numeric columns")
        work = frame[[x, y]].dropna()
        if work.empty:
            return _ScatterPayload(title="scatter has no overlapping x/y data")
        total = len(work)
        xvals = numeric(_to_numeric_or_timestamp(work[x])).to_numpy(dtype=float)
        yvals = numeric(work[y]).to_numpy(dtype=float)
        downsampled = len(xvals) > budget
        if downsampled:
            xvals, yvals = _downsample_xy(xvals, yvals, budget)
        note = f"↓ {total:,} → {budget:,} points" if downsampled else None
        return _ScatterPayload(
            x=xvals.tolist(),
            y=yvals.tolist(),
            title=f"{y} vs {x}",
            xlabel=x,
            ylabel=y,
            note=note,
        )

    def _paint(self, plt, payload: _ScatterPayload, theme) -> None:
        if not payload.x:
            _decorate(plt, payload.title)
            return
        plt.scatter(
            payload.x,
            payload.y,
            marker="braille",
            color=_hex_rgb(theme.secondary),
        )
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)
