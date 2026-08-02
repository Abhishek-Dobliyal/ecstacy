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
        if value < 0:
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
    where: str | None = None
    group_by: list[str] = Field(default_factory=list)
    select: list[str] = Field(default_factory=list)
    limit: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PanelConfig:
        payload = dict(data)
        for field in ("y", "group_by", "select"):
            v = payload.get(field)
            if isinstance(v, str):
                payload[field] = [v]
        return cls(**payload)


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str | None = None
    refresh: str | None = None
    sources: list[SourceSpec] = Field(default_factory=list)
    panels: list[PanelConfig] = Field(default_factory=list)

    @field_validator("refresh")
    @classmethod
    def _validate_refresh(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parse_duration(value)
        except Exception as exc:
            raise ValueError(f"invalid refresh duration {value!r}") from exc
        return value

    @model_validator(mode="after")
    def validate_panel_sources(self) -> DashboardConfig:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for spec in self.sources:
            if spec.id in seen:
                duplicates.add(spec.id)
            seen.add(spec.id)
        if duplicates:
            raise ConfigError(
                f"duplicate source id(s): {', '.join(sorted(duplicates))}"
            )
        for panel in self.panels:
            if panel.source not in seen:
                raise ConfigError(
                    f"panel references unknown source: {panel.source!r}"
                )
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DashboardConfig:
        known = {"theme", "refresh", "sources", "panels"}
        extras = set(data) - known
        if extras:
            raise ConfigError(
                f"unknown dashboard field(s): {', '.join(sorted(extras))}"
            )
        sources = [SourceSpec.from_dict(s) for s in data.get("sources", [])]
        panels = [PanelConfig.from_dict(p) for p in data.get("panels", [])]
        return cls(
            theme=data.get("theme"),
            refresh=data.get("refresh"),
            sources=sources,
            panels=panels,
        )
