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

ONEDARK = Theme(
    name="onedark",
    primary="#61afef",
    secondary="#56b6c2",
    accent="#c678dd",
    foreground="#abb2bf",
    background="#282c34",
    surface="#21252b",
    panel="#1e2127",
    success="#98c379",
    warning="#e5c07b",
    error="#e06c75",
    dark=True,
)

DARCULA = Theme(
    name="darcula",
    primary="#cc7832",
    secondary="#9876aa",
    accent="#ffc66d",
    foreground="#a9b7c6",
    background="#2b2b2b",
    surface="#313335",
    panel="#3c3f41",
    success="#6a8759",
    warning="#ffc66d",
    error="#bc3f3c",
    dark=True,
)

SYNTHWAVE = Theme(
    name="synthwave",
    primary="#f97e72",
    secondary="#ff7edb",
    accent="#00f1ff",
    foreground="#f4eee4",
    background="#2a2139",
    surface="#34294f",
    panel="#241b2f",
    success="#72f1b8",
    warning="#ffcc00",
    error="#ff5e8f",
    dark=True,
)

THEMES = [ECSTACY_DARK, ECSTACY_LIGHT, ONEDARK, DARCULA, SYNTHWAVE]
_THEME_NAMES = tuple(t.name for t in THEMES)


def register_themes(app) -> None:
    for theme in THEMES:
        app.register_theme(theme)


def theme_names() -> list[str]:
    return list(_THEME_NAMES)


def theme_entries() -> list[tuple[str, str]]:
    """Return ``[(name, primary_hex), ...]`` for picker swatches."""
    return [(t.name, t.primary) for t in THEMES]
