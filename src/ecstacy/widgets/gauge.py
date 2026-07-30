from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping, auto_mapping, numeric

if TYPE_CHECKING:
    from textual.timer import Timer

_BAR_WIDTH = 24
_TICK = 0.04
_DURATION = 0.25
_STEPS = max(1, int(_DURATION / _TICK))


@registry.viz.register("gauge")
class GaugeView(Static):
    viz_name = "gauge"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._name: str = ""
        self._latest = 0.0
        self._delta = 0.0
        self._low = 0.0
        self._high = 1.0
        self._target_fill = 0
        self._step = 0
        self._timer: Timer | None = None

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        # stop any running animation so error messages aren't overwritten
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        mapping = mapping or auto_mapping(dataset, self.viz_name)
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        frame = dataset.frame
        if not column or column not in frame.columns:
            self.update("no numeric column to gauge")
            return
        series = numeric(frame[column]).dropna()
        if series.empty:
            self.update("no data")
            return
        self._name = column
        self._latest = float(series.iloc[-1])
        previous = float(series.iloc[-2]) if len(series) > 1 else self._latest
        self._delta = self._latest - previous
        self._low = float(series.min())
        self._high = float(series.max())
        span = self._high - self._low or 1.0
        self._target_fill = int(max(0.0, min(1.0, (self._latest - self._low) / span)) * _BAR_WIDTH)
        self._step = 0
        self._start_anim()

    def _start_anim(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        self._step = 0
        self._timer = self.set_interval(_TICK, self._advance)

    def on_unmount(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _advance(self) -> None:
        self._step += 1
        progress = min(1.0, self._step / _STEPS)
        fill = int(progress * self._target_fill)
        self.update(_render(self._name, self._latest, self._delta, self._low, self._high, fill))
        if self._step >= _STEPS:
            if self._timer is not None:
                self._timer.stop()
            self._timer = None


def _render(name: str, latest: float, delta: float, low: float, high: float, filled: int) -> str:
    bar = "⣿" * filled + "⣀" * (_BAR_WIDTH - filled)
    return (
        f"{name}\n\n"
        f"  {latest:,.2f}   (delta {delta:+.2f})\n\n"
        f"  [{bar}]\n"
        f"  min {low:,.2f}   max {high:,.2f}"
    )
