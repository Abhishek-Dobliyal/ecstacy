from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api import types as pdt

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
    mx = max(values) if values else 1.0
    return [_heat_color(v, mx, theme) for v in values]


def _theme_palette(app) -> list[str]:
    t = app.current_theme
    return [t.primary, t.accent, t.secondary]


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
    bucket_size = (n - 2) / (threshold - 2)
    prev_x = float(x[0])
    prev_y = float(y[0])
    for i in range(threshold - 2):
        a = int(np.floor(i * bucket_size)) + 1
        b = int(np.floor((i + 1) * bucket_size)) + 1
        bx = x[a:b]
        by = y[a:b]
        if len(bx) == 0:
            out_x[i + 1] = prev_x
            out_y[i + 1] = prev_y
            continue
        c = int(np.floor((i + 1) * bucket_size)) + 1
        d = min(int(np.floor((i + 2) * bucket_size)) + 1, n)
        if c < d:
            avg_x = float(np.mean(x[c:d]))
            avg_y = float(np.mean(y[c:d]))
        else:
            avg_x = float(x[-1])
            avg_y = float(y[-1])
        areas = np.abs(
            prev_x * (by - avg_y)
            + bx * (avg_y - prev_y)
            + avg_x * (prev_y - by)
        )
        idx = int(np.argmax(areas))
        out_x[i + 1] = float(bx[idx])
        out_y[i + 1] = float(by[idx])
        prev_x = float(bx[idx])
        prev_y = float(by[idx])
    out_x[-1] = x[-1]
    out_y[-1] = y[-1]
    return out_x, out_y


def _downsample_xy(
    x: np.ndarray, y: np.ndarray, threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    return _lttb(x, y, threshold)
