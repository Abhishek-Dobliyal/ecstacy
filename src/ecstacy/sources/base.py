from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, ConfigDict, Field

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet, EcstacyError


class SourceError(EcstacyError):
    """Raised when a source fails to load or is misconfigured."""

    def __init__(self, message: str, source_id: str | None = None) -> None:
        super().__init__(message)
        self.source_id = source_id


class Source(ABC):
    kind: str = "base"
    supports_stream: bool = False

    def __init__(self, id: str, **params: Any) -> None:
        self.id = id
        self.params = params

    @abstractmethod
    def fetch(self) -> DataSet:
        ...

    def describe(self) -> str:
        return f"{self.kind}:{self.id}"

    async def stream(self) -> AsyncIterator[DataSet]:
        raise NotImplementedError(f"{self.kind} source does not support streaming")
        yield  # pragma: no cover


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    id: str
    params: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceSpec":
        payload = dict(data)
        kind = payload.pop("kind")
        id = payload.pop("id", kind)
        return cls(kind=kind, id=id, params=payload)


def create_source(spec: SourceSpec) -> Source:
    if not registry.sources.has(spec.kind):
        known = ", ".join(registry.sources.names()) or "none"
        raise SourceError(
            f"unknown source kind: {spec.kind!r} (known: {known})",
            source_id=spec.id,
        )
    factory = registry.sources.get(spec.kind)
    return factory(id=spec.id, **spec.params)
