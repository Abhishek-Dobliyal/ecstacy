from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from textual_plotext import PlotextPlot

from ecstacy.core.dataset import DataSet


@dataclass
class ColumnMapping:
    x: str | None = None
    y: list[str] = field(default_factory=list)
    category: str | None = None
    value: str | None = None
    bins: int = 20


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def auto_mapping(dataset: DataSet, viz_name: str) -> ColumnMapping:
    schema = dataset.schema
    values = schema.value_columns
    times = schema.time_columns
    cats = schema.category_columns
    mapping = ColumnMapping()
    mapping.value = values[0] if values else None
    mapping.category = cats[0] if cats else (times[0] if times else None)
    if viz_name == "scatter":
        mapping.x = values[0] if values else None
        mapping.y = values[1:2] if len(values) > 1 else values[:1]
    else:
        mapping.x = times[0] if times else (cats[0] if cats else None)
        mapping.y = values[:4]
    return mapping


class PlotWidget(PlotextPlot):
    viz_name = "plot"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._dataset: DataSet | None = None
        self._mapping: ColumnMapping | None = None

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        self._dataset = dataset
        self._mapping = mapping or auto_mapping(dataset, self.viz_name)
        if self.is_mounted:
            self.redraw()

    def on_mount(self) -> None:
        super().on_mount()
        self.redraw()
        self.app.theme_changed_signal.subscribe(self, self._on_theme_changed)

    def _on_theme_changed(self, _theme) -> None:
        self.redraw()

    def redraw(self) -> None:
        if self._dataset is None or self._mapping is None:
            return
        plt = self.plt
        plt.clear_figure()
        try:
            plt.theme("dark" if self.app.current_theme.dark else "pro")
        except Exception:
            plt.theme("dark")
        try:
            self._draw(plt, self._dataset.frame, self._mapping)
        except Exception as error:
            plt.title(f"cannot render: {error}")
        self.refresh()

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        raise NotImplementedError
