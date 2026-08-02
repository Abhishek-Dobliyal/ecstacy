from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


class ThemePickerScreen(ModalScreen):
    DEFAULT_CSS = """
    ThemePickerScreen {
        align: center middle;
    }
    #themepicker-box {
        width: 40;
        height: auto;
        max-height: 20;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #themepicker-list {
        height: auto;
        max-height: 14;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self, entries: list[tuple[str, str]], current: str
    ) -> None:
        super().__init__()
        self.entries = entries
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="themepicker-box"):
            yield Label("Themes  (enter to select · esc to cancel)")
            yield ListView(id="themepicker-list")

    def on_mount(self) -> None:
        lv = self.query_one("#themepicker-list", ListView)
        for index, (name, primary) in enumerate(self.entries):
            marker = "[green]▸[/green]" if name == self.current else " "
            swatch = f"[{primary}]●[/{primary}]"
            lv.append(ListItem(Label(f"{marker}  {swatch}  {name}"), name=name))
            if name == self.current:
                lv.index = index

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(str(event.item.name))

    def action_cancel(self) -> None:
        self.dismiss(None)
