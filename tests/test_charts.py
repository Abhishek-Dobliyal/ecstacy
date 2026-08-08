from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ecstacy.widgets import charts
from ecstacy.widgets.base import ColumnMapping


def test_hex_rgb_parses_shorthand():
    assert charts._hex_rgb("#abc") == (170, 187, 204)


def test_hex_rgb_falls_back_on_invalid():
    assert charts._hex_rgb("not-a-color") == (128, 128, 128)


def test_xvals_datetime_to_numeric():
    frame = pd.DataFrame(
        {"timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]), "value": [1, 2]}
    )
    xvals = charts._xvals(frame, "timestamp")
    assert xvals is not None
    assert xvals.dtype == "float64"


def test_xvals_numeric():
    frame = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
    xvals = charts._xvals(frame, "x")
    assert list(xvals) == [1, 2, 3]


def test_dropna_xy_removes_nan_rows():
    frame = pd.DataFrame({"x": [1.0, None, 3.0], "y": [10.0, 20.0, None]})
    result = charts._dropna_xy(frame, "x", ["y"])
    assert len(result) == 1
    assert result.iloc[0]["x"] == 1.0
    assert result.iloc[0]["y"] == 10.0


def test_to_numeric_or_timestamp_converts_datetime():
    series = pd.Series(pd.to_datetime(["2024-01-01", "2024-01-02"]))
    result = charts._to_numeric_or_timestamp(series)
    assert result.dtype == "float64"


def test_hex_rgb_returns_plotext_rgb_tuple():
    """plotext only accepts int/256-code or (r,g,b) tuples, not hex strings."""
    from plotext._utility import is_rgb_color

    rgb = charts._hex_rgb("#7cdf32")
    assert isinstance(rgb, tuple)
    assert len(rgb) == 3
    assert all(isinstance(v, int) for v in rgb)
    assert is_rgb_color(rgb)


def test_hex_rgb_rejects_hex_string_for_plotext():
    """Sanity: confirm that raw hex strings are NOT accepted by plotext."""
    from plotext._utility import is_rgb_color, is_string_color

    assert not is_string_color("#7cdf32")
    assert not is_rgb_color("#7cdf32")


@pytest.mark.asyncio
async def test_line_chart_renders_in_light_theme():
    from textual.app import App
    from textual.theme import Theme

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    light = Theme(
        name="ecstacy-light",
        primary="#3d8f0d",
        secondary="#0891b2",
        accent="#b45309",
        foreground="#1f2937",
        background="#f8fafc",
        surface="#ffffff",
        panel="#eef2f7",
        success="#16a34a",
        warning="#d97706",
        error="#dc2626",
        dark=False,
    )

    class _App(App):
        def on_mount(self):
            self.register_theme(light)
            self.theme = "ecstacy-light"
            df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [4, 3, 2, 1]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "line"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
    # no crash == pass


@pytest.mark.asyncio
async def test_sparkline_renders_full_canvas():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"value": list(range(20))})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "sparkline"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
    # no crash == pass


@pytest.mark.asyncio
async def test_line_chart_caps_points_for_large_frame():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"a": list(range(5000)), "b": list(range(5000))})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "line"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
    # no crash == pass


def test_sparkline_downsamples_via_lttb_above_threshold():
    """Above _MAX_POINTS the sparkline downsamples via LTTB (preserving shape)
    instead of truncating to the last _MAX_POINTS, and surfaces a note."""
    from ecstacy.widgets.base import ColumnMapping
    from ecstacy.widgets.spark import _MAX_POINTS, SparklineView

    n = _MAX_POINTS * 4
    df = pd.DataFrame({"value": list(range(n))})
    payload = SparklineView()._prepare(df, ColumnMapping(value="value"), 100)
    assert len(payload.values) == _MAX_POINTS
    assert payload.note is not None and "↓" in payload.note
    # First and last points are preserved by LTTB (endpoints are kept).
    assert payload.values[0] == 0
    assert payload.values[-1] == n - 1


def test_sparkline_below_threshold_keeps_all_and_no_note():
    """Below _MAX_POINTS no downsampling happens and no note is set."""
    from ecstacy.widgets.base import ColumnMapping
    from ecstacy.widgets.spark import SparklineView

    df = pd.DataFrame({"value": list(range(50))})
    payload = SparklineView()._prepare(df, ColumnMapping(value="value"), 100)
    assert len(payload.values) == 50
    assert payload.note is None
    assert payload.title == "value · last 50"


