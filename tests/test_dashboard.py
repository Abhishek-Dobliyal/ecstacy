from __future__ import annotations

import pytest

from ecstacy.config.loader import load_dashboard
from ecstacy.config.schema import ConfigError, DashboardConfig, PanelConfig, SourceSpec


def test_load_dashboard_resolves_relative_paths(tmp_path):
    sub = tmp_path / "data"
    sub.mkdir()
    csv = sub / "sample.csv"
    csv.write_text("a,b\n1,2\n")
    dashboard_file = tmp_path / "ops.yaml"
    dashboard_file.write_text(
        "sources:\n"
        "  - kind: file\n"
        "    id: metrics\n"
        "    path: ./data/sample.csv\n"
        "panels:\n"
        "  - source: metrics\n"
        "    viz: table\n"
    )
    dashboard = load_dashboard(str(dashboard_file))
    assert dashboard.sources[0].params["path"] == str(csv.resolve())


def test_load_dashboard_keeps_absolute_paths(tmp_path):
    csv = tmp_path / "sample.csv"
    csv.write_text("a,b\n1,2\n")
    dashboard_file = tmp_path / "ops.yaml"
    dashboard_file.write_text(
        f"sources:\n"
        f"  - kind: file\n"
        f"    id: metrics\n"
        f"    path: {csv}\n"
        f"panels:\n"
        f"  - source: metrics\n"
        f"    viz: table\n"
    )
    dashboard = load_dashboard(str(dashboard_file))
    assert dashboard.sources[0].params["path"] == str(csv)


def test_load_dashboard_validates_sources(tmp_path):
    bad_dashboard = tmp_path / "bad.yaml"
    bad_dashboard.write_text(
        "sources:\n"
        "  - kind: file\n"
        "    id: metrics\n"
        "    path: x.csv\n"
        "panels:\n"
        "  - source: unknown\n"
        "    viz: line\n"
    )
    with pytest.raises(ConfigError):
        load_dashboard(str(bad_dashboard))


def test_grid_size_calculations():
    from ecstacy.screens.dashboard import _grid_size

    assert _grid_size(1) == (1, 1)
    assert _grid_size(2) == (1, 2)
    assert _grid_size(3) == (2, 2)
    assert _grid_size(4) == (2, 2)
    assert _grid_size(5) == (2, 3)
    assert _grid_size(9) == (3, 3)
    assert _grid_size(10)[0] * _grid_size(10)[1] >= 10


def test_mapping_from_panel():
    from ecstacy.screens.dashboard import _mapping_from_panel

    panel = PanelConfig(
        source="metrics", viz="line", x="timestamp", y=["revenue", "margin"]
    )
    mapping = _mapping_from_panel(panel)
    assert mapping.x == "timestamp"
    assert mapping.y == ["revenue", "margin"]


def test_dashboard_config_from_relative_path():
    data = {
        "sources": [{"kind": "file", "id": "metrics", "path": "./dashboards/sample.csv"}],
        "panels": [{"source": "metrics", "viz": "line"}],
    }
    dashboard = DashboardConfig.from_dict(data)
    assert dashboard.sources[0].kind == "file"
    assert dashboard.panels[0].source == "metrics"


def test_source_spec_unknown_kind():
    from ecstacy.sources.base import SourceError, create_source

    spec = SourceSpec(kind="not-real", id="x", params={})
    with pytest.raises(SourceError):
        create_source(spec)


def test_panel_config_accepts_transform_fields():
    panel = PanelConfig(
        source="metrics",
        viz="bar",
        category="region",
        value="revenue",
        where="revenue > 100",
        group_by=["region"],
        agg="mean",
        select=["region", "revenue"],
        limit=10,
    )
    assert panel.where == "revenue > 100"
    assert panel.group_by == ["region"]
    assert panel.agg == "mean"
    assert panel.select == ["region", "revenue"]
    assert panel.limit == 10


def test_panel_config_from_dict_parses_transform_fields():
    data = {
        "source": "metrics",
        "viz": "bar",
        "category": "region",
        "value": "revenue",
        "where": "revenue > 100",
        "group_by": "region",
        "agg": "mean",
        "select": "region, revenue",
        "limit": 10,
    }
    panel = PanelConfig.from_dict(data)
    assert panel.group_by == ["region"]
    assert panel.select == ["region, revenue"]


