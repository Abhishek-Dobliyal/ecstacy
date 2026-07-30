from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label

from ecstacy.core import registry
from ecstacy.core.dataset import DataSet
from ecstacy.widgets.base import ColumnMapping

if TYPE_CHECKING:
    from textual.timer import Timer

_PAGE_SIZE = 200


class _LazyDataTable(DataTable):
    """DataTable subclass that triggers a callback when the user scrolls
    near the bottom, so the parent can load the next page of rows."""

    def __init__(self, on_near_bottom, page_size: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._on_near_bottom = on_near_bottom
        self._page_size = page_size

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:  # type: ignore[override]
        super().watch_scroll_y(old_value, new_value)
        if self.virtual_size.height - new_value - self.size.height < self._page_size:
            self._on_near_bottom()


@registry.viz.register("table")
class TableView(Vertical):
    viz_name = "table"
    BINDINGS = [
        ("s", "sort_prompt", "Sort"),
        ("c", "column_picker", "Columns"),
        ("e", "export_view", "Export"),
    ]
    DEFAULT_CSS = """
    TableView {
        height: 1fr;
    }
    TableView #table-data {
        height: 1fr;
    }
    TableView #table-footer {
        height: 1;
        margin: 0 0 1 0;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame: pd.DataFrame = pd.DataFrame()
        self._sort_cols: list[tuple[str, bool]] = []
        self._pending_dataset: DataSet | None = None
        self._search_timer: Timer | None = None
        self._search_value = ""
        self._hidden_columns: set[str] = set()
        self._string_frame: pd.DataFrame | None = None
        self._string_frame_source: pd.DataFrame | None = None
        self._search_gen = 0
        self._rendered_columns: tuple[str, ...] = ()
        self._columns_signature: tuple[str, ...] = ()
        self._full_view: pd.DataFrame | None = None
        self._loaded_count = 0
        self._loading = False

    def compose(self) -> ComposeResult:
        yield _LazyDataTable(
            on_near_bottom=self._load_next_page,
            page_size=_PAGE_SIZE,
            id="table-data",
        )
        yield Label("", id="table-footer")

    def on_mount(self) -> None:
        table = self.query_one("#table-data", DataTable)
        table.cursor_type = "column"
        table.zebra_stripes = True
        if self._pending_dataset is not None:
            self._frame = self._pending_dataset.frame
            self._columns_signature = tuple(str(c) for c in self._frame.columns)
            self._pending_dataset = None
            self._populate()

    def action_sort_prompt(self) -> None:
        table = self.query_one("#table-data", DataTable)
        table.focus()
        self.notify("use arrow keys to select a column, press enter to sort")

    def set_search(self, value: str) -> None:
        """Called by ChartScreen when the screen-level search input changes."""
        self._search_value = value
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(0.15, self._populate_after_debounce)

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
        if fmt not in ("csv", "json", "markdown"):
            self.notify(f"unknown format: {fmt}", severity="error")
            return
        frame = self._get_current_view()

        def _work() -> None:
            try:
                if fmt == "csv":
                    frame.to_csv(path, index=False)
                elif fmt == "json":
                    frame.to_json(path, orient="records", indent=2, date_format="iso")
                else:
                    frame.to_markdown(path, index=False)
            except Exception as exc:
                self._notify_threadsafe(f"export failed: {exc}", error=True)
                return
            self._notify_threadsafe(f"exported {len(frame)} rows to {path}")

        self.run_worker(_work, thread=True, exclusive=False, exit_on_error=False)

    def _notify_threadsafe(self, message: str, error: bool = False) -> None:
        try:
            self.app.call_from_thread(
                self.notify, message, severity="error" if error else "information"
            )
        except RuntimeError:
            pass  # app shutting down

    def _get_current_view(self) -> pd.DataFrame:
        frame = self._frame
        all_columns = [str(c) for c in frame.columns]
        visible_columns = [c for c in all_columns if c not in self._hidden_columns]
        work = sort_frame_multi(frame, self._sort_cols)
        work = self._filter_cached(work, self._search_value)
        return work[visible_columns]

    def _on_columns_picked(self, hidden: set[str] | None) -> None:
        if hidden is None:
            return
        self._hidden_columns = hidden
        self._populate(self._search_value)

    def set_data(self, dataset: DataSet, mapping: ColumnMapping | None = None) -> None:
        new_frame = dataset.frame
        new_sig = tuple(str(c) for c in new_frame.columns)
        if new_sig != self._columns_signature:
            self._sort_cols = []
            self._hidden_columns = set()
            self._columns_signature = new_sig
            self._loaded_count = 0
        # String cache invalidates on frame identity change; no manual bust needed.
        if self.is_mounted:
            self._frame = new_frame
            self._populate()
        else:
            self._pending_dataset = dataset

    def _populate_after_debounce(self) -> None:
        # Offload filter/sort to a thread; discard stale results via gen counter.
        self._search_gen += 1
        gen = self._search_gen
        search = self._search_value
        frame = self._frame
        sort_cols = list(self._sort_cols)
        hidden = set(self._hidden_columns)

        def _work() -> None:
            strings = self._string_frame
            if strings is None or self._string_frame_source is not frame:
                strings = frame.astype(str).apply(lambda col: col.str.lower())
                if self._frame is frame:
                    self._string_frame = strings
                    self._string_frame_source = frame
            work = frame
            if search:
                needle = search.lower()
                columns = [c for c in frame.columns if str(c) not in hidden]
                mask = pd.Series(False, index=strings.index)
                for col in columns:
                    mask = mask | strings[col].str.contains(needle, na=False, regex=False)
                work = frame[mask]
            filtered_count = len(work)
            work = sort_frame_multi(work, sort_cols)
            try:
                self.app.call_from_thread(
                    self._deliver_search,
                    gen,
                    search,
                    work,
                    filtered_count,
                    len(frame),
                    sort_cols,
                )
            except RuntimeError:
                pass  # app shutting down

        self.run_worker(_work, thread=True, exclusive=False, exit_on_error=False)

    def _deliver_search(
        self,
        gen: int,
        search: str,
        full_view: pd.DataFrame,
        filtered_count: int,
        total_before: int,
        sort_cols: list[tuple[str, bool]],
    ) -> None:
        if gen != self._search_gen or not self.is_mounted:
            return
        table = self.query_one("#table-data", DataTable)
        table.clear()  # rows only; column layout is unchanged
        self._full_view = full_view
        self._loaded_count = 0
        self._render_table_rows()
        footer = self.query_one("#table-footer", Label)
        footer.update(
            _footer_text(search, filtered_count, total_before, self._loaded_count, sort_cols)
        )

    def on_data_table_column_selected(self, event: DataTable.ColumnSelected) -> None:
        if event.data_table.id != "table-data":
            return
        visible_columns = [
            str(c) for c in self._frame.columns if str(c) not in self._hidden_columns
        ]
        index = event.cursor_column
        if not (0 <= index < len(visible_columns)):
            return
        col = visible_columns[index]
        existing = [(c, a) for c, a in self._sort_cols if c == col]
        if existing:
            idx = self._sort_cols.index(existing[0])
            self._sort_cols[idx] = (col, not self._sort_cols[idx][1])
        else:
            self._sort_cols.append((col, True))
        self._populate()

    def _string_frame_cached(self) -> pd.DataFrame:
        if self._string_frame is None or self._string_frame_source is not self._frame:
            self._string_frame = self._frame.astype(str).apply(
                lambda col: col.str.lower()
            )
            self._string_frame_source = self._frame
        return self._string_frame

    def _filter_cached(self, frame: pd.DataFrame, search: str) -> pd.DataFrame:
        if not search:
            return frame
        needle = search.lower()
        strings = self._string_frame_cached()
        columns = [c for c in frame.columns if str(c) not in self._hidden_columns]
        mask = pd.Series(False, index=strings.index)
        for col in columns:
            mask = mask | strings[col].str.contains(needle, na=False, regex=False)
        if not mask.index.equals(frame.index):
            mask = mask.reindex(frame.index, fill_value=False)
        return frame[mask]

    def _populate(self, search: str = "") -> None:
        self._search_gen += 1  # invalidate any in-flight search worker
        table = self.query_one("#table-data", DataTable)
        frame = self._frame
        if frame.empty:
            table.clear(columns=True)
            self._rendered_columns = ()
            self._full_view = None
            self._loaded_count = 0
            return
        all_columns = [str(c) for c in frame.columns]
        visible_columns = [c for c in all_columns if c not in self._hidden_columns]
        if tuple(visible_columns) != self._rendered_columns:
            table.clear(columns=True)
            table.add_columns(*visible_columns)
            self._rendered_columns = tuple(visible_columns)
        else:
            table.clear()  # rows only; column layout is unchanged
        total_before = len(frame)
        work = self._filter_cached(frame, search)
        filtered_count = len(work)
        work = sort_frame_multi(work, self._sort_cols)
        self._full_view = work
        self._loaded_count = 0
        self._render_table_rows()
        footer = self.query_one("#table-footer", Label)
        footer.update(
            _footer_text(search, filtered_count, total_before, self._loaded_count, self._sort_cols)
        )

    def _render_table_rows(self) -> None:
        """Append the next page of rows from _full_view to the DataTable."""
        if self._full_view is None or self._loading:
            return
        self._loading = True
        table = self.query_one("#table-data", DataTable)
        visible_columns = [
            str(c) for c in self._full_view.columns
            if str(c) not in self._hidden_columns
        ]
        end = min(self._loaded_count + _PAGE_SIZE, len(self._full_view))
        if end <= self._loaded_count:
            self._loading = False
            return
        slc = self._full_view.iloc[self._loaded_count:end]
        rows = [
            [_fmt(value) for value in row]
            for row in slc[visible_columns].itertuples(index=False, name=None)
        ]
        if rows:
            table.add_rows(rows)
        self._loaded_count = end
        self._loading = False

    def _load_next_page(self) -> None:
        """Called by _LazyDataTable when the user scrolls near the bottom."""
        if (
            self._full_view is None
            or self._loading
            or self._loaded_count >= len(self._full_view)
        ):
            return
        self._render_table_rows()
        # Update footer to reflect newly loaded rows
        footer = self.query_one("#table-footer", Label)
        total = len(self._full_view)
        search = self._search_value
        footer.update(
            _footer_text(
                search,
                total,
                len(self._frame),
                self._loaded_count,
                self._sort_cols,
            )
        )


def _footer_text(
    search: str,
    filtered_count: int,
    total_before: int,
    shown: int,
    sort_cols: list[tuple[str, bool]],
) -> str:
    sort_text = ""
    if sort_cols:
        sort_text = "  ·  sorted by " + ", ".join(
            f"{c} {'↑' if a else '↓'}" for c, a in sort_cols
        )
    if filtered_count > shown:
        count_text = f"showing {shown} of {filtered_count} rows  ·  scroll for more"
    else:
        count_text = f"{filtered_count} rows"
    if search:
        count_text += f" (of {total_before})"
    return f"{count_text}{sort_text}"


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
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)
