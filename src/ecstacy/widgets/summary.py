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
        for col in numeric_cols:
            series = pd.to_numeric(frame[col], errors="coerce").dropna()
            if series.empty:
                continue
            lines.append(
                f"  {str(col):<20} {len(series):>6} "
                f"{series.mean():>12.2f} {series.median():>12.2f} "
                f"{series.std():>12.2f} {series.min():>12.2f} {series.max():>12.2f}"
            )
        self.update("\n".join(lines))
