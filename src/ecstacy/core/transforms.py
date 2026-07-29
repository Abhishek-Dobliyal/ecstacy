from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ecstacy.core.dataset import EcstacyError


class TransformError(EcstacyError):
    """Raised when a transform cannot be applied."""


def _validate_transform_inputs(frame: pd.DataFrame, transform: Transform) -> None:
    if transform.limit is not None and transform.limit < 0:
        raise TransformError(f"limit must be non-negative, got {transform.limit}")
    if transform.where:
        try:
            frame.query(transform.where)
        except Exception as exc:
            raise TransformError(f"invalid where clause {transform.where!r}: {exc}") from exc
    if transform.group_by:
        missing = [c for c in transform.group_by if c not in frame.columns]
        if missing:
            raise TransformError(f"group_by columns not found: {', '.join(missing)}")
    if transform.resample or transform.time_column:
        if not transform.resample or not transform.time_column:
            raise TransformError("resample and time_column must both be provided")
        if transform.time_column not in frame.columns:
            raise TransformError(f"time_column not found: {transform.time_column}")


@dataclass
class Transform:
    select: list[str] | None = None
    where: str | None = None
    group_by: list[str] | None = None
    agg: str = "sum"
    resample: str | None = None
    time_column: str | None = None
    limit: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def apply(self, frame: pd.DataFrame) -> pd.DataFrame:
        _validate_transform_inputs(frame, self)
        result = frame
        if self.where:
            result = result.query(self.where)
        if self.resample and self.time_column:
            result = _resample(result, self.time_column, self.resample, self.agg)
        elif self.group_by:
            result = _aggregate(result, self.group_by, self.agg)
        if self.select:
            keep = [c for c in self.select if c in result.columns]
            result = result[keep]
        if self.limit is not None:
            result = result.head(self.limit)
        return result


def _aggregate(frame: pd.DataFrame, group_by: list[str], agg: str) -> pd.DataFrame:
    grouped = frame.groupby(group_by, dropna=False)
    try:
        return grouped.agg(agg, numeric_only=True).reset_index()
    except Exception as exc:
        raise TransformError(f"aggregation {agg!r} failed: {exc}") from exc


def _resample(frame: pd.DataFrame, time_column: str, rule: str, agg: str) -> pd.DataFrame:
    indexed = frame.copy()
    indexed[time_column] = pd.to_datetime(indexed[time_column], errors="coerce")
    indexed = indexed.dropna(subset=[time_column]).set_index(time_column)
    try:
        resampled = indexed.resample(rule).agg(agg, numeric_only=True)
    except Exception as exc:
        raise TransformError(f"resample {rule!r} failed: {exc}") from exc
    return resampled.reset_index()


def parse_transform_query(text: str) -> Transform:
    """Parse a transform query string into a Transform object.

    Supported clauses (separated by | or newlines):
      where <expr>          — pandas query expression
      group_by <col>[, ...]  — group by columns
      agg <func>            — aggregation function (sum, mean, count, ...)
      select <col>[, ...]    — select columns
      limit <n>             — limit to N rows
      resample <rule>       — resample rule (e.g. D, W, M)
      time <col>            — time column for resample

    Example: "where value > 100 | group_by region | agg mean | limit 10"
    """
    parts: dict[str, Any] = {}
    for segment in text.replace("\n", "|").split("|"):
        segment = segment.strip()
        if not segment:
            continue
        tokens = segment.split(None, 1)
        if len(tokens) < 2:
            continue
        keyword, rest = tokens[0].lower(), tokens[1].strip()
        if keyword == "where":
            parts["where"] = rest
        elif keyword == "group_by":
            parts["group_by"] = [c.strip() for c in rest.split(",") if c.strip()]
        elif keyword == "agg":
            parts["agg"] = rest
        elif keyword == "select":
            parts["select"] = [c.strip() for c in rest.split(",") if c.strip()]
        elif keyword == "limit":
            try:
                parts["limit"] = int(rest)
            except ValueError:
                raise TransformError(f"invalid limit value: {rest!r}") from None
        elif keyword == "resample":
            parts["resample"] = rest
        elif keyword == "time":
            parts["time_column"] = rest
    return Transform(
        select=parts.get("select"),
        where=parts.get("where"),
        group_by=parts.get("group_by"),
        agg=parts.get("agg", "sum"),
        resample=parts.get("resample"),
        time_column=parts.get("time_column"),
        limit=parts.get("limit"),
    )
