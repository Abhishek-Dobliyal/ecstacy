from __future__ import annotations

import numpy as np
import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import (
    _downsample_xy,
    _hex_rgb,
    _lttb,
    _numeric_columns,
    _to_numeric_or_timestamp,
)
from ecstacy.widgets.charts._payloads import _LinePayload, _LineSeries


@registry.viz.register("line")
class LineChart(PlotWidget):
    viz_name = "line"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        ycols = [c for c in mapping.y if c in frame.columns] or _numeric_columns(frame)
        if not ycols:
            return _LinePayload(title="line chart needs a numeric column")
        xcol = mapping.x if mapping.x and mapping.x in frame.columns else None
        work = frame
        series_list: list[_LineSeries] = []
        downsampled = False
        for col in ycols:
            yvals_raw = numeric(work[col]).dropna()
            if yvals_raw.empty:
                continue
            if xcol is not None and xcol in work.columns:
                x_raw = _to_numeric_or_timestamp(work[xcol])
                x_aligned = x_raw.loc[yvals_raw.index].dropna()
                y_aligned = yvals_raw.loc[x_aligned.index]
                if len(y_aligned) > budget:
                    xs, ys = _downsample_xy(
                        x_aligned.to_numpy(dtype=float),
                        y_aligned.to_numpy(dtype=float),
                        budget,
                    )
                    series_list.append(_LineSeries(x=xs.tolist(), y=ys.tolist(), label=col))
                    downsampled = True
                else:
                    series_list.append(_LineSeries(
                        x=x_aligned.to_numpy(dtype=float).tolist(),
                        y=y_aligned.to_numpy(dtype=float).tolist(),
                        label=col,
                    ))
            else:
                yvals = yvals_raw.to_numpy(dtype=float)
                if len(yvals) > budget:
                    idx = np.arange(len(yvals))
                    _, ys = _lttb(idx, yvals, budget)
                    series_list.append(_LineSeries(x=None, y=ys.tolist(), label=col))
                    downsampled = True
                else:
                    series_list.append(_LineSeries(x=None, y=yvals.tolist(), label=col))
        title = " / ".join(ycols) if ycols else "line"
        if xcol:
            title = f"{title} over {xcol}"
        note = f"↓ {len(work):,} → {budget:,} points" if downsampled else None
        return _LinePayload(
            series=series_list,
            title=title,
            xlabel=xcol,
            ylabel=", ".join(ycols) or None,
            note=note,
        )

    def _paint(self, plt, payload: _LinePayload, theme) -> None:
        if not payload.series:
            from ecstacy.widgets.charts._helpers import _decorate
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        for i, s in enumerate(payload.series):
            color = _hex_rgb(palette[i % len(palette)])
            if s.x is not None:
                plt.plot(s.x, s.y, label=s.label, marker="braille", color=color)
            else:
                plt.plot(s.y, label=s.label, marker="braille", color=color)
        from ecstacy.widgets.charts._helpers import _decorate
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)
