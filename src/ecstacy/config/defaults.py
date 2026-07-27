from __future__ import annotations

DEFAULT_THEME = "ecstacy-dark"
DEFAULT_REFRESH = "0s"
DEFAULT_MAX_ROWS = 1000
CONFIG_DIRNAME = "ecstacy"
CONFIG_FILENAME = "config.yaml"
PROJECT_CONFIG = "ecstacy.yaml"

DEFAULTS: dict[str, object] = {
    "theme": DEFAULT_THEME,
    "refresh": DEFAULT_REFRESH,
    "splash": True,
    "max_rows": DEFAULT_MAX_ROWS,
}
