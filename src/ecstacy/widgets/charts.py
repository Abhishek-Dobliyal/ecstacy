from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pandas.api import types as pdt

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric

# Used by benchmarks; the TUI uses PlotWidget._budget() instead.
MAX_CHART_POINTS = 1000


# Helpers

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


# LTTB downsampling

def _lttb(
    x: np.ndarray, y: np.ndarray, threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets downsampling.

    Reduces *(x, y)* to at most *threshold* points while preserving the
    visual shape (peaks and valleys) at O(n) cost over the input length.
    The first and last points are always kept.
    """
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
        # Average of the next bucket (triangle's third point).
        c = int(np.floor((i + 1) * bucket_size)) + 1
        d = min(int(np.floor((i + 2) * bucket_size)) + 1, n)
        if c < d:
            avg_x = float(np.mean(x[c:d]))
            avg_y = float(np.mean(y[c:d]))
        else:
            avg_x = float(x[-1])
            avg_y = float(y[-1])
        # Triangle area for each candidate — maximise it.
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
    """LTTB downsample a paired (x, y) series, keeping points aligned."""
    return _lttb(x, y, threshold)


# Payloads

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


# Line

@registry.viz.register("line")
class LineChart(PlotWidget):
    viz_name = "line"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        ycols = [c for c in mapping.y if c in frame.columns] or _numeric_columns(frame)
        if not ycols:
            return _LinePayload(title="line chart needs a numeric column")
        xcol = mapping.x if mapping.x and mapping.x in frame.columns else None
        work = frame
        series_list: list[_LineSeries] = []
        downsampled = False
        for col in ycols:
            yvals_raw = numeric(work[col]).dropna()
            if yvals_raw.empty:
                continue
            if xcol is not None and xcol in work.columns:
                x_raw = _to_numeric_or_timestamp(work[xcol])
                # Align x to y's non-null index.
                x_aligned = x_raw.loc[yvals_raw.index].dropna()
                y_aligned = yvals_raw.loc[x_aligned.index]
                if len(y_aligned) > budget:
                    xs, ys = _downsample_xy(
                        x_aligned.to_numpy(dtype=float),
                        y_aligned.to_numpy(dtype=float),
                        budget,
                    )
                    series_list.append(_LineSeries(x=xs.tolist(), y=ys.tolist(), label=col))
                    downsampled = True
                else:
                    series_list.append(_LineSeries(
                        x=x_aligned.to_numpy(dtype=float).tolist(),
                        y=y_aligned.to_numpy(dtype=float).tolist(),
                        label=col,
                    ))
            else:
                yvals = yvals_raw.to_numpy(dtype=float)
                if len(yvals) > budget:
                    idx = np.arange(len(yvals))
                    _, ys = _lttb(idx, yvals, budget)
                    series_list.append(_LineSeries(x=None, y=ys.tolist(), label=col))
                    downsampled = True
                else:
                    series_list.append(_LineSeries(x=None, y=yvals.tolist(), label=col))
        title = " / ".join(ycols) if ycols else "line"
        if xcol:
            title = f"{title} over {xcol}"
        note = f"↓ {len(work):,} → {budget:,} points" if downsampled else None
        return _LinePayload(
            series=series_list,
            title=title,
            xlabel=xcol,
            ylabel=", ".join(ycols) or None,
            note=note,
        )

    def _paint(self, plt, payload: _LinePayload, theme) -> None:
        if not payload.series:
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        for i, s in enumerate(payload.series):
            color = _hex_rgb(palette[i % len(palette)])
            if s.x is not None:
                plt.plot(s.x, s.y, label=s.label, marker="braille", color=color)
            else:
                plt.plot(s.y, label=s.label, marker="braille", color=color)
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)


# Bar

@registry.viz.register("bar")
class BarChart(PlotWidget):
    viz_name = "bar"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        category = mapping.category or mapping.x
        value = mapping.y[0] if mapping.y else mapping.value
        if not category:
            cats = _category_columns(frame)
            category = cats[0] if cats else None
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not category or not value:
            return _BarPayload(title="bar chart needs a category and a numeric column")
        if category == value:
            return _BarPayload(title="bar chart needs distinct category and value columns")
        work = frame[[category, value]].copy()
        work[value] = numeric(work[value])
        work = work.dropna(subset=[category, value])
        if work.empty:
            return _BarPayload(title="bar chart has no data after removing NaNs")
        grouped = work.groupby(category)[value].sum().sort_values(ascending=False).head(30)
        labels = [str(i) for i in grouped.index]
        total_cats = work[category].nunique()
        note = None
        if len(grouped) < total_cats:
            note = f"top {len(grouped)} of {total_cats} categories"
        return _BarPayload(
            labels=labels,
            values=grouped.tolist(),
            title=f"{value} by {category}",
            xlabel=category,
            ylabel=value,
            note=note,
        )

    def _paint(self, plt, payload: _BarPayload, theme) -> None:
        if not payload.labels:
            _decorate(plt, payload.title)
            return
        colors = _heat_colors(payload.values, theme)
        plt.bar(
            payload.labels,
            payload.values,
            orientation="vertical",
            color=colors,
            marker="braille",
        )
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)


# Histogram

@registry.viz.register("histogram")
class Histogram(PlotWidget):
    viz_name = "histogram"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column:
            columns = _numeric_columns(frame)
            column = columns[0] if columns else None
        if not column:
            return _HistPayload(title="")
        # Truncate before coercion/dropna so they run on ≤budget rows.
        series = frame[column]
        total = len(series)
        if total > budget:
            series = series.tail(budget)
        values = numeric(series).dropna().tolist()
        if not values:
            return _HistPayload(title=f"no numeric data for {column}")
        note = f"last {len(values):,} of {total:,} values" if total > budget else None
        return _HistPayload(
            values=values,
            bins=mapping.bins,
            title=f"distribution of {column}",
            xlabel=column,
            ylabel="count",
            note=note,
        )

    def _paint(self, plt, payload: _HistPayload, theme) -> None:
        if not payload.values:
            if payload.title:
                _decorate(plt, payload.title)
            return
        plt.hist(payload.values, payload.bins, color=_hex_rgb(theme.accent), marker="braille")
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)


# Scatter

@registry.viz.register("scatter")
class Scatter(PlotWidget):
    viz_name = "scatter"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        x = mapping.x
        y = mapping.y[0] if mapping.y else mapping.value
        if not x or not y:
            nums = _numeric_columns(frame)
            if len(nums) >= 2:
                x, y = nums[0], nums[1]
        if not x or not y:
            return _ScatterPayload(title="scatter needs two numeric columns")
        # Drop NaN on the x/y pair; downsampling happens below if needed.
        work = frame[[x, y]].dropna()
        if work.empty:
            return _ScatterPayload(title="scatter has no overlapping x/y data")
        total = len(work)
        xvals = numeric(_to_numeric_or_timestamp(work[x])).to_numpy(dtype=float)
        yvals = numeric(work[y]).to_numpy(dtype=float)
        downsampled = len(xvals) > budget
        if downsampled:
            xvals, yvals = _downsample_xy(xvals, yvals, budget)
        note = f"↓ {total:,} → {budget:,} points" if downsampled else None
        return _ScatterPayload(
            x=xvals.tolist(),
            y=yvals.tolist(),
            title=f"{y} vs {x}",
            xlabel=x,
            ylabel=y,
            note=note,
        )

    def _paint(self, plt, payload: _ScatterPayload, theme) -> None:
        if not payload.x:
            _decorate(plt, payload.title)
            return
        plt.scatter(
            payload.x,
            payload.y,
            marker="braille",
            color=_hex_rgb(theme.secondary),
        )
        _decorate(plt, payload.title, xlabel=payload.xlabel, ylabel=payload.ylabel)


# Heatmap

@registry.viz.register("heatmap")
class Heatmap(PlotWidget):
    viz_name = "heatmap"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        numbers = frame.select_dtypes("number")
        if numbers.shape[1] < 2:
            return _HeatmapPayload(title="heatmap needs at least two numeric columns")
        total = len(numbers)
        if total > budget:
            numbers = numbers.tail(budget)
        corr = numbers.corr().fillna(0.0).round(2)
        note = f"last {len(numbers):,} of {total:,} rows" if total > budget else None
        return _HeatmapPayload(corr=corr, title="correlation matrix", note=note)

    def _paint(self, plt, payload: _HeatmapPayload, theme) -> None:
        if payload.corr is None:
            _decorate(plt, payload.title)
            return
        # plotext 5.3.2's draw_heatmap prints the frame to stdout (library
        # bug); suppress it so it doesn't corrupt the TUI display.
        with contextlib.redirect_stdout(io.StringIO()):
            plt.heatmap(payload.corr)
        _decorate(plt, payload.title)


# Box

@registry.viz.register("box")
class BoxPlot(PlotWidget):
    viz_name = "box"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        category = mapping.category or mapping.x
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not value:
            return _BoxPayload(title="box plot needs a numeric column")
        if not category or category not in frame.columns:
            category = None
        if category:
            grouped = frame.dropna(subset=[value, category]).groupby(category)[value]
            labels: list[str] = []
            data: list[list[float]] = []
            total_values = 0
            shown_values = 0
            for cat, group in grouped:
                vals = numeric(group).dropna()
                total_values += len(vals)
                if len(vals) > budget:
                    vals = vals.tail(budget)
                vals = vals.tolist()
                shown_values += len(vals)
                if not vals:
                    continue
                labels.append(str(cat))
                data.append(vals)
            if not data:
                return _BoxPayload(title=f"no data for {value}")
            note = None
            if total_values > shown_values:
                note = f"last {shown_values:,} of {total_values:,} values"
            return _BoxPayload(
                labels=labels,
                data=data,
                title=f"{value} by {category}",
                ylabel=value,
                note=note,
            )
        else:
            series = numeric(frame[value]).dropna()
            total = len(series)
            if total > budget:
                series = series.tail(budget)
            if series.empty:
                return _BoxPayload(title=f"no data for {value}")
            note = f"last {len(series):,} of {total:,} values" if total > budget else None
            return _BoxPayload(
                labels=[value],
                data=[series.tolist()],
                title=f"distribution of {value}",
                ylabel=value,
                note=note,
            )

    def _paint(self, plt, payload: _BoxPayload, theme) -> None:
        if not payload.data:
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        colors = [_hex_rgb(palette[0]), _hex_rgb(palette[1])]
        plt.box(payload.labels, payload.data, colors=colors)
        _decorate(plt, payload.title, ylabel=payload.ylabel)


# Proportion

@registry.viz.register("proportion")
class ProportionChart(PlotWidget):
    viz_name = "proportion"

    def _prepare(self, frame: pd.DataFrame, mapping: ColumnMapping, budget: int):
        category = mapping.category or mapping.x
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        if not category:
            cats = _category_columns(frame)
            category = cats[0] if cats else None
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not category or not value:
            return _ProportionPayload(
                title="proportion chart needs a category and a numeric column"
            )
        if category == value:
            return _ProportionPayload(
                title="proportion chart needs distinct category and value columns"
            )
        work = frame[[category, value]].copy()
        work[value] = numeric(work[value])
        work = work.dropna(subset=[category, value])
        if work.empty:
            return _ProportionPayload(title="proportion chart has no data after removing NaNs")
        grouped = work.groupby(category)[value].sum().sort_values(ascending=False).head(20)
        labels = [str(i) for i in grouped.index]
        total_cats = work[category].nunique()
        note = None
        if len(grouped) < total_cats:
            note = f"top {len(grouped)} of {total_cats} categories"
        return _ProportionPayload(
            labels=labels,
            values=grouped.tolist(),
            title=f"{value} by {category}",
            note=note,
        )

    def _paint(self, plt, payload: _ProportionPayload, theme) -> None:
        if not payload.labels:
            _decorate(plt, payload.title)
            return
        palette = [theme.primary, theme.accent, theme.secondary]
        colors = [_hex_rgb(palette[i % len(palette)]) for i in range(len(payload.labels))]
        # Horizontal bars as a pie substitute.
        plt.bar(
            payload.labels, payload.values,
            orientation="horizontal", color=colors, marker="braille",
        )
        _decorate(plt, payload.title)
