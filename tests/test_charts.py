from __future__ import annotations

import pandas as pd
import pytest

from ecstacy.widgets import charts


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


def test_max_chart_points_constant():
    assert charts.MAX_CHART_POINTS == 1000


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

