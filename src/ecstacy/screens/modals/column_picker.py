from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


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
        if self.columns:
            lv.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        col = str(event.item.name)
        if col in self.hidden:
            self.hidden.discard(col)
        else:
            self.hidden.add(col)
        marker = "[dim]○[/dim]" if col in self.hidden else "[green]●[/green]"
        event.item.query_one(Label).update(f"{marker}  {col}")

    def action_cancel(self) -> None:
        self.dismiss(self.hidden)
