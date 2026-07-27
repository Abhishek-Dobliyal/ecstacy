from __future__ import annotations

import pytest
from pydantic import ValidationError

from ecstacy.config.loader import load_app_config
from ecstacy.config.schema import ConfigError, DashboardConfig, PanelConfig, SourceSpec


def test_load_app_config_defaults():
    config = load_app_config()
    assert config.theme == "ecstacy-dark"
    assert config.refresh == "0s"
    assert config.splash is True


def test_load_app_config_overrides():
    config = load_app_config({"theme": "ecstacy-light", "splash": False})
    assert config.theme == "ecstacy-light"
    assert config.splash is False


def test_load_app_config_invalid_refresh():
    with pytest.raises(ConfigError):
        load_app_config({"refresh": "not-a-duration"})


def test_load_app_config_invalid_max_rows():
    with pytest.raises(ConfigError):
        load_app_config({"max_rows": -5})


def test_dashboard_config_validates_panel_sources():
    with pytest.raises(ConfigError):
        DashboardConfig(
            sources=[SourceSpec(kind="file", id="metrics", params={"path": "x.csv"})],
            panels=[PanelConfig(source="unknown", viz="line")],
        )


def test_dashboard_config_from_dict():
    data = {
        "theme": "ecstacy-dark",
        "sources": [{"kind": "file", "id": "metrics", "path": "x.csv"}],
        "panels": [
            {"source": "metrics", "viz": "line", "y": "revenue"},
            {"source": "metrics", "viz": "bar", "category": "region", "value": "revenue"},
        ],
    }
    dashboard = DashboardConfig.from_dict(data)
    assert len(dashboard.sources) == 1
    assert len(dashboard.panels) == 2
    assert dashboard.panels[0].y == ["revenue"]


def test_panel_config_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        PanelConfig(source="x", viz="line", unknown_field=123)
