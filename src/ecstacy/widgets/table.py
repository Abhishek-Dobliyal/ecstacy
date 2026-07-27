from __future__ import annotations

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input

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
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame: pd.DataFrame = pd.DataFrame()
        self._sort_col: str | None = None
        self._sort_asc: bool = True
        self._pending_dataset: DataSet | None = None

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ to search  ·  type to filter rows", id="table-search")
        yield DataTable(id="table-data")

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

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        self._sort_col = None
        self._sort_asc = True
        if self.is_mounted:
            self._frame = dataset.frame
            self._populate()
        else:
            self._pending_dataset = dataset

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "table-search":
            return
        self._populate(event.value)

    def on_data_table_column_selected(self, event: DataTable.ColumnSelected) -> None:
        if event.data_table.id != "table-data":
            return
        col = str(event.column_key.value) if event.column_key else None
        if col is None:
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._populate()

    def _populate(self, search: str = "") -> None:
        table = self.query_one("#table-data", DataTable)
        table.clear(columns=True)
        frame = self._frame
        if frame.empty:
            return
        columns = [str(c) for c in frame.columns]
        table.add_columns(*columns)
        work = frame.head(defaults.DEFAULT_MAX_ROWS)
        work = sort_frame(work, self._sort_col, self._sort_asc)
        work = filter_frame(work, search)
        rows = [
            [_fmt(value) for value in row]
            for row in work.itertuples(index=False, name=None)
        ]
        if rows:
            table.add_rows(rows)


def sort_frame(frame: pd.DataFrame, column: str | None, ascending: bool) -> pd.DataFrame:
    if not column or column not in frame.columns:
        return frame
    try:
        return frame.sort_values(by=column, ascending=ascending)
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
