from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select

from ecstacy.widgets.base import ColumnMapping

# Per-viz field descriptor: (field_name, label, is_multi).
VIZ_FIELDS: dict[str, list[tuple[str, str, bool]]] = {
    "line": [("x", "X axis", False), ("y", "Y series (comma-sep)", True)],
    "bar": [("category", "Category", False), ("value", "Value", False)],
    "histogram": [("value", "Column", False)],
    "scatter": [("x", "X axis", False), ("y", "Y axis", False)],
    "box": [("value", "Value", False), ("category", "Category (optional)", False)],
    "proportion": [("category", "Category", False), ("value", "Value", False)],
    "sparkline": [("value", "Column", False)],
    "gauge": [("value", "Column", False)],
}

VIZ_NO_MAPPING = {"heatmap", "table", "summary", "json"}


class ChartMappingScreen(ModalScreen):
    DEFAULT_CSS = """
    ChartMappingScreen {
        align: center middle;
    }
    #mapping-box {
        width: 60;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #mapping-box Select {
        width: 100%;
        margin: 0 0 1 0;
    }
    #mapping-box Label {
        margin: 0 0 0 0;
    }
    #mapping-buttons {
        height: auto;
        align-horizontal: right;
        margin: 1 0 0 0;
    }
    #mapping-buttons Button {
        margin: 0 0 0 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        viz_name: str,
        columns: list[str],
        mapping: ColumnMapping,
    ) -> None:
        super().__init__()
        self.viz_name = viz_name
        self.columns = columns
        self.mapping = mapping
        self._fields = VIZ_FIELDS.get(viz_name, [])

    def compose(self) -> ComposeResult:
        with Vertical(id="mapping-box"):
            yield Label(f"Map columns · {self.viz_name}")
            for field, label, _is_multi in self._fields:
                yield Label(label)
                current = getattr(self.mapping, field)
                if isinstance(current, list):
                    current = current[0] if current else None
                options = [("(auto)", None)] + [(c, c) for c in self.columns]
                select = Select(
                    options=options,
                    value=current if current in self.columns else None,
                    id=f"map-{field}",
                )
                yield select
            yield Label("tab to OK, press enter to confirm · esc to cancel")
            with Horizontal(id="mapping-buttons"):
                yield Button("OK", id="mapping-ok")
                yield Button("Cancel", id="mapping-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mapping-ok":
            self.action_confirm()
        elif event.button.id == "mapping-cancel":
            self.action_cancel()

    def action_confirm(self) -> None:
        result = ColumnMapping(
            x=self.mapping.x,
            y=list(self.mapping.y),
            category=self.mapping.category,
            value=self.mapping.value,
            bins=self.mapping.bins,
        )
        for field, _label, is_multi in self._fields:
            select = self.query_one(f"#map-{field}", Select)
            value = select.value
            if value is None or value == "(auto)":
                if is_multi:
                    setattr(result, field, [])
                else:
                    setattr(result, field, None)
            elif is_multi:
                setattr(result, field, [str(value)])
            else:
                setattr(result, field, str(value))
        self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)
