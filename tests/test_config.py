from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ecstacy.config.loader import ensure_user_config, load_app_config
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


def test_ensure_user_config_creates_dir_and_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = ensure_user_config()
    assert path.exists()
    assert path.parent.is_dir()
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    assert "theme" in data
    assert "refresh" in data


def test_ensure_user_config_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ensure_user_config()
    config_path = ensure_user_config()
    data = yaml.safe_load(config_path.read_text())
    assert "theme" in data


def test_ensure_user_config_does_not_overwrite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config_dir = tmp_path / "ecstacy"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("theme: ecstacy-light\nrefresh: 10s\n")
    ensure_user_config()
    data = yaml.safe_load(config_file.read_text())
    assert data["theme"] == "ecstacy-light"
    assert data["refresh"] == "10s"