def test_max_chart_points_constant():
    assert charts.MAX_CHART_POINTS == 1000


@pytest.mark.asyncio
async def test_box_plot_renders_with_category():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame(
                {"region": ["us", "eu", "us", "eu", "us"], "value": [10, 20, 30, 15, 25]}
            )
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "box"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_box_plot_renders_without_category():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"value": [10, 20, 30, 40, 50]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "box"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_box_plot_no_numeric_column():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "box"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_proportion_chart_renders():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame(
                {"region": ["us", "eu", "ap"], "value": [100, 50, 25]}
            )
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "proportion"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


@pytest.mark.asyncio
async def test_proportion_chart_no_numeric_column():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu"]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "proportion"))

    async with _App().run_test() as pilot:
        for _ in range(6):
            await pilot.pause()


def test_pie_alias_resolves_to_proportion():
    from ecstacy.widgets import create_viz, resolve_viz, viz_names
    from ecstacy.widgets.charts import ProportionChart

    assert resolve_viz("pie") == "proportion"
    assert isinstance(create_viz("pie"), ProportionChart)
    assert "pie" not in viz_names()
    assert "proportion" in viz_names()


@pytest.mark.asyncio
async def test_chart_screen_pie_alias_lands_on_proportion():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.widgets.charts import ProportionChart

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame({"region": ["us", "eu"], "value": [1, 2]})
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "pie"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        assert app.screen.names[app.screen.index] == "proportion"
        assert isinstance(app.screen.query_one("#viz-holder").children[0], ProportionChart)


@pytest.mark.asyncio
async def test_chart_screen_transform_bar_filters_data():
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen

    class _App(App):
        def on_mount(self):
            df = pd.DataFrame(
                {"region": ["us", "eu", "us", "eu"], "value": [10, 20, 5, 30]}
            )
            ds = DataSet.from_dataframe(df, source_id="s", kind="test")
            self.push_screen(ChartScreen(ds, "table"))

    app = _App()
    async with app.run_test() as pilot:
        for _ in range(6):
            await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ChartScreen)
        screen._transform_query = "where value > 10"
        await screen._render_current()
        await pilot.pause()
        transformed = screen._get_transformed_dataset()
        assert transformed.meta.rows == 2
        assert "eu" in list(transformed.frame["region"])


@pytest.mark.asyncio
async def test_chart_screen_refreshes_data(tmp_path):
    from textual.app import App

    from ecstacy.core.dataset import DataSet
    from ecstacy.screens.chart import ChartScreen
    from ecstacy.sources.base import SourceSpec

    csv = tmp_path / "live.csv"
    csv.write_text("a,b\n1,10\n2,20\n")

    spec = SourceSpec(kind="file", id="live", params={"path": str(csv)})

    class _App(App):
        def on_mount(self):
            import pandas as pd
            df = pd.read_csv(csv)
            ds = DataSet.from_dataframe(df, source_id="live", kind="file")
            self.push_screen(ChartScreen(ds, "table", spec=spec, refresh=0.1))

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen.refresh_interval == 0.1
        assert screen._scheduler is not None

        csv.write_text("a,b\n1,10\n2,20\n3,30\n4,40\n")
        await app.workers.wait_for_complete()
        for _ in range(10):
            await pilot.pause()
        assert screen.dataset.meta.rows == 4
        screen._stop_refresh()



def test_category_columns_finds_pandas3_string_columns():
    frame = pd.DataFrame({"region": ["us", "eu"], "value": [1, 2]})
    assert charts._category_columns(frame) == ["region"]


# LTTB downsampling

def test_lttb_preserves_extremes():
    """LTTB retains a spike that tail() would drop."""
    y = np.zeros(1000)
    y[500] = 100.0
    x = np.arange(1000, dtype=float)
    _, sy = charts._lttb(x, y, 100)
    assert 100.0 in sy
    # tail(100) would miss the spike entirely (it's at index 500)


def test_lttb_output_length():
    x = np.arange(10000, dtype=float)
    y = np.sin(x / 100)
    sx, sy = charts._lttb(x, y, 500)
    assert len(sx) == 500
    assert len(sy) == 500


def test_lttb_short_series_unchanged():
    x = np.arange(10, dtype=float)
    y = np.arange(10, dtype=float)
    sx, sy = charts._lttb(x, y, 100)
    assert len(sx) == 10
    assert list(sx) == list(x)
    assert list(sy) == list(y)


