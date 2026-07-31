from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class _LineSeries:
    x: list[float] | None  # None → use implicit y index
    y: list[float]
    label: str


@dataclass
class _LinePayload:
    series: list[_LineSeries] = field(default_factory=list)
    title: str = ""
    xlabel: str | None = None
    ylabel: str | None = None
    note: str | None = None


@dataclass
class _BarPayload:
    labels: list[str] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    title: str = ""
    xlabel: str | None = None
    ylabel: str | None = None
    note: str | None = None


@dataclass
class _HistPayload:
    values: list[float] = field(default_factory=list)
    bins: int = 20
    title: str = ""
    xlabel: str | None = None
    ylabel: str | None = None
    note: str | None = None


@dataclass
class _ScatterPayload:
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    title: str = ""
    xlabel: str | None = None
    ylabel: str | None = None
    note: str | None = None


@dataclass
class _HeatmapPayload:
    corr: pd.DataFrame | None = None
    title: str = ""
    note: str | None = None


@dataclass
class _BoxPayload:
    labels: list[str] = field(default_factory=list)
    data: list[list[float]] = field(default_factory=list)
    title: str = ""
    ylabel: str | None = None
    note: str | None = None


@dataclass
class _ProportionPayload:
    labels: list[str] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    title: str = ""
    note: str | None = None
