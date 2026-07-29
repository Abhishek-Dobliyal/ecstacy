from __future__ import annotations

import pandas as pd
from textual.widgets import Static

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping


@registry.viz.register("summary")
class SummaryCard(Static):
    viz_name = "summary"

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        frame = dataset.frame
        if frame.empty:
            self.update("no data")
            return
        numeric_cols = frame.select_dtypes("number").columns
        if len(numeric_cols) == 0:
            self.update(f"{len(frame)} rows  ·  no numeric columns")
            return
        lines = [f"  [bold]{len(frame)} rows[/bold]  ·  {len(frame.columns)} columns\n"]
        header = (
            f"  {'column':<20} {'count':>6} {'mean':>12} "
            f"{'median':>12} {'std':>12} {'min':>12} {'max':>12}"
        )
        lines.append(header)
        lines.append(
            f"  {'─' * 20} {'─' * 6} {'─' * 12} "
            f"{'─' * 12} {'─' * 12} {'─' * 12} {'─' * 12}"
        )
        numeric_frame = frame[numeric_cols].apply(pd.to_numeric, errors="coerce")
        stats = numeric_frame.agg(["count", "mean", "median", "std", "min", "max"])
        for col in numeric_cols:
            col_stats = stats[col]
            if col_stats["count"] == 0:
                continue
            lines.append(
                f"  {str(col):<20} {int(col_stats['count']):>6} "
                f"{col_stats['mean']:>12.2f} {col_stats['median']:>12.2f} "
                f"{col_stats['std']:>12.2f} {col_stats['min']:>12.2f} "
                f"{col_stats['max']:>12.2f}"
            )
        self.update("\n".join(lines))
