from __future__ import annotations

from typing import Any

import pandas as pd
from textual.widgets import Tree

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping

_MAX_ITEMS = 200
_MAX_DEPTH = 20


@registry.viz.register("json")
class JsonTree(Tree):
    viz_name = "json"

    def __init__(self, **kwargs) -> None:
        super().__init__("data", **kwargs)

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        self.clear()
        data = dataset.meta.raw
        if data is None:
            data = dataset.frame.head(_MAX_ITEMS).to_dict(orient="records")
        _add(self.root, data)
        self.root.expand()


def _add(node, data: Any, depth: int = 0) -> None:
    if depth > _MAX_DEPTH:
        node.add_leaf("…")
        return
    if isinstance(data, dict):
        for key, value in list(data.items())[:_MAX_ITEMS]:
            if isinstance(value, (dict, list)):
                _add(node.add(str(key)), value, depth + 1)
            else:
                node.add_leaf(f"{key}: {_fmt(value)}")
    elif isinstance(data, list):
        for index, item in enumerate(data[:_MAX_ITEMS]):
            if isinstance(item, (dict, list)):
                _add(node.add(f"[{index}]"), item, depth + 1)
            else:
                node.add_leaf(f"[{index}] {_fmt(item)}")
    else:
        node.add_leaf(_fmt(data))


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)
