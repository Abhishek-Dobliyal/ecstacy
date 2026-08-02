from __future__ import annotations

from textual.theme import Theme

ECSTACY_DARK = Theme(
    name="ecstacy-dark",
    primary="#7cdf32",
    secondary="#00d7d7",
    accent="#ffcc00",
    foreground="#c8d3a5",
    background="#0a0e14",
    surface="#0f141a",
    panel="#1c2128",
    success="#7cdf32",
    warning="#ffab00",
    error="#ff5f5f",
    dark=True,
)

ECSTACY_LIGHT = Theme(
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

THEMES = [ECSTACY_DARK, ECSTACY_LIGHT]
_THEME_NAMES = tuple(t.name for t in THEMES)


def register_themes(app) -> None:
    for theme in THEMES:
        app.register_theme(theme)


def theme_names() -> list[str]:
    return list(_THEME_NAMES)
