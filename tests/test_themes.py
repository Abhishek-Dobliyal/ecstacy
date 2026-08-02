from __future__ import annotations

import pytest

from ecstacy.theming import theme_entries, theme_names
from ecstacy.theming.themes import THEMES

_REQUIRED_FIELDS = (
    "name",
    "primary",
    "secondary",
    "accent",
    "foreground",
    "background",
    "surface",
    "panel",
    "success",
    "warning",
    "error",
    "dark",
)


def test_all_themes_have_required_fields():
    for theme in THEMES:
        for field in _REQUIRED_FIELDS:
            assert getattr(theme, field) is not None, f"{theme.name} missing {field}"


def test_theme_names_returns_five():
    names = theme_names()
    assert len(names) == 5
    assert "ecstacy-dark" in names
    assert "ecstacy-light" in names
    assert "onedark" in names
    assert "darcula" in names
    assert "synthwave" in names


def test_theme_names_are_unique():
    names = theme_names()
    assert len(names) == len(set(names))


def test_theme_entries_match_names():
    entries = theme_entries()
    assert len(entries) == len(THEMES)
    for (name, primary), theme in zip(entries, THEMES, strict=True):
        assert name == theme.name
        assert primary == theme.primary


def test_new_themes_are_dark():
    from ecstacy.theming.themes import DARCULA, ONEDARK, SYNTHWAVE

    assert ONEDARK.dark is True
    assert DARCULA.dark is True
    assert SYNTHWAVE.dark is True


def test_ecstacy_light_is_not_dark():
    from ecstacy.theming.themes import ECSTACY_LIGHT

    assert ECSTACY_LIGHT.dark is False


@pytest.mark.asyncio
async def test_theme_picker_dismisses_with_selected_name():
    from textual.app import App
    from textual.widgets import ListView

    from ecstacy.screens.modals.theme_picker import ThemePickerScreen

    entries = theme_entries()

    class _App(App):
        def on_mount(self):
            self.push_screen(ThemePickerScreen(entries, "ecstacy-dark"))

    app = _App()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, ThemePickerScreen)
        lv = screen.query_one("#themepicker-list", ListView)
        assert lv.index == 0
        lv.index = 2
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen is not screen


@pytest.mark.asyncio
async def test_theme_picker_cancel_returns_none():
    from textual.app import App

    from ecstacy.screens.modals.theme_picker import ThemePickerScreen

    entries = theme_entries()
    result_holder: list = []

    class _App(App):
        def on_mount(self):
            def _callback(result):
                result_holder.append(result)

            self.push_screen(ThemePickerScreen(entries, "ecstacy-dark"), _callback)

    app = _App()
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert result_holder == [None]


@pytest.mark.asyncio
async def test_action_pick_theme_pushes_picker():

    from ecstacy.app import EcstacyApp
    from ecstacy.config.schema import AppConfig
    from ecstacy.screens.modals.theme_picker import ThemePickerScreen

    app = EcstacyApp(AppConfig())
    async with app.run_test() as pilot:
        app.action_pick_theme()
        await pilot.pause()
        assert isinstance(app.screen, ThemePickerScreen)
