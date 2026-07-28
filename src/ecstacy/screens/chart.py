from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header

from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.sources.base import SourceError, SourceSpec, create_source
from ecstacy.widgets import create_viz, viz_names
from ecstacy.widgets.base import ColumnMapping


class ChartScreen(Screen):
    BINDINGS = [
        ("right", "next_viz", "Next viz"),
        ("n", "next_viz", "Next viz"),
        ("left", "prev_viz", "Prev viz"),
        ("p", "prev_viz", "Prev viz"),
        ("r", "refresh", "Refresh"),
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
        self.index = self.names.index(viz_name) if viz_name in self.names else 0
        self._scheduler: Scheduler | None = None
        self._job: Job | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(id="viz-holder")
        yield Footer()

    async def on_mount(self) -> None:
        await self._render_current()
        self._start_refresh()

    async def on_unmount(self) -> None:
        self._stop_refresh()

    def _stop_refresh(self) -> None:
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None
            self._job = None

    def _start_refresh(self) -> None:
        self._stop_refresh()
        if self.refresh_interval <= 0 or self.spec is None:
            return
        try:
            source = create_source(self.spec)
        except SourceError:
            return
        self._scheduler = Scheduler(self.app)
        self._job = Job(
            source=source,
            interval=self.refresh_interval,
            on_data=self._on_refresh_data,
            on_error=self._on_refresh_error,
        )
        self._scheduler.add(self._job)

    def _on_refresh_data(self, dataset: DataSet) -> None:
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
        if widget is not None and hasattr(widget, "set_data"):
            widget.set_data(self.dataset, self.mapping)
        self._update_border()

    def _update_border(self) -> None:
        holder = self.query_one("#viz-holder", Container)
        name = self.names[self.index]
        refresh_tag = (
            f"  ⟳ {self.refresh_interval:.0f}s" if self.refresh_interval > 0 else ""
        )
        holder.border_title = (
            f"{self.index + 1} {name}  |  {self.dataset.meta.source_id}{refresh_tag}"
        )
        holder.border_subtitle = (
            f"{self.dataset.meta.rows} rows   n next  p prev  r refresh  esc back"
        )

    async def _render_current(self) -> None:
        holder = self.query_one("#viz-holder", Container)
        await holder.remove_children()
        name = self.names[self.index]
        widget = create_viz(name)
        await holder.mount(widget)
        widget.set_data(self.dataset, self.mapping)
        self._update_border()
        self.app.sub_title = (
            f"{self.dataset.meta.source_id}  |  {name}  "
            f"({self.index + 1}/{len(self.names)})"
        )
        widget.styles.opacity = 0.0
        widget.styles.animate("opacity", 1.0, duration=0.25, easing="out_cubic")

    async def action_next_viz(self) -> None:
        self.index = (self.index + 1) % len(self.names)
        await self._render_current()

    async def action_prev_viz(self) -> None:
        self.index = (self.index - 1) % len(self.names)
        await self._render_current()

    async def action_refresh(self) -> None:
        if self._scheduler is not None and self._job is not None:
            self.notify("refreshing...")
            self._scheduler._run_once(self._job)
        else:
            self.notify("no refresh configured (use --refresh)", severity="warning")
