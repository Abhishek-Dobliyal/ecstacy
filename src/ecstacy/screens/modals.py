from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


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
