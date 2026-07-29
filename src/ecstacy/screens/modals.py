from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView


class OpenScreen(ModalScreen):
    DEFAULT_CSS = """
    OpenScreen {
        align: center middle;
    }
    #open-box {
        width: 70;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, dashboard: bool = False) -> None:
        super().__init__()
        self.dashboard = dashboard

    def compose(self) -> ComposeResult:
        title = "Open dashboard YAML" if self.dashboard else "Open file path or URL"
        with Vertical(id="open-box"):
            yield Label(title)
            yield Input(placeholder="path or https://...", id="open-input")

    def on_mount(self) -> None:
        self.query_one("#open-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss()
        if not value:
            return
        if self.dashboard:
            self.app.open_dashboard_path(value)
        else:
            self.app.open_path(value)

    def action_cancel(self) -> None:
        self.dismiss()


class ColumnPickerScreen(ModalScreen):
    DEFAULT_CSS = """
    ColumnPickerScreen {
        align: center middle;
    }
    #colpicker-box {
        width: 50;
        height: auto;
        max-height: 24;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #colpicker-list {
        height: auto;
        max-height: 18;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, columns: list[str], hidden: set[str]) -> None:
        super().__init__()
        self.columns = columns
        self.hidden = hidden

    def compose(self) -> ComposeResult:
        with Vertical(id="colpicker-box"):
            yield Label("Toggle columns (enter to toggle, esc to close)")
            yield ListView(id="colpicker-list")

    def on_mount(self) -> None:
        lv = self.query_one("#colpicker-list", ListView)
        for col in self.columns:
            marker = "[dim]○[/dim]" if col in self.hidden else "[green]●[/green]"
            lv.append(ListItem(Label(f"{marker}  {col}"), name=col))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        col = str(event.item.name)
        if col in self.hidden:
            self.hidden.discard(col)
        else:
            self.hidden.add(col)
        self.dismiss(self.hidden)

    def action_cancel(self) -> None:
        self.dismiss(self.hidden)
