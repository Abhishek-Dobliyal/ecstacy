from __future__ import annotations

from collections.abc import Callable

from ecstacy.core.dataset import DataSet

Listener = Callable[[str, DataSet], None]


class Store:
    def __init__(self) -> None:
        self._datasets: dict[str, DataSet] = {}
        self._listeners: list[Listener] = []

    def set(self, source_id: str, dataset: DataSet) -> None:
        self._datasets[source_id] = dataset
        for listener in list(self._listeners):
            listener(source_id, dataset)

    def get(self, source_id: str) -> DataSet | None:
        return self._datasets.get(source_id)

    def ids(self) -> list[str]:
        return list(self._datasets)

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)