def test_lttb_preserves_endpoints():
    x = np.arange(1000, dtype=float)
    y = np.sin(x / 100)
    sx, sy = charts._lttb(x, y, 50)
    assert sx[0] == x[0]
    assert sx[-1] == x[-1]
    assert sy[0] == y[0]
    assert sy[-1] == y[-1]


def test_lttb_threshold_below_3():
    x = np.arange(100, dtype=float)
    y = np.arange(100, dtype=float)
    sx, sy = charts._lttb(x, y, 2)
    assert len(sx) == 100
    assert list(sx) == list(x)


def test_lttb_exact_fit():
    x = np.arange(50, dtype=float)
    y = np.arange(50, dtype=float)
    sx, sy = charts._lttb(x, y, 50)
    assert len(sx) == 50


def test_lttb_empty_bucket_fallback():
    x = np.array([0.0, 1, 2, 10, 11, 12])
    y = np.array([0.0, 1, 2, 10, 11, 12])
    sx, sy = charts._lttb(x, y, 4)
    assert len(sx) == 4
    assert sx[0] == 0.0
    assert sx[-1] == 12.0


def test_lttb_monotonic_x_preserved():
    x = np.arange(500, dtype=float)
    y = np.sin(x / 50)
    sx, _ = charts._lttb(x, y, 100)
    diffs = np.diff(sx)
    assert (diffs > 0).all()


def test_lttb_nan_y_no_crash():
    x = np.arange(100, dtype=float)
    y = np.arange(100, dtype=float)
    y[50] = np.nan
    sx, sy = charts._lttb(x, y, 20)
    assert len(sx) == 20


def test_lttb_preserves_endpoints_exact():
    x = np.linspace(0, 100, 200)
    y = np.cos(x)
    sx, sy = charts._lttb(x, y, 30)
    assert sx[0] == x[0]
    assert sy[0] == y[0]
    assert sx[-1] == x[-1]
    assert sy[-1] == y[-1]

def test_line_chart_note_when_downsampled():
    frame = pd.DataFrame({"x": range(1000), "y": range(1000)})
    payload = charts.LineChart()._prepare(
        frame, ColumnMapping(x="x", y=["y"]), 100
    )
    assert payload.note == "↓ 1,000 → 100 points"


def test_line_chart_no_note_when_under_budget():
    frame = pd.DataFrame({"x": range(50), "y": range(50)})
    payload = charts.LineChart()._prepare(
        frame, ColumnMapping(x="x", y=["y"]), 100
    )
    assert payload.note is None


def test_scatter_chart_note_when_downsampled():
    frame = pd.DataFrame({"x": range(1000), "y": range(1000)})
    payload = charts.Scatter()._prepare(
        frame, ColumnMapping(x="x", y=["y"]), 100
    )
    assert payload.note == "↓ 1,000 → 100 points"


def test_histogram_note_when_truncated():
    frame = pd.DataFrame({"value": range(1000)})
    payload = charts.Histogram()._prepare(
        frame, ColumnMapping(value="value"), 100
    )
    assert payload.note == "last 100 of 1,000 values"


def test_heatmap_note_when_truncated():
    frame = pd.DataFrame({"a": range(1000), "b": range(1000), "c": range(1000)})
    payload = charts.Heatmap()._prepare(frame, ColumnMapping(), 100)
    assert payload.note == "last 100 of 1,000 rows"


def test_box_chart_note_when_truncated():
    frame = pd.DataFrame({"value": range(1000)})
    payload = charts.BoxPlot()._prepare(
        frame, ColumnMapping(value="value"), 100
    )
    assert payload.note == "last 100 of 1,000 values"


def test_bar_chart_note_when_truncated():
    frame = pd.DataFrame(
        {"category": [f"c{i}" for i in range(40)], "value": range(40)}
    )
    payload = charts.BarChart()._prepare(
        frame, ColumnMapping(category="category", value="value"), 100
    )
    assert payload.note == "top 30 of 40 categories"


def test_proportion_chart_note_when_truncated():
    frame = pd.DataFrame(
        {"category": [f"c{i}" for i in range(25)], "value": range(25)}
    )
    payload = charts.ProportionChart()._prepare(
        frame, ColumnMapping(category="category", value="value"), 100
    )
    assert payload.note == "top 20 of 25 categories"
