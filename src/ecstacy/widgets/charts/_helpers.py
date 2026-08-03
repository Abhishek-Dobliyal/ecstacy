from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api import types as pdt

from ecstacy.widgets.base import ColumnMapping

MAX_CHART_POINTS = 1000


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(c) for c in frame.select_dtypes("number").columns]


def _category_columns(frame: pd.DataFrame) -> list[str]:
    return [
        str(c)
        for c in frame.columns
        if pdt.is_object_dtype(frame[c])
        or pdt.is_string_dtype(frame[c])
        or isinstance(frame[c].dtype, pd.CategoricalDtype)
    ]


def _is_numeric(series: pd.Series) -> bool:
    return pdt.is_numeric_dtype(series)


def _is_datetime(series: pd.Series) -> bool:
    return pdt.is_datetime64_any_dtype(series)


def _to_numeric_or_timestamp(series: pd.Series) -> pd.Series:
    if _is_numeric(series):
        return pd.to_numeric(series, errors="coerce")
    if _is_datetime(series):
        return series.astype("int64") / 1e9
    coerced = pd.to_numeric(series, errors="coerce")
    if coerced.notna().any():
        return coerced
    return series


def _dropna_xy(frame: pd.DataFrame, x: str | None, ycols: list[str]) -> pd.DataFrame:
    cols = [c for c in ([x] if x else []) + ycols if c in frame.columns]
    return frame.dropna(subset=cols)


def _xvals(frame: pd.DataFrame, column: str | None) -> pd.Series | None:
    if not column or column not in frame.columns:
        return None
    series = frame[column]
    if _is_numeric(series) or _is_datetime(series):
        coerced = _to_numeric_or_timestamp(series)
        return coerced.dropna()
    return series.dropna()


def _hex_rgb(hex_str: str) -> tuple[int, int, int]:
    try:
        h = hex_str.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except Exception:
        return (128, 128, 128)


def _lerp_rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _heat_color(value: float, max_value: float, theme) -> tuple[int, int, int]:
    success = _hex_rgb(theme.success)
    warning = _hex_rgb(theme.warning)
    error = _hex_rgb(theme.error)
    ratio = max(0.0, min(1.0, value / max_value)) if max_value else 0.0
    if ratio < 0.5:
        return _lerp_rgb(success, warning, ratio * 2)
    return _lerp_rgb(warning, error, (ratio - 0.5) * 2)


def _heat_colors(values: list[float], theme) -> list[tuple[int, int, int]]:
    success = _hex_rgb(theme.success)
    warning = _hex_rgb(theme.warning)
    error = _hex_rgb(theme.error)
    mx = max(values) if values else 1.0
    colors: list[tuple[int, int, int]] = []
    for v in values:
        ratio = max(0.0, min(1.0, v / mx)) if mx else 0.0
        if ratio < 0.5:
            colors.append(_lerp_rgb(success, warning, ratio * 2))
        else:
            colors.append(_lerp_rgb(warning, error, (ratio - 0.5) * 2))
    return colors


def _theme_palette(theme) -> list[str]:
    return [theme.primary, theme.accent, theme.secondary]


def _grouped_topn(
    frame: pd.DataFrame,
    mapping: ColumnMapping,
    *,
    top_n: int,
    kind_label: str,
    prefer_value: bool = False,
) -> tuple[list[str], list[float], str, str | None, str, str] | str:
    """Shared prepare logic for bar/proportion charts.

    Returns ``(labels, values, title, note, category, value)`` on success,
    or an error message string when the mapping is invalid or the frame
    has no data.
    """
    category = mapping.category or mapping.x
    if prefer_value:
        value = mapping.value or (mapping.y[0] if mapping.y else None)
    else:
        value = mapping.y[0] if mapping.y else mapping.value
    if not category:
        cats = _category_columns(frame)
        category = cats[0] if cats else None
    if not value:
        nums = _numeric_columns(frame)
        value = nums[0] if nums else None
    if not category or not value:
        return f"{kind_label} needs a category and a numeric column"
    if category == value:
        return f"{kind_label} needs distinct category and value columns"
    work = frame[[category, value]].copy()
    work[value] = pd.to_numeric(work[value], errors="coerce")
    work = work.dropna(subset=[category, value])
    if work.empty:
        return f"{kind_label} has no data after removing NaNs"
    grouped = (
        work.groupby(category)[value].sum().sort_values(ascending=False).head(top_n)
    )
    labels = [str(i) for i in grouped.index]
    total_cats = work[category].nunique()
    note = f"top {len(grouped)} of {total_cats} categories" if len(grouped) < total_cats else None
    title = f"{value} by {category}"
    return labels, grouped.tolist(), title, note, category, value


def _decorate(plt, title: str, xlabel: str | None = None, ylabel: str | None = None) -> None:
    plt.grid(True, True)
    plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)


def _lttb(
    x: np.ndarray, y: np.ndarray, threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets downsampling."""
    n = len(x)
    if n <= threshold or threshold < 3:
        return x, y
    out_x = np.empty(threshold)
    out_y = np.empty(threshold)
    out_x[0] = x[0]
    out_y[0] = y[0]
    out_x[-1] = x[-1]
    out_y[-1] = y[-1]
    bucket_size = (n - 2) / (threshold - 2)

    # Precompute bucket boundaries as integer arrays.
    num_buckets = threshold - 2
    starts = np.floor(np.arange(num_buckets) * bucket_size).astype(int) + 1
    mids = np.floor(np.arange(1, num_buckets + 1) * bucket_size).astype(int) + 1
    ends = np.minimum(
        np.floor(np.arange(2, num_buckets + 2) * bucket_size).astype(int) + 1, n
    )

    # Precompute next-bucket averages via cumulative sums (one pass, no per-iteration np.mean).
    cumsum_x = np.cumsum(x)
    cumsum_y = np.cumsum(y)
    avg_x = np.empty(num_buckets)
    avg_y = np.empty(num_buckets)
    for i in range(num_buckets):
        c, d = mids[i], ends[i]
        if c < d:
            sx_prev = cumsum_x[c - 1] if c > 0 else 0.0
            sy_prev = cumsum_y[c - 1] if c > 0 else 0.0
            avg_x[i] = (cumsum_x[d - 1] - sx_prev) / (d - c)
            avg_y[i] = (cumsum_y[d - 1] - sy_prev) / (d - c)
        else:
            avg_x[i] = float(x[-1])
            avg_y[i] = float(y[-1])

    prev_x = float(x[0])
    prev_y = float(y[0])
    for i in range(num_buckets):
        a, b = starts[i], mids[i]
        bx = x[a:b]
        by = y[a:b]
        if len(bx) == 0:
            out_x[i + 1] = prev_x
            out_y[i + 1] = prev_y
            continue
        ax = avg_x[i]
        ay = avg_y[i]
        areas = np.abs(
            prev_x * (by - ay)
            + bx * (ay - prev_y)
            + ax * (prev_y - by)
        )
        idx = int(np.argmax(areas))
        val_x = float(bx[idx])
        val_y = float(by[idx])
        out_x[i + 1] = val_x
        out_y[i + 1] = val_y
        prev_x = val_x
        prev_y = val_y
    return out_x, out_y


def _downsample_xy(
    x: np.ndarray, y: np.ndarray, threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    return _lttb(x, y, threshold)
