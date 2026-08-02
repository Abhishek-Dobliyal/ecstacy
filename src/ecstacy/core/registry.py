from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from textual.widget import Widget

    from ecstacy.sources.base import Source

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, label: str) -> None:
        self._label = label
        self._items: dict[str, T] = {}

    def register(self, name: str) -> Callable[[T], T]:
        def wrapper(item: T) -> T:
            self._items[name] = item
            return item

        return wrapper

    def get(self, name: str) -> T:
        if name not in self._items:
            raise KeyError(f"unknown {self._label}: {name}")
        return self._items[name]

    def has(self, name: str) -> bool:
        return name in self._items

    def names(self) -> list[str]:
        return sorted(self._items)


sources: Registry[type[Source]] = Registry("source")  # type: ignore[valid-type]
viz: Registry[type[Widget]] = Registry("viz")  # type: ignore[valid-type]
