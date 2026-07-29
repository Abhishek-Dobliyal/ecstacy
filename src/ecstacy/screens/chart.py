from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Input

from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.core.transforms import TransformError, parse_transform_query
from ecstacy.sources.base import Source, SourceError, SourceSpec, create_source
from ecstacy.widgets import create_viz, resolve_viz, viz_names
from ecstacy.widgets.base import ColumnMapping

if TYPE_CHECKING:
    from textual.worker import Worker


class ChartScreen(Screen):
    DEFAULT_CSS = """
    ChartScreen #transform-bar {
        height: 1;
        margin: 0 0 0 0;
        border: round $accent;
        padding: 0 1;
    }
    ChartScreen #viz-holder {
        height: 1fr;
    }
    """
    BINDINGS = [
        ("right", "next_viz", "Next viz"),
        ("n", "next_viz", "Next viz"),
        ("left", "prev_viz", "Prev viz"),
        ("p", "prev_viz", "Prev viz"),
        ("r", "refresh", "Refresh"),
        ("ctrl+f", "focus_transform", "Query"),
        ("t", "app.toggle_theme", "Theme"),
        ("escape", "app.pop_screen", "Back"),
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
        self._stream_worker: Worker | None = None
        self._transform_query = ""
        self._transform_cache: DataSet | None = None
        self._transform_cache_key: tuple[int, str] | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        placeholder = (
            "ctrl+f to query  ·  where value > 100 | group_by region | agg mean | limit 10"
        )
        yield Input(placeholder=placeholder, id="transform-bar")
        yield Container(id="viz-holder")
        yield Footer()

    def action_focus_transform(self) -> None:
        self.query_one("#transform-bar", Input).focus()

    async def on_mount(self) -> None:
        await self._render_current()
        self._start_refresh()

    async def on_unmount(self) -> None:
        self._stop_refresh()

    def _stop_refresh(self) -> None:
        if self._stream_worker is not None:
            self._stream_worker.cancel()
            self._stream_worker = None
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None
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
        if getattr(source, "is_stdin", False):
            return  # re-reading stdin would hit EOF or block on a live pipe
        keep_raw = resolve_viz(self.names[self.index]) == "json"
        if getattr(source, "supports_stream", False):
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
        stream = source.stream(keep_raw=keep_raw)
        try:
            async for dataset in stream:
                self._on_refresh_data(dataset)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._on_refresh_error(error)
        finally:
            await stream.aclose()

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
        holder = self.query_one("#viz-holder", Container)
        widget = holder.children[0] if holder.children else None
        dataset = self._get_transformed_dataset()
        if widget is not None and hasattr(widget, "set_data"):
            widget.set_data(dataset, self.mapping)
        self._update_border(dataset)

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
            self._scheduler.run_now(self._job)
        else:
            self.notify("no refresh configured (use --refresh)", severity="warning")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "transform-bar":
            return
        self._transform_query = event.value.strip()
        await self._render_current()

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
        """Focus the interactive part of the newly rendered widget.

        Without this, auto-focus lands on the transform-bar Input whenever the
        previously focused widget is unmounted, and keys like n/p/arrows get
        swallowed by the Input instead of reaching the screen bindings.
        """
        tables = widget.query(DataTable)
        if tables:
            self.set_focus(tables.first())
        else:
            self.set_focus(None)

    async def _render_current(self) -> None:
        holder = self.query_one("#viz-holder", Container)
        await holder.remove_children()
        name = self.names[self.index]
        widget = create_viz(name)
        await holder.mount(widget)
        dataset = self._get_transformed_dataset()
        widget.set_data(dataset, self.mapping)
        self._update_border(dataset)
        self.app.sub_title = (
            f"{dataset.meta.source_id}  |  {name}  "
            f"({self.index + 1}/{len(self.names)})"
        )
        widget.styles.opacity = 0.0
        widget.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")
        self._focus_content(widget)