def test_dashboard_applies_transform_in_prepare_panel(tmp_path):
    import pandas as pd

    from ecstacy.config.schema import DashboardConfig
    from ecstacy.screens.dashboard import DashboardScreen

    csv = tmp_path / "data.csv"
    csv.write_text("region,value\nus,10\nus,20\neu,15\neu,5\n")
    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="metrics", params={"path": str(csv)})],
        panels=[
            PanelConfig(
                source="metrics",
                viz="table",
                group_by=["region"],
                agg="sum",
                where="value > 5",
            ),
        ],
    )
    screen = DashboardScreen(dashboard)
    frame = pd.read_csv(csv)
    screen._datasets["metrics"] = __import__(
        "ecstacy.core.dataset", fromlist=["DataSet"]
    ).DataSet.from_dataframe(frame, source_id="metrics", kind="file")
    result = screen._apply_transform(screen.dashboard.panels[0], frame)
    assert set(result["region"]) == {"us", "eu"}
    assert result[result["region"] == "us"]["value"].iloc[0] == 30
    assert result[result["region"] == "eu"]["value"].iloc[0] == 15


def test_source_spec_from_dict_missing_kind():
    from ecstacy.sources.base import SourceSpecError

    with pytest.raises(SourceSpecError):
        SourceSpec.from_dict({"id": "x"})


def test_dashboard_duplicate_source_ids_rejected():
    sources = [
        SourceSpec(kind="file", id="a", params={"path": "x.csv"}),
        SourceSpec(kind="file", id="a", params={"path": "y.csv"}),
    ]
    with pytest.raises(ConfigError, match="duplicate"):
        DashboardConfig(sources=sources)


def test_dashboard_invalid_refresh_rejected():
    with pytest.raises(Exception, match="invalid refresh"):
        DashboardConfig(refresh="5x")


def test_panel_config_rejects_layout_field():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PanelConfig(source="s", viz="line", layout={"row": 0})


def test_load_dashboard_missing_file():
    with pytest.raises(ConfigError, match="no such file"):
        load_dashboard("/does/not/exist.yaml")


# -----------------------------------------------------------------------
# Single-panel pooling: n/p cycles reuse widgets instead of rebuilding
# -----------------------------------------------------------------------


async def _settle(pilot, rounds: int = 8) -> None:
    for _ in range(rounds):
        await pilot.pause()


def _single_dashboard(*panel_sources: str):
    """Dashboard with one table panel per entry in *panel_sources*; multiple
    panels may share the same source id."""
    unique_sources = dict.fromkeys(panel_sources)
    return DashboardConfig(
        sources=[
            SourceSpec(kind="file", id=src, params={"path": f"{src}.csv"})
            for src in unique_sources
        ],
        panels=[PanelConfig(viz="table", source=src) for src in panel_sources],
    )


def _frame_dataset(rows, source_id="s"):
    import pandas as pd

    from ecstacy.core.dataset import DataSet

    return DataSet.from_dataframe(
        pd.DataFrame({"a": list(range(rows))}), source_id=source_id, kind="test"
    )


@pytest.mark.asyncio
async def test_single_panel_cycle_reuses_pooled_widgets():
    from textual.app import App

    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = _single_dashboard("s", "s")

    class _App(App):
        def on_mount(self):
            screen = DashboardScreen(dashboard)
            screen._multi_panel = False
            self.push_screen(screen)

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        screen._on_data("s")(_frame_dataset(2))
        await _settle(pilot)
        assert screen._panels_built
        first = screen._panel_widgets[0]
        # Two panels were configured; visit the second one.
        await screen.action_next_panel()
        await _settle(pilot)
        second = screen._panel_widgets[1]
        assert second is not first
        assert screen._single_pool[0].display is False
        assert screen._single_pool[1].display is True
        # Cycling back reuses the pooled widget — no teardown/rebuild.
        await screen.action_prev_panel()
        await _settle(pilot)
        assert screen._panel_widgets[0] is first
        assert screen._single_pool[0].display is True
        assert screen._single_pool[1].display is False


