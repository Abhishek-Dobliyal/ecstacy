from __future__ import annotations

from typing import Any

from textual.widgets import Tree

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping

_MAX_ITEMS = 200


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


def _add(node, data: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                _add(node.add(str(key)), value)
            else:
                node.add_leaf(f"{key}: {value}")
    elif isinstance(data, list):
        for index, item in enumerate(data[:_MAX_ITEMS]):
            if isinstance(item, (dict, list)):
                _add(node.add(f"[{index}]"), item)
            else:
                node.add_leaf(f"[{index}] {item}")
    else:
        node.add_leaf(str(data))
