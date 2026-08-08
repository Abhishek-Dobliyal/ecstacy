from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import _hex_rgb, _lttb

_MAX_POINTS = 500


@dataclass
class _SparkPayload:
    values: list[float] = field(default_factory=list)
    title: str = ""
    note: str | None = None


@registry.viz.register("sparkline")
class SparklineView(PlotWidget):
    viz_name = "sparkline"

    def _prepare(self, frame, mapping: ColumnMapping, budget: int):
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column or column not in frame.columns:
            return _SparkPayload(title="no numeric column to sparkline")
        series = numeric(frame[column]).dropna()
        if series.empty:
            return _SparkPayload(title=f"no data for {column}")
        # Downsample via LTTB (preserves shape) instead of truncating to the
        # last _MAX_POINTS, so earlier data isn't discarded. Matches the line
        # chart's fidelity strategy.
        downsampled = False
        if len(series) > _MAX_POINTS:
            idx = np.arange(len(series))
            _, ys = _lttb(idx, series.to_numpy(dtype=float), _MAX_POINTS)
            values = ys.tolist()
            downsampled = True
        else:
            values = series.tolist()
        if downsampled:
            title = f"{column} · {len(values):,} of {len(series):,}"
            note = f"↓ {len(series):,} → {len(values):,} points"
        else:
            title = f"{column} · last {len(values)}"
            note = None
        return _SparkPayload(values=values, title=title, note=note)

    def _paint(self, plt, payload: _SparkPayload, theme) -> None:
        if not payload.values:
            if payload.title:
                plt.title(payload.title)
            return
        color = _hex_rgb(theme.primary)
        plt.plot(payload.values, marker="braille", color=color)
        plt.grid(False)
        plt.title(payload.title)
