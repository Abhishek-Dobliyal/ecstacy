from textual.widget import Widget

from ecstacy.core import registry
from ecstacy.widgets import charts, gauge, json_tree, spark, summary, table  # noqa: F401
from ecstacy.widgets.base import ColumnMapping, auto_mapping

VIZ_ORDER = [
    "table",
    "line",
    "bar",
    "histogram",
    "scatter",
    "sparkline",
    "gauge",
    "heatmap",
    "box",
    "pie",
    "summary",
    "json",
]


def viz_names() -> list[str]:
    ordered = [name for name in VIZ_ORDER if registry.viz.has(name)]
    extra = [name for name in registry.viz.names() if name not in VIZ_ORDER]
    return ordered + extra


def create_viz(name: str) -> Widget:
    return registry.viz.get(name)()


__all__ = ["ColumnMapping", "auto_mapping", "viz_names", "create_viz", "VIZ_ORDER"]
