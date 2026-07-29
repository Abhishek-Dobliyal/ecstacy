from __future__ import annotations

import contextlib
import io

import pandas as pd
from pandas.api import types as pdt

from ecstacy.core import registry
from ecstacy.widgets.base import ColumnMapping, PlotWidget, numeric

MAX_CHART_POINTS = 1000


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [str(c) for c in frame.select_dtypes("number").columns]


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


@registry.viz.register("line")
class LineChart(PlotWidget):
    viz_name = "line"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        ycols = [c for c in mapping.y if c in frame.columns] or _numeric_columns(frame)
        xvals = _xvals(frame, mapping.x)
        palette = _theme_palette(self.app)
        work = _dropna_xy(frame, mapping.x, ycols)
        if len(work) > MAX_CHART_POINTS:
            work = work.tail(MAX_CHART_POINTS)
            if xvals is not None:
                xvals = xvals.tail(MAX_CHART_POINTS)
        for i, col in enumerate(ycols):
            color = _hex_rgb(palette[i % len(palette)])
            series = numeric(work[col]).dropna()
            yvals = series.tolist()
            if not yvals:
                continue
            current_x = xvals.loc[series.index] if xvals is not None else None
            if current_x is not None:
                plt.plot(
                    current_x.tolist(), yvals, label=col, marker="braille", color=color
                )
            else:
                plt.plot(yvals, label=col, marker="braille", color=color)
        title = " / ".join(ycols) if ycols else "line"
        if mapping.x:
            title = f"{title} over {mapping.x}"
        _decorate(plt, title, xlabel=mapping.x, ylabel=", ".join(ycols) or None)


@registry.viz.register("bar")
class BarChart(PlotWidget):
    viz_name = "bar"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        category = mapping.category or mapping.x
        value = mapping.y[0] if mapping.y else mapping.value
        if not category:
            cats = [
                c for c in frame.columns
                if frame[c].dtype == "object"
                or str(frame[c].dtype).startswith("category")
            ]
            category = cats[0] if cats else None
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not category or not value:
            plt.title("bar chart needs a category and a numeric column")
            return
        work = frame[[category, value]]
        work[value] = numeric(work[value])
        work = work.dropna(subset=[category, value])
        if work.empty:
            plt.title("bar chart has no data after removing NaNs")
            return
        grouped = work.groupby(category)[value].sum().sort_values(ascending=False).head(30)
        labels = [str(i) for i in grouped.index]
        colors = _heat_colors(grouped.tolist(), self.app.current_theme)
        plt.bar(labels, grouped.tolist(), orientation="vertical", color=colors, marker="braille")
        _decorate(plt, f"{value} by {category}", xlabel=category, ylabel=value)


@registry.viz.register("histogram")
class Histogram(PlotWidget):
    viz_name = "histogram"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        column = mapping.value or (mapping.y[0] if mapping.y else None)
        if not column:
            columns = _numeric_columns(frame)
            column = columns[0] if columns else None
        if not column:
            return
        values = numeric(frame[column]).dropna().tolist()
        if not values:
            plt.title(f"no numeric data for {column}")
            return
        plt.hist(
            values, mapping.bins, color=_hex_rgb(self.app.current_theme.accent), marker="braille"
        )
        _decorate(plt, f"distribution of {column}", xlabel=column, ylabel="count")


@registry.viz.register("scatter")
class Scatter(PlotWidget):
    viz_name = "scatter"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        x = mapping.x
        y = mapping.y[0] if mapping.y else mapping.value
        if not x or not y:
            nums = _numeric_columns(frame)
            if len(nums) >= 2:
                x, y = nums[0], nums[1]
            elif len(nums) == 1:
                x = nums[0]
        if not x or not y:
            plt.title("scatter needs two numeric columns")
            return
        work = _dropna_xy(frame, x, [y])
        if len(work) > MAX_CHART_POINTS:
            work = work.tail(MAX_CHART_POINTS)
        xvals = numeric(work[x]).dropna()
        yvals = numeric(work[y]).dropna()
        common = xvals.index.intersection(yvals.index)
        if not len(common):
            plt.title("scatter has no overlapping x/y data")
            return
        plt.scatter(
            xvals.loc[common].tolist(),
            yvals.loc[common].tolist(),
            marker="braille",
            color=_hex_rgb(self.app.current_theme.secondary),
        )
        _decorate(plt, f"{y} vs {x}", xlabel=x, ylabel=y)


@registry.viz.register("heatmap")
class Heatmap(PlotWidget):
    viz_name = "heatmap"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        numbers = frame.select_dtypes("number")
        if numbers.shape[1] < 2:
            plt.title("heatmap needs at least two numeric columns")
            return
        corr = numbers.corr().fillna(0.0).round(2)
        # plotext 5.3.2's draw_heatmap prints the frame to stdout (library
        # bug); suppress it so it doesn't corrupt the TUI display.
        with contextlib.redirect_stdout(io.StringIO()):
            plt.heatmap(corr)
        _decorate(plt, "correlation matrix")


@registry.viz.register("box")
class BoxPlot(PlotWidget):
    viz_name = "box"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        category = mapping.category or mapping.x
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not value:
            plt.title("box plot needs a numeric column")
            return
        if not category or category not in frame.columns:
            category = None
        palette = _theme_palette(self.app)
        colors = [_hex_rgb(palette[0]), _hex_rgb(palette[1])]
        if category:
            grouped = frame.dropna(subset=[value, category]).groupby(category)[value]
            labels: list[str] = []
            data: list[list[float]] = []
            for cat, group in grouped:
                vals = numeric(group).dropna().tolist()
                if not vals:
                    continue
                labels.append(str(cat))
                data.append(vals)
            if not data:
                plt.title(f"no data for {value}")
                return
            plt.box(labels, data, colors=colors)
            _decorate(plt, f"{value} by {category}", ylabel=value)
        else:
            series = numeric(frame[value]).dropna()
            if series.empty:
                plt.title(f"no data for {value}")
                return
            plt.box([value], [series.tolist()], colors=colors)
            _decorate(plt, f"distribution of {value}", ylabel=value)


@registry.viz.register("proportion")
class ProportionChart(PlotWidget):
    viz_name = "proportion"

    def _draw(self, plt, frame: pd.DataFrame, mapping: ColumnMapping) -> None:
        category = mapping.category or mapping.x
        value = mapping.value or (mapping.y[0] if mapping.y else None)
        if not category:
            cats = [
                str(c) for c in frame.columns
                if frame[c].dtype == "object" or str(frame[c].dtype).startswith("category")
            ]
            category = cats[0] if cats else None
        if not value:
            nums = _numeric_columns(frame)
            value = nums[0] if nums else None
        if not category or not value:
            plt.title("proportion chart needs a category and a numeric column")
            return
        work = frame[[category, value]]
        work[value] = numeric(work[value])
        work = work.dropna(subset=[category, value])
        if work.empty:
            plt.title("proportion chart has no data after removing NaNs")
            return
        grouped = work.groupby(category)[value].sum().sort_values(ascending=False).head(20)
        labels = [str(i) for i in grouped.index]
        values = grouped.tolist()
        palette = _theme_palette(self.app)
        colors = [_hex_rgb(palette[i % len(palette)]) for i in range(len(labels))]
        # plotext has no pie primitive; horizontal bars are the proportion view
        plt.bar(labels, values, orientation="horizontal", color=colors, marker="braille")
        _decorate(plt, f"{value} by {category}")
