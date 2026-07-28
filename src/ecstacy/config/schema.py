from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ecstacy.config import defaults
from ecstacy.core.dataset import EcstacyError
from ecstacy.sources.base import SourceSpec
from ecstacy.util.timeparse import parse_duration


class ConfigError(EcstacyError):
    """Raised when configuration is invalid."""


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    theme: str = defaults.DEFAULT_THEME
    refresh: str = defaults.DEFAULT_REFRESH
    splash: bool = True
    max_rows: int = defaults.DEFAULT_MAX_ROWS

    @field_validator("refresh")
    @classmethod
    def _validate_refresh(cls, value: str) -> str:
        try:
            parse_duration(value)
        except Exception as exc:
            raise ValueError(f"invalid refresh duration {value!r}") from exc
        return value

    @field_validator("max_rows")
    @classmethod
    def _validate_max_rows(cls, value: int) -> int:
        if value is not None and value < 0:
            raise ValueError("max_rows must be non-negative")
        return value


class PanelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    viz: str
    x: str | None = None
    y: list[str] = Field(default_factory=list)
    category: str | None = None
    value: str | None = None
    agg: str = "sum"
    bins: int = 20
    layout: dict[str, int] = Field(default_factory=dict)
    where: str | None = None
    group_by: list[str] = Field(default_factory=list)
    select: list[str] = Field(default_factory=list)
    limit: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PanelConfig":
        payload = dict(data)
        y = payload.get("y")
        if isinstance(y, str):
            payload["y"] = [y]
        gb = payload.get("group_by")
        if isinstance(gb, str):
            payload["group_by"] = [gb]
        sel = payload.get("select")
        if isinstance(sel, str):
            payload["select"] = [sel]
        return cls(**payload)


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str | None = None
    refresh: str | None = None
    sources: list[SourceSpec] = Field(default_factory=list)
    panels: list[PanelConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_panel_sources(self) -> "DashboardConfig":
        source_ids = {s.id for s in self.sources}
        for panel in self.panels:
            if panel.source not in source_ids:
                raise ConfigError(
                    f"panel references unknown source: {panel.source!r}"
                )
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardConfig":
        sources = [SourceSpec.from_dict(s) for s in data.get("sources", [])]
        panels = [PanelConfig.from_dict(p) for p in data.get("panels", [])]
        return cls(
            theme=data.get("theme"),
            refresh=data.get("refresh"),
            sources=sources,
            panels=panels,
        )
