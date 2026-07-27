from __future__ import annotations

import pandas as pd

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, auto_mapping, numeric
from ecstacy.widgets.charts import _hex_rgb

_MAX_POINTS = 500


@registry.viz.register("sparkline")
class SparklineView(PlotWidget):
    viz_name = "sparkline"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column or column not in frame.columns:
            plt.title("no numeric column to sparkline")
            return
        series = numeric(frame[column]).dropna()
        if series.empty:
            plt.title(f"no data for {column}")
            return
        values = series.tolist()[-_MAX_POINTS:]
        color = _hex_rgb(self.app.current_theme.primary)
        plt.plot(values, marker="braille", color=color)
        plt.grid(False)
        plt.title(f"{column} · last {len(values)}")
