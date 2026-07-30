from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Select

from ecstacy.widgets.base import ColumnMapping


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
            self.app.open_dashboard_path(value)  # type: ignore[attr-defined]
        else:
            self.app.open_path(value)  # type: ignore[attr-defined]

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
        # toggle in place; the updated set is returned on esc
        marker = "[dim]○[/dim]" if col in self.hidden else "[green]●[/green]"
        event.item.query_one(Label).update(f"{marker}  {col}")

    def action_cancel(self) -> None:
        self.dismiss(self.hidden)


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


# Fields shown per viz in the chart mapping picker.  Maps viz name to a
# list of (field_name, label, is_multi) tuples.  Fields not listed here
# are preserved from the existing mapping.
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
    """Modal for picking which columns a chart plots.

    Shows only the fields relevant to the current viz type.  Column
    fields are ``Select`` dropdowns with an "(auto)" option that sets
    the field to ``None``.  On confirm, a new ``ColumnMapping`` is
    built from the existing one with picked fields overwritten.
    """

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
    """

    BINDINGS = [("escape", "cancel", "Cancel"), ("enter", "confirm", "OK")]

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
                # Select requires at least one option; default to first
                select = Select(
                    options=options,
                    value=current if current in self.columns else None,
                    id=f"map-{field}",
                )
                yield select

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
