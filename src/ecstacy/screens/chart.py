from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Input, Label

from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.core.transforms import TransformError, parse_transform_query
from ecstacy.sources.base import Source, SourceError, SourceSpec, StreamableSource, create_source
from ecstacy.widgets import create_viz, resolve_viz, viz_names
from ecstacy.widgets.base import ColumnMapping

if TYPE_CHECKING:
    from textual.worker import Worker


class ChartScreen(Screen):
    DEFAULT_CSS = """
    ChartScreen #input-row {
        height: 1;
        margin: 1 0 0 0;
        padding: 0;
    }
    ChartScreen #search-bar {
        width: 1fr;
        border: none;
        padding: 0 1;
        background: $surface;
    }
    ChartScreen #transform-bar {
        width: 1fr;
        border: none;
        padding: 0 1;
        background: $surface;
    }
    ChartScreen #viz-holder {
        height: 1fr;
    }
    ChartScreen #chart-note {
        height: 1;
        content-align: center middle;
        color: $text-muted;
    }
    """
    BINDINGS = [
        ("right", "next_viz", "Next viz"),
        ("n", "next_viz", "Next viz"),
        ("left", "prev_viz", "Prev viz"),
        ("p", "prev_viz", "Prev viz"),
        ("r", "refresh", "Refresh"),
        ("ctrl+f", "focus_transform", "Query"),
        ("slash", "focus_search", "Search"),
        ("c", "column_picker", "Columns"),
        ("t", "app.toggle_theme", "Theme"),
        ("escape", "escape", "Back"),
    ]

    def __init__(
        self,
        dataset: DataSet,
        viz_name: str = "table",
        mapping: ColumnMapping | None = None,
        spec: SourceSpec | None = None,
        refresh: float = 0.0,
    ) -> None:
        super().__init__()
        self.dataset = dataset
        self.mapping = mapping
        self.spec = spec
        self.refresh_interval = refresh
        self.names = viz_names()
        resolved = resolve_viz(viz_name)
        self.index = self.names.index(resolved) if resolved in self.names else 0
        self._scheduler: Scheduler | None = None
        self._job: Job | None = None
        self._source: Source | None = None
        self._stream_worker: Worker | None = None
        self._transform_query = ""
        self._transform_cache: DataSet | None = None
        self._transform_cache_key: tuple[int, str] | None = None
        self._viz_pool: dict[str, Widget] = {}
        self._active_widget: Widget | None = None
        self._toast_note = False

    def _on_chart_note(self, note: str | None) -> None:
        """Update the chart footer label and toast once on note change."""
        label = self.query_one("#chart-note", Label)
        if note:
            label.update(note)
            label.display = True
            if self._toast_note:
                self.notify(note, severity="information")
                self._toast_note = False
        else:
            label.update("")
            label.display = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="input-row"):
            search_bar = Input(
                placeholder="/ to search  ·  type to filter rows", id="search-bar"
            )
            search_bar.can_focus = False
            yield search_bar
            transform_bar = Input(
                placeholder=(
                    "ctrl+f to query · join clauses with | (any source, not SQL)  ·  "
                    "where value > 100 | group_by region | agg mean | limit 10"
                ),
                id="transform-bar",
            )
            transform_bar.can_focus = False
            yield transform_bar
        yield Container(id="viz-holder")
        yield Label("", id="chart-note")
        yield Footer()

    def action_focus_transform(self) -> None:
        if self._active_widget is not None and hasattr(self._active_widget, "set_search"):
            bar = self.query_one("#transform-bar", Input)
            bar.can_focus = True
            bar.focus()

    def action_focus_search(self) -> None:
        if self._active_widget is not None and hasattr(self._active_widget, "set_search"):
            bar = self.query_one("#search-bar", Input)
            bar.can_focus = True
            bar.focus()

    def action_column_picker(self) -> None:
        from ecstacy.screens.modals import VIZ_NO_MAPPING, ChartMappingScreen
        from ecstacy.widgets.base import auto_mapping

        name = self.names[self.index]
        if name in VIZ_NO_MAPPING:
            self.notify("this view has no column mapping", severity="information")
            return
        dataset = self._get_transformed_dataset()
        columns = dataset.schema.columns
        current = self.mapping or auto_mapping(dataset, name)
        self.app.push_screen(
            ChartMappingScreen(name, columns, current),
            self._on_mapping_picked,
        )

    def _on_mapping_picked(self, result: ColumnMapping | None) -> None:
        if result is None:
            return
        self.mapping = result
        dataset = self._get_transformed_dataset()
        if self._active_widget is not None and hasattr(self._active_widget, "set_data"):
            self._active_widget.set_data(dataset, self.mapping)  # type: ignore[attr-defined]
        self._update_border(dataset)

    def action_escape(self) -> None:
        """Exit search/query input first; pop screen when no input is focused."""
        focused = self.focused
        if isinstance(focused, Input):
            focused.can_focus = False
            if self._active_widget is not None:
                self._focus_content(self._active_widget)
            else:
                self.set_focus(None)
            return
        self.app.pop_screen()

    async def on_mount(self) -> None:
        await self._render_current()
        self._start_refresh()

    async def on_unmount(self) -> None:
        self._stop_refresh()

    def _stop_refresh(self) -> None:
        from ecstacy.core.stream import close_source

        if self._stream_worker is not None:
            self._stream_worker.cancel()
            self._stream_worker = None
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None
        if self._source is not None:
            close_source(self._source)
            self._source = None
        self._job = None

    def _start_refresh(self) -> None:
        from ecstacy.widgets import resolve_viz

        self._stop_refresh()
        if self.spec is None:
            return
        try:
            source = create_source(self.spec)
        except SourceError as error:
            self.notify(f"refresh unavailable: {error.message}", severity="warning")
            return
        self._source = source
        if getattr(source, "is_stdin", False):
            return  # re-reading stdin would hit EOF or block on a live pipe
        keep_raw = resolve_viz(self.names[self.index]) == "json"
        if isinstance(source, StreamableSource):
            self._start_stream(source, keep_raw=keep_raw)
            return
        self._scheduler = Scheduler(self.app, is_active=lambda: self.app.screen is self)
        self._job = Job(
            source=source,
            interval=self.refresh_interval,
            on_data=self._on_refresh_data,
            on_error=self._on_refresh_error,
            keep_raw=keep_raw,
        )
        # data is already fresh from the initial fetch; don't refetch at t=0
        self._scheduler.add(self._job, run_immediately=False)

    def _start_stream(self, source: Source, keep_raw: bool = False) -> None:
        self._stream_worker = self.run_worker(
            self._consume_stream(source, keep_raw=keep_raw),
            exclusive=True,
            exit_on_error=False,
        )

    async def _consume_stream(self, source: Source, keep_raw: bool = False) -> None:
        from ecstacy.core.stream import consume_stream

        await consume_stream(
            source=source,
            screen=self,
            on_data=self._on_refresh_data,
            on_error=self._on_refresh_error,
            keep_raw=keep_raw,
            on_done=lambda: setattr(self, "_stream_worker", None),
        )

    def _on_refresh_data(self, dataset: DataSet) -> None:
        if not self.is_attached:
            return
        self.dataset = dataset
        self.call_after_refresh(self._update_current_widget)

    def _on_refresh_error(self, error: Exception) -> None:
        msg = (
            f"refresh failed: {error.message}"
            if isinstance(error, SourceError)
            else f"refresh failed: {error}"
        )
        self.notify(msg, severity="error")

    async def _update_current_widget(self) -> None:
        widget = self._active_widget
        dataset = self._get_transformed_dataset()
        if widget is not None and hasattr(widget, "set_data"):
            widget.set_data(dataset, self.mapping)  # type: ignore[attr-defined]
        self._update_border(dataset)

    def _update_table_bindings(self, is_table: bool) -> None:
        """Show the search/query footer bindings only in table view."""
        for key in ("slash", "ctrl+f"):
            try:
                bindings = self._bindings.get_bindings_for_key(key)
            except Exception:
                continue
            self._bindings.key_to_bindings[key] = [
                replace(binding, show=is_table) for binding in bindings
            ]
        self.refresh_bindings()

    def _update_border(self, dataset: DataSet | None = None) -> None:
        dataset = dataset or self.dataset
        holder = self.query_one("#viz-holder", Container)
        name = self.names[self.index]
        refresh_tag = (
            f"  ⟳ {self.refresh_interval:.0f}s" if self.refresh_interval > 0 else ""
        )
        holder.border_title = (
            f"{self.index + 1} {name}  |  {dataset.meta.source_id}{refresh_tag}"
        )
        holder.border_subtitle = (
            f"{dataset.meta.rows} rows   n next  p prev  r refresh  esc back"
        )

    async def action_next_viz(self) -> None:
        self.index = (self.index + 1) % len(self.names)
        await self._render_current()

    async def action_prev_viz(self) -> None:
        self.index = (self.index - 1) % len(self.names)
        await self._render_current()

    async def action_refresh(self) -> None:
        if self._scheduler is not None and self._job is not None:
            self.notify("refreshing...")
            self._scheduler.run_now(self._job, force=True)
        else:
            self.notify("no refresh configured (use --refresh)", severity="warning")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "transform-bar":
            return
        self._transform_query = event.value.strip()
        await self._render_current()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-bar":
            return
        widget = self._active_widget
        if widget is not None and hasattr(widget, "set_search"):
            widget.set_search(event.value)

    def _get_transformed_dataset(self) -> DataSet:
        key = (id(self.dataset), self._transform_query)
        if self._transform_cache_key == key and self._transform_cache is not None:
            return self._transform_cache
        if not self._transform_query:
            result = self.dataset
        else:
            try:
                transform = parse_transform_query(self._transform_query)
                frame = transform.apply(self.dataset.frame)
            except TransformError as error:
                self.notify(f"query error: {error.message}", severity="warning")
                result = self.dataset
            except Exception as error:
                self.notify(f"query error: {error}", severity="warning")
                result = self.dataset
            else:
                result = DataSet.from_dataframe(
                    frame,
                    source_id=self.dataset.meta.source_id,
                    kind=self.dataset.meta.kind,
                    diet=False,
                )
        self._transform_cache_key = key
        self._transform_cache = result
        return result

    def _focus_content(self, widget: Widget) -> None:
        """Focus the widget's interactive part to prevent Input from swallowing bindings."""
        tables = widget.query(DataTable)
        if tables:
            self.set_focus(tables.first())
        else:
            self.set_focus(None)

    async def _render_current(self) -> None:
        holder = self.query_one("#viz-holder", Container)
        name = self.names[self.index]
        if self._active_widget is not None:
            self._active_widget.display = False
        # Pool widgets to avoid mount/unmount on every cycle.
        if name not in self._viz_pool:
            widget = create_viz(name)
            await holder.mount(widget)
            self._viz_pool[name] = widget
        else:
            widget = self._viz_pool[name]
            widget.display = True
        self._active_widget = widget
        # Show search/query bars for table only; preserve previous search.
        search_bar = self.query_one("#search-bar", Input)
        transform_bar = self.query_one("#transform-bar", Input)
        is_table = hasattr(widget, "set_search")
        search_bar.display = is_table
        transform_bar.display = is_table
        self._update_table_bindings(is_table)
        # Keep the pooled table's DataTable out of the focus chain while it
        # is hidden.  On screen resume Textual's auto-focus (AUTO_FOCUS="*")
        # ignores display:none and would focus it, routing keys like "c" to
        # the table's bindings while a chart is shown.
        pooled_table = self._viz_pool.get("table")
        if pooled_table is not None:
            for data_table in pooled_table.query(DataTable):
                data_table.can_focus = is_table
        if is_table:
            search_bar.value = widget._search_value  # type: ignore[attr-defined]
        else:
            if hasattr(widget, "set_on_note"):
                widget.set_on_note(self._on_chart_note)
                self._toast_note = True
        dataset = self._get_transformed_dataset()
        widget.set_data(dataset, self.mapping)  # type: ignore[attr-defined]
        self._update_border(dataset)
        self.app.sub_title = (
            f"{dataset.meta.source_id}  |  {name}  "
            f"({self.index + 1}/{len(self.names)})"
        )
        # NOTE: no fade-in animation here — animating opacity refreshes the
        # widget every animation frame, which forces a full plotext rebuild
        # (~100ms+) per frame and stalls the UI on every viz switch.
        self._focus_content(widget)
