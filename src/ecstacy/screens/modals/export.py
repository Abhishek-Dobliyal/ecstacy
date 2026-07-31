from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class ExportScreen(ModalScreen):
    DEFAULT_CSS = """
    ExportScreen {
        align: center middle;
    }
    #export-box {
        width: 60;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="export-box"):
            yield Label("Export current view")
            yield Input(placeholder="output path (e.g. out.csv)", id="export-path")
            yield Input(placeholder="format: csv, json, or markdown", id="export-fmt")

    def on_mount(self) -> None:
        self.query_one("#export-path", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "export-path":
            self.query_one("#export-fmt", Input).focus()
        elif event.input.id == "export-fmt":
            path = self.query_one("#export-path", Input).value.strip()
            fmt = event.value.strip().lower() or "csv"
            if not path:
                return
            self.dismiss((path, fmt))

    def action_cancel(self) -> None:
        self.dismiss(None)
