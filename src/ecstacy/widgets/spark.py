from __future__ import annotations

from dataclasses import dataclass, field

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric
from ecstacy.widgets.charts._helpers import _hex_rgb

_MAX_POINTS = 500


@dataclass
class _SparkPayload:
    values: list[float] = field(default_factory=list)
    title: str = ""


@registry.viz.register("sparkline")
class SparklineView(PlotWidget):
    viz_name = "sparkline"

    def _prepare(self, frame, mapping: ColumnMapping, budget: int):
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column or column not in frame.columns:
            return _SparkPayload(title="no numeric column to sparkline")
        # Truncate BEFORE coercion/dropna so they run on ≤_MAX_POINTS rows.
        series = frame[column]
        if len(series) > _MAX_POINTS:
            series = series.iloc[-_MAX_POINTS:]
        values = numeric(series).dropna().tolist()
        if not values:
            return _SparkPayload(title=f"no data for {column}")
        return _SparkPayload(values=values, title=f"{column} · last {len(values)}")

    def _paint(self, plt, payload: _SparkPayload, theme) -> None:
        if not payload.values:
            if payload.title:
                plt.title(payload.title)
            return
        color = _hex_rgb(theme.primary)
        plt.plot(payload.values, marker="braille", color=color)
        plt.grid(False)
        plt.title(payload.title)
