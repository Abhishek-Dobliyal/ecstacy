from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Label

from ecstacy.config import defaults
from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping


@registry.viz.register("table")
class TableView(Vertical):
    viz_name = "table"
    BINDINGS = [
        ("slash", "focus_search", "Search"),
        ("s", "sort_prompt", "Sort"),
        ("c", "column_picker", "Columns"),
        ("e", "export_view", "Export"),
    ]
    DEFAULT_CSS = """
    TableView {
        height: 1fr;
    }
    TableView #table-search {
        height: 1;
        margin: 0 0 0 0;
        border: round $accent;
        padding: 0 1;
    }
    TableView #table-data {
        height: 1fr;
    }
    TableView #table-footer {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame: pd.DataFrame = pd.DataFrame()
        self._sort_cols: list[tuple[str, bool]] = []
        self._pending_dataset: DataSet | None = None
        self._search_timer = None
        self._search_value = ""
        self._hidden_columns: set[str] = set()
        self._string_frame: pd.DataFrame | None = None

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ to search  ·  type to filter rows", id="table-search")
        yield DataTable(id="table-data")
        yield Label("", id="table-footer")

    def on_mount(self) -> None:
        table = self.query_one("#table-data", DataTable)
        table.cursor_type = "column"
        table.zebra_stripes = True
        if self._pending_dataset is not None:
            self._frame = self._pending_dataset.frame
            self._pending_dataset = None
            self._populate()

    def action_focus_search(self) -> None:
        self.query_one("#table-search", Input).focus()

    def action_sort_prompt(self) -> None:
        table = self.query_one("#table-data", DataTable)
        table.focus()
        self.notify("use arrow keys to select a column, press enter to sort")

    def action_column_picker(self) -> None:
        from ecstacy.screens.modals import ColumnPickerScreen

        columns = [str(c) for c in self._frame.columns]
        self.app.push_screen(
            ColumnPickerScreen(columns, set(self._hidden_columns)),
            self._on_columns_picked,
        )

    def action_export_view(self) -> None:
        from ecstacy.screens.modals import ExportScreen

        self.app.push_screen(ExportScreen(), self._on_export_picked)

    def _on_export_picked(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        path, fmt = result
        self._export_to_file(path, fmt)

    def _export_to_file(self, path: str, fmt: str) -> None:

        frame = self._get_current_view()
        try:
            if fmt == "csv":
                frame.to_csv(path, index=False)
            elif fmt == "json":
                frame.to_json(path, orient="records", indent=2, date_format="iso")
            elif fmt == "markdown":
                frame.to_markdown(path, index=False)
            else:
                self.notify(f"unknown format: {fmt}", severity="error")
                return
        except Exception as exc:
            self.notify(f"export failed: {exc}", severity="error")
            return
        self.notify(f"exported {len(frame)} rows to {path}")

    def _get_current_view(self) -> pd.DataFrame:
        frame = self._frame
        all_columns = [str(c) for c in frame.columns]
        visible_columns = [c for c in all_columns if c not in self._hidden_columns]
        work = sort_frame_multi(frame, self._sort_cols)
        work = filter_frame(work, self._search_value)
        return work[visible_columns]

    def _on_columns_picked(self, hidden: set[str]) -> None:
        self._hidden_columns = hidden
        self._populate(self._search_value)

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        self._sort_cols = []
        self._hidden_columns = set()
        self._string_frame = None
        if self.is_mounted:
            self._frame = dataset.frame
            self._populate()
        else:
            self._pending_dataset = dataset

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "table-search":
            return
        self._search_value = event.value
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(0.15, self._populate_after_debounce)

    def _populate_after_debounce(self) -> None:
        self._populate(self._search_value)

    def on_data_table_column_selected(self, event: DataTable.ColumnSelected) -> None:
        if event.data_table.id != "table-data":
            return
        col = str(event.column_key.value) if event.column_key else None
        if col is None:
            return
        existing = [(c, a) for c, a in self._sort_cols if c == col]
        if existing:
            idx = self._sort_cols.index(existing[0])
            self._sort_cols[idx] = (col, not self._sort_cols[idx][1])
        else:
            self._sort_cols.append((col, True))
        self._populate()

    def _string_frame_cached(self) -> pd.DataFrame:
        if self._string_frame is None:
            self._string_frame = self._frame.astype(str).apply(lambda col: col.str.lower())
        return self._string_frame

    def _filter_cached(self, frame: pd.DataFrame, search: str) -> pd.DataFrame:
        if not search:
            return frame
        needle = search.lower()
        strings = self._string_frame_cached()
        mask = pd.Series(False, index=strings.index)
        for col in frame.columns:
            mask = mask | strings[col].str.contains(needle, na=False, regex=False)
        if not mask.index.equals(frame.index):
            mask = mask.reindex(frame.index, fill_value=False)
        return frame[mask]

    def _populate(self, search: str = "") -> None:
        table = self.query_one("#table-data", DataTable)
        table.clear(columns=True)
        frame = self._frame
        if frame.empty:
            return
        all_columns = [str(c) for c in frame.columns]
        visible_columns = [c for c in all_columns if c not in self._hidden_columns]
        table.add_columns(*visible_columns)
        total_before = len(frame)
        work = self._filter_cached(frame, search)
        filtered_count = len(work)
        work = sort_frame_multi(work, self._sort_cols)
        work = work.head(defaults.DEFAULT_MAX_ROWS)
        rows = [
            [_fmt(value) for value in row]
            for row in work[visible_columns].itertuples(index=False, name=None)
        ]
        if rows:
            table.add_rows(rows)
        footer = self.query_one("#table-footer", Label)
        sort_text = ""
        if self._sort_cols:
            sort_text = "  ·  sorted by " + ", ".join(
                f"{c} {'↑' if a else '↓'}" for c, a in self._sort_cols
            )
        if search:
            footer.update(f"{filtered_count} rows (of {total_before}){sort_text}")
        else:
            footer.update(f"{filtered_count} rows{sort_text}")


def sort_frame(frame: pd.DataFrame, column: str | None, ascending: bool) -> pd.DataFrame:
    if not column or column not in frame.columns:
        return frame
    try:
        return frame.sort_values(by=column, ascending=ascending)
    except Exception:
        return frame


def sort_frame_multi(
    frame: pd.DataFrame, sort_cols: list[tuple[str, bool]]
) -> pd.DataFrame:
    valid = [(c, a) for c, a in sort_cols if c in frame.columns]
    if not valid:
        return frame
    try:
        return frame.sort_values(
            by=[c for c, _ in valid],
            ascending=[a for _, a in valid],
        )
    except Exception:
        return frame


def filter_frame(frame: pd.DataFrame, search: str) -> pd.DataFrame:
    if not search:
        return frame
    needle = search.lower()
    mask = pd.Series(False, index=frame.index)
    for col in frame.columns:
        col_mask = frame[col].astype(str).str.lower().str.contains(
            needle, na=False, regex=False
        )
        mask = mask | col_mask
    return frame[mask]


def _fmt(value: object) -> str:
    if value is None:
        return ""
    return str(value)
