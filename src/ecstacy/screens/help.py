from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP = (
    "[bold yellow]Panels[/bold yellow]\n"
    "  1 quick-start   the main actions -- open, dashboard, theme, help, quit\n"
    "  2 sources       source plugins Ecstacy can read from\n"
    "  3 recents       datasets you have opened this session, enter to reopen\n"
    "  4 charts        visualizations available inside the chart view\n"
    "  5 keys          keyboard shortcut cheatsheet\n\n"
    "[bold yellow]Navigation[/bold yellow]\n"
    "  tab / shift+tab   move between panels\n"
    "  arrow keys        move within a panel\n"
    "  enter or click    activate the highlighted item\n\n"
    "[bold yellow]Home keys[/bold yellow]\n"
    "  o    open a file path or URL\n"
    "  d    open a dashboard YAML\n"
    "  t    pick theme\n"
    "  r    refresh recents\n"
    "  ?    help (this screen)\n"
    "  q    quit\n\n"
    "[bold yellow]Chart keys[/bold yellow]\n"
    "  n / right    next visualization\n"
    "  p / left     previous visualization\n"
    "  ctrl+f       query / transform bar\n"
    "  /            focus search (table view)\n"
    "  r            refresh (with --refresh)\n"
    "  t            pick theme\n"
    "  esc          back to home\n\n"
    "[bold yellow]Table keys (in table view)[/bold yellow]\n"
    "  s            sort by a column\n"
    "  c            column picker\n"
    "  e            export view to file\n\n"
    "[bold yellow]Dashboard keys[/bold yellow]\n"
    "  m            toggle grid / single panel layout\n"
    "  n / right    next panel (single layout)\n"
    "  p / left     previous panel (single layout)\n"
    "  r            refresh now\n"
    "  t            pick theme\n"
    "  esc          back to home\n\n"
    "[dim]press esc to close this help[/dim]"
)


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 70;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(_HELP, markup=True)
