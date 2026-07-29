from __future__ import annotations

from ecstacy.core.dataset import DataSet


class Store:
    def __init__(self) -> None:
        self._datasets: dict[str, DataSet] = {}

    def set(self, source_id: str, dataset: DataSet) -> None:
        self._datasets[source_id] = dataset

    def get(self, source_id: str) -> DataSet | None:
        return self._datasets.get(source_id)

    def ids(self) -> list[str]:
        return list(self._datasets)
