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