@pytest.mark.asyncio
async def test_single_panel_hidden_refresh_applied_on_show():
    """Data arriving for a hidden pooled panel is applied lazily on show."""
    from textual.app import App

    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = _single_dashboard("s", "s")

    class _App(App):
        def on_mount(self):
            screen = DashboardScreen(dashboard)
            screen._multi_panel = False
            self.push_screen(screen)

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        screen._on_data("s")(_frame_dataset(2))
        await _settle(pilot)
        # Visit panel 1 so both are pooled, then go back to panel 0.
        await screen.action_next_panel()
        await _settle(pilot)
        await screen.action_prev_panel()
        await _settle(pilot)
        w0 = screen._panel_widgets[0]
        w1 = screen._panel_widgets[1]
        # New data arrives while panel 1 is hidden.
        screen._on_data("s")(_frame_dataset(5))
        await app.workers.wait_for_complete()
        await _settle(pilot)
        # Visible panel updated in place; hidden panel skipped.
        assert len(w0._frame) == 5
        assert len(w1._frame) == 2
        # Showing panel 1 applies the cached data.
        await screen.action_next_panel()
        await _settle(pilot)
        assert screen._panel_widgets[1] is w1
        assert len(w1._frame) == 5


@pytest.mark.asyncio
async def test_panels_paint_on_initial_render():
    """set_data runs before mount in _prepare_panel_widget; on_mount must
    still kick off prepare+paint or panels render empty until a data change."""
    from textual.app import App

    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = DashboardConfig(
        sources=[SourceSpec(kind="file", id="s", params={"path": "x.csv"})],
        panels=[PanelConfig(viz="line", source="s")],
    )

    class _App(App):
        def on_mount(self):
            self.push_screen(DashboardScreen(dashboard))

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        screen._on_data("s")(_frame_dataset(3))
        await app.workers.wait_for_complete()
        await _settle(pilot)
        widget = screen._panel_widgets[0]
        assert widget._render_data is not None
        assert widget._build_cache is not None


@pytest.mark.asyncio
async def test_single_panel_placeholder_replaced_once_data_arrives():
    """A 'source not loaded' placeholder is replaced with a real widget
    when its source data exists by the time the panel is shown."""
    from textual.app import App

    from ecstacy.screens.dashboard import DashboardScreen

    dashboard = _single_dashboard("s", "t")

    class _App(App):
        def on_mount(self):
            screen = DashboardScreen(dashboard)
            screen._multi_panel = False
            self.push_screen(screen)

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        # Only source "s" has data; panel 1 (source "t") is a placeholder.
        screen._on_data("s")(_frame_dataset(2))
        await _settle(pilot)
        await screen.action_next_panel()  # show placeholder for "t"
        await _settle(pilot)
        assert 1 not in screen._panel_widgets
        assert 1 in screen._single_pool
        # Data for "t" arrives; nothing to rebuild (no widget yet).
        screen._on_data("t")(_frame_dataset(3, source_id="t"))
        await app.workers.wait_for_complete()
        await _settle(pilot)
        # Cycle away and back: the placeholder is replaced with a widget.
        await screen.action_prev_panel()
        await _settle(pilot)
        await screen.action_next_panel()
        await _settle(pilot)
        assert 1 in screen._panel_widgets
        assert len(screen._panel_widgets[1]._frame) == 3


@pytest.mark.asyncio
async def test_multi_panel_six_panels_all_receive_data():
    from textual.app import App

    from ecstacy.screens.dashboard import DashboardScreen

    panel_sources = ["a", "b", "c", "d", "e", "f"]
    dashboard = DashboardConfig(
        sources=[
            SourceSpec(kind="file", id=src, params={"path": f"{src}.csv"})
            for src in panel_sources
        ],
        panels=[PanelConfig(viz="table", source=src) for src in panel_sources],
    )

    class _App(App):
        def on_mount(self):
            self.push_screen(DashboardScreen(dashboard))

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        for src in panel_sources:
            screen._on_data(src)(_frame_dataset(3, source_id=src))
        await app.workers.wait_for_complete()
        await _settle(pilot)
        assert screen._panels_built
        assert len(screen._panel_widgets) == 6
        for i in range(6):
            widget = screen._panel_widgets[i]
            assert len(widget._frame) == 3
