from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ecstacy import APP_NAME
from ecstacy.core import registry
from ecstacy.screens.help import HelpScreen
from ecstacy.screens.modals import OpenScreen
from ecstacy.widgets import viz_names

_QUICK_ITEMS = [
    ("q-open", "o", "open a file or URL"),
    ("q-dashboard", "d", "open a dashboard YAML"),
    ("q-theme", "t", "toggle theme"),
    ("q-help", "?", "help"),
    ("q-quit", "q", "quit"),
]

_SOURCE_INFO = {
    "file": "csv, tsv, json, ndjson, parquet or log files",
    "rest": "poll a REST endpoint returning json",
    "sql": "run a DuckDB query (can read files directly)",
    "sqlite": "run a SQLite query (in-memory or file-backed)",
    "socket": "stream JSON records from a WebSocket endpoint",
}

_CHART_INFO = {
    "table": "the raw rows, sortable, searchable",
    "line": "time series values across time or index",
    "bar": "grouped totals by category",
    "histogram": "distribution of a single numeric column",
    "scatter": "relationship between two numeric columns",
    "sparkline": "compact one-line trend of a value column",
    "gauge": "latest value with delta and min/max",
    "heatmap": "correlation between numeric columns",
    "box": "distribution quartiles per category",
    "proportion": "share of total per category (horizontal bars)",
    "summary": "count/mean/median/std/min/max per column",
    "json": "raw json payload as a tree",
}


class HomeScreen(Screen):
    BINDINGS = [
        ("o", "open", "Open"),
        ("d", "dashboard", "Dashboard"),
        ("t", "app.toggle_theme", "Theme"),
        ("question_mark", "help", "Help"),
        ("r", "refresh", "Refresh"),
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid(id="home-grid"):
            yield ListView(
                *[
                    ListItem(
                        Label(f"[bold yellow] {key} [/bold yellow]  {label}"),
                        id=item_id,
                    )
                    for item_id, key, label in _QUICK_ITEMS
                ],
                id="quick",
            )
            yield ListView(
                *[
                    ListItem(
                        Label(
                            f"[bright_green]+[/bright_green]  [bold]{name}[/bold]  "
                            f"[dim]{_SOURCE_INFO.get(name, '')}[/dim]"
                        ),
                        id=f"src-{name}",
                    )
                    for name in registry.sources.names()
                ],
                id="sources",
            )
            yield ListView(id="recents")
            yield ListView(
                *[
                    ListItem(
                        Label(
                            f"[bright_green]+[/bright_green]  [bold]{name}[/bold]  "
                            f"[dim]{_CHART_INFO.get(name, '')}[/dim]"
                        ),
                        id=f"viz-{name}",
                    )
                    for name in viz_names()
                ],
                id="charts",
            )
            yield Static("", id="keys", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.app.title = APP_NAME
        self.app.sub_title = "home"
        self._title("quick", "1 quick-start", "enter or click")
        self._title("sources", "2 sources", "supported input kinds")
        self._title("recents", "3 recents", "enter to reopen")
        self._title("charts", "4 charts", "available visualizations")
        self._title("keys", "5 keys", "tab / arrows / enter")
        self.query_one("#keys", Static).update(self._keys_text())
        self._refresh_recents()
        self.query_one("#quick", ListView).focus()

    def on_screen_resume(self) -> None:
        self.app.sub_title = "home"
        self._refresh_recents()

    def _title(self, wid: str, title: str, subtitle: str) -> None:
        widget = self.query_one(f"#{wid}")
        widget.border_title = title
        if subtitle:
            widget.border_subtitle = subtitle

    def _refresh_recents(self) -> None:
        list_view = self.query_one("#recents", ListView)
        list_view.clear()
        recents = getattr(self.app, "recents", [])
        count = len(recents)
        self._title(
            "recents",
            "3 recents",
            f"enter to reopen · {count} this session" if count else "enter to reopen",
        )
        if not recents:
            list_view.append(
                ListItem(Label("[dim]no sources yet -- press o to open one[/dim]"))
            )
            return
        for idx, (label, spec) in enumerate(recents[:8], start=1):
            item = ListItem(Label(f"[bold yellow]{idx}[/bold yellow]   {label}"))
            item._spec = spec  # type: ignore[attr-defined]
            list_view.append(item)

    def _keys_text(self) -> str:
        lines = [
            "[bold yellow]NAV[/bold yellow]    tab / shift+tab move panel   "
            "arrows within   enter select   click also works",
            "[bold yellow]HOME[/bold yellow]   o open   d dashboard   t theme   "
            "r refresh   ? help   q quit",
            "[bold yellow]CHART[/bold yellow]  n / right next viz   p / left prev viz   "
            "ctrl+f query   r refresh   esc back",
        ]
        return "\n".join(lines)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        wid = item.id or ""
        actions = {
            "q-open": self.action_open,
            "q-dashboard": self.action_dashboard,
            "q-theme": self.app.action_toggle_theme,  # type: ignore[attr-defined]
            "q-help": self.action_help,
            "q-quit": self.app.exit,
        }
        if wid in actions:
            actions[wid]()
            return
        if wid.startswith("src-"):
            kind = wid[len("src-"):]
            desc = _SOURCE_INFO.get(kind, kind)
            self.notify(f"{kind}: {desc}. press o to open one.")
            return
        if wid.startswith("viz-"):
            name = wid[len("viz-"):]
            desc = _CHART_INFO.get(name, name)
            self.notify(f"{name}: {desc}. open a source, then press n / p to cycle.")
            return
        spec = getattr(item, "_spec", None)
        if spec is not None:
            self.app.open_source(spec)  # type: ignore[attr-defined]

    def action_refresh(self) -> None:
        self._refresh_recents()
        self.notify("recents refreshed")

    def action_open(self) -> None:
        self.app.push_screen(OpenScreen())

    def action_dashboard(self) -> None:
        self.app.push_screen(OpenScreen(dashboard=True))

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())
