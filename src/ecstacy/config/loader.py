from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ecstacy.config import defaults
from ecstacy.config.schema import AppConfig, ConfigError, DashboardConfig

_ENV_PREFIX = "ECSTACY_"


def user_config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / defaults.CONFIG_DIRNAME / defaults.CONFIG_FILENAME


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return data if isinstance(data, dict) else {}


def _env_overrides() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in os.environ.items():
        if key.startswith(_ENV_PREFIX):
            result[key[len(_ENV_PREFIX):].lower()] = value
    return result


def _clean_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (overrides or {}).items() if v is not None}


def load_app_config(overrides: dict[str, Any] | None = None) -> AppConfig:
    merged: dict[str, Any] = dict(defaults.DEFAULTS)
    merged.update(_read_yaml(user_config_path()))
    merged.update(_read_yaml(Path.cwd() / defaults.PROJECT_CONFIG))
    merged.update(_env_overrides())
    merged.update(_clean_overrides(overrides))
    try:
        return AppConfig(**merged)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"invalid app config: {errors}") from exc


def load_dashboard(path: str | Path) -> DashboardConfig:
    dashboard_path = Path(path).expanduser().resolve()
    base_dir = dashboard_path.parent
    data = _read_yaml(dashboard_path)
    data = _resolve_source_paths(data, base_dir)
    try:
        return DashboardConfig.from_dict(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"invalid dashboard config: {errors}") from exc


def _resolve_source_paths(data: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Resolve relative `path` params in file sources against the dashboard dir."""
    sources = data.get("sources")
    if not isinstance(sources, list):
        return data
    for spec in sources:
        if not isinstance(spec, dict) or spec.get("kind") != "file":
            continue
        raw_path = spec.get("path")
        if raw_path is None:
            continue
        p = Path(str(raw_path))
        if not p.is_absolute():
            spec["path"] = str((base_dir / p).resolve())
    return data
