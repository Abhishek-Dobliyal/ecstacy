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
    "proportion",
    "summary",
    "json",
]

# Backwards-compatible aliases for renamed visualizations. These resolve
# anywhere a viz name is accepted but are not listed by viz_names().
_VIZ_ALIASES = {"pie": "proportion"}


def resolve_viz(name: str) -> str:
    return _VIZ_ALIASES.get(name, name)


def viz_names() -> list[str]:
    ordered = [name for name in VIZ_ORDER if registry.viz.has(name)]
    extra = [name for name in registry.viz.names() if name not in VIZ_ORDER]
    return ordered + extra


def create_viz(name: str) -> Widget:
    return registry.viz.get(resolve_viz(name))()


__all__ = [
    "ColumnMapping",
    "auto_mapping",
    "viz_names",
    "create_viz",
    "resolve_viz",
    "VIZ_ORDER",
]
