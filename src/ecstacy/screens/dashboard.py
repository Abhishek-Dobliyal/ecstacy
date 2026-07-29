from __future__ import annotations

import math

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label

from ecstacy.config.schema import DashboardConfig, PanelConfig
from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.core.transforms import Transform, TransformError
from ecstacy.sources.base import Source, SourceError, SourceSpec, create_source
from ecstacy.util.timeparse import parse_duration
from ecstacy.widgets import create_viz
from ecstacy.widgets.base import ColumnMapping


def _mapping_from_panel(panel: PanelConfig) -> ColumnMapping:
    return ColumnMapping(
        x=panel.x,
        y=list(panel.y),
        category=panel.category,
        value=panel.value,
        bins=panel.bins,
    )


def _grid_size(n: int) -> tuple[int, int]:
    if n <= 1:
        return (1, 1)
    if n == 2:
        return (1, 2)
    if n <= 4:
        return (2, 2)
    if n <= 6:
        return (2, 3)
    if n <= 9:
        return (3, 3)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return (cols, rows)


class DashboardScreen(Screen):
    DEFAULT_CSS = """
    DashboardScreen #dashboard-holder {
        height: 1fr;
        padding: 0 1;
    }
    DashboardScreen #dashboard-grid {
        height: 1fr;
        grid-gutter: 1 1;
    }
    DashboardScreen #dashboard-holder > Container {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    DashboardScreen #dashboard-grid > Container {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("m", "toggle_layout", "Toggle layout"),
        ("n", "next_panel", "Next panel"),
        ("right", "next_panel", "Next panel"),
        ("p", "prev_panel", "Prev panel"),
        ("left", "prev_panel", "Prev panel"),
        ("r", "refresh", "Refresh now"),
        ("t", "app.toggle_theme", "Theme"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(
        self, dashboard: DashboardConfig, max_rows: int | None = None
    ) -> None:
        super().__init__()
        self.dashboard = dashboard
        self._max_rows = max_rows
        self._datasets: dict[str, DataSet] = {}
        self._sources: dict[str, Source] = {}
        self._panel_index = 0
        self._multi_panel = True
        self._scheduler: Scheduler | None = None
        self._jobs: list[Job] = []
        self._panel_widgets: dict[int, Widget] = {}
        self._panels_built = False
        self._render_pending = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(id="dashboard-holder")
        yield Footer()

    async def on_mount(self) -> None:
        await self._show_loading()
        self._start_scheduler()

    async def on_unmount(self) -> None:
        self._stop_scheduler()
        for source in self._sources.values():
            close = getattr(source, "close", None)
            if callable(close):
                close()

    def _stop_scheduler(self) -> None:
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None
        self._jobs = []

    def _start_scheduler(self) -> None:
        from ecstacy.widgets import resolve_viz

        self._stop_scheduler()
        interval = self._parse_refresh_interval()
        self._scheduler = Scheduler(self.app, is_active=lambda: self.app.screen is self)
        # Precompute which sources need the raw payload (only if a panel
        # using the json-tree viz references them).
        json_sources = {
            panel.source
            for panel in self.dashboard.panels
            if resolve_viz(panel.viz) == "json"
        }
        for spec in self.dashboard.sources:
            enriched = self._with_max_rows(spec)
            try:
                source = create_source(enriched)
            except SourceError as error:
                self.notify(
                    f"failed to create source {spec.id}: {error.message}",
                    severity="error",
                )
                continue
            self._sources[spec.id] = source
            job = Job(
                source=source,
                interval=interval,
                on_data=self._on_data(spec.id),
                on_error=self._on_error(spec.id),
                keep_raw=spec.id in json_sources,
            )
            self._jobs.append(job)
            self._scheduler.add(job)

    def _parse_refresh_interval(self) -> float:
        if not self.dashboard.refresh:
            return 0.0
        try:
            interval = parse_duration(self.dashboard.refresh)
        except Exception:
            return 0.0
        return interval if interval > 0 else 0.0

    def _on_data(self, source_id: str):
        def _handle(dataset: DataSet) -> None:
            if not self.is_attached:
                return
            self._datasets[source_id] = dataset
            if not self._panels_built:
                self._schedule_rebuild()
            else:
                self._update_panels_for(source_id)

        return _handle

    def _on_error(self, source_id: str):
        def _handle(error: Exception) -> None:
            msg = (
                f"failed to load {source_id}: {error.message}"
                if isinstance(error, SourceError)
                else f"failed to load {source_id}: {error}"
            )
            self.notify(msg, severity="error")

        return _handle

    async def _show_loading(self) -> None:
        holder = self.query_one("#dashboard-holder", Container)
        await holder.remove_children()
        await holder.mount(Label("loading dashboard...", id="dashboard-loading"))

    def _schedule_rebuild(self) -> None:
        if self._render_pending:
            return
        self._render_pending = True
        self.call_after_refresh(self._render_panels_safe)

    async def _render_panels_safe(self) -> None:
        self._render_pending = False
        await self._render_panels()

    def _update_panels_for(self, source_id: str) -> None:
        """Update only the panels fed by source_id, in place (no rebuild)."""
        dataset = self._datasets.get(source_id)
        if dataset is None:
            return
        # a panel whose widget couldn't be built yet (source was missing at
        # build time, or a viz/transform error) needs a full rebuild instead
        needs_rebuild = any(
            panel.source == source_id and idx not in self._panel_widgets
            for idx, panel in enumerate(self.dashboard.panels)
        )
        if needs_rebuild:
            self._schedule_rebuild()
            return
        targets = [
            (idx, panel)
            for idx, panel in enumerate(self.dashboard.panels)
            if panel.source == source_id
        ]
        if not targets:
            return

        def _work() -> None:
            # transforms + schema inference run off the UI thread
            results: list[tuple[int, DataSet | TransformError]] = []
            for idx, panel in targets:
                try:
                    frame = self._apply_transform(panel, dataset.frame)
                    transformed = DataSet.from_dataframe(
                        frame,
                        source_id=dataset.meta.source_id,
                        kind=dataset.meta.kind,
                        diet=False,
                    )
                except TransformError as error:
                    results.append((idx, error))
                else:
                    results.append((idx, transformed))
            try:
                self.app.call_from_thread(self._apply_panel_results, results)
            except RuntimeError:
                pass  # app shutting down

        self.run_worker(_work, thread=True, exclusive=False, exit_on_error=False)

    def _apply_panel_results(
        self, results: list[tuple[int, DataSet | TransformError]]
    ) -> None:
        for idx, result in results:
            widget = self._panel_widgets.get(idx)
            if widget is None or not widget.is_attached:
                continue
            if isinstance(result, TransformError):
                self.notify(
                    f"panel {idx + 1} transform error: {result.message}",
                    severity="error",
                )
                continue
            widget.set_data(result, _mapping_from_panel(self.dashboard.panels[idx]))

    async def action_refresh(self) -> None:
        if self._scheduler is None or not self._jobs:
            self.notify("nothing to refresh", severity="warning")
            return
        self.notify("refreshing...")
        for job in self._jobs:
            self._scheduler.run_now(job)

    def _with_max_rows(self, spec: SourceSpec) -> SourceSpec:
        # sql queries express their own row limits; socket has no max_rows
        if self._max_rows is None or spec.kind in ("sql", "socket"):
            return spec
        params = dict(spec.params)
        params.setdefault("max_rows", self._max_rows)
        return SourceSpec(kind=spec.kind, id=spec.id, params=params)

    async def _render_panels(self) -> None:
        holder = self.query_one("#dashboard-holder", Container)
        await holder.remove_children()
        self._panel_widgets = {}
        self._panels_built = False
        if not self.dashboard.panels:
            await holder.mount(Label("dashboard has no panels"))
            return
        if self._multi_panel:
            await self._render_multi(holder)
        else:
            await self._render_single(holder)
        self._panels_built = True
        # Rebuilding panels destroys the previously focused widget; reset focus
        # so panel search Inputs don't swallow the n/p/arrow screen bindings.
        self.set_focus(None)

    async def _render_multi(self, holder: Container) -> None:
        self.app.sub_title = ""  # clear any stale single-panel subtitle
        cols, rows = _grid_size(len(self.dashboard.panels))
        grid = Grid(id="dashboard-grid")
        grid.styles.grid_size = (cols, rows)
        await holder.mount(grid)
        for idx, panel in enumerate(self.dashboard.panels):
            container, content = self._prepare_panel_widget(idx, panel)
            await grid.mount(container)
            if content is not None:
                await container.mount(content)
                if not isinstance(content, Label):
                    self._panel_widgets[idx] = content

    async def _render_single(self, holder: Container) -> None:
        panel = self.dashboard.panels[self._panel_index]
        container, content = self._prepare_panel_widget(self._panel_index, panel)
        await holder.mount(container)
        if content is not None:
            await container.mount(content)
            if not isinstance(content, Label):
                self._panel_widgets[self._panel_index] = content
        self.app.sub_title = (
            f"{panel.viz} ({self._panel_index + 1}/{len(self.dashboard.panels)})"
        )

    def _prepare_panel_widget(
        self, index: int, panel: PanelConfig
    ) -> tuple[Container, Widget | Label | None]:
        container = Container(id=f"panel-{index}-{panel.source}")
        container.border_title = f"{panel.viz} · {panel.source}"
        dataset = self._datasets.get(panel.source)
        if dataset is None:
            return container, Label(f"source {panel.source!r} not loaded")
        try:
            widget: Widget = create_viz(panel.viz)
        except Exception as error:
            return container, Label(f"cannot create widget {panel.viz!r}: {error}")
        try:
            frame = self._apply_transform(panel, dataset.frame)
        except TransformError as error:
            return container, Label(f"transform error: {error.message}")
        transformed = DataSet.from_dataframe(
            frame,
            source_id=dataset.meta.source_id,
            kind=dataset.meta.kind,
            diet=False,
        )
        mapping = _mapping_from_panel(panel)
        widget.set_data(transformed, mapping)
        return container, widget

    def _apply_transform(self, panel: PanelConfig, frame: pd.DataFrame) -> pd.DataFrame:
        has_transform = (
            panel.where
            or panel.group_by
            or panel.select
            or panel.limit is not None
            or panel.agg != "sum"
        )
        if not has_transform:
            return frame
        transform = Transform(
            select=panel.select or None,
            where=panel.where,
            group_by=panel.group_by or None,
            agg=panel.agg,
            limit=panel.limit,
        )
        return transform.apply(frame)

    async def action_toggle_layout(self) -> None:
        self._multi_panel = not self._multi_panel
        await self._render_panels()
        self.notify("grid layout" if self._multi_panel else "single panel layout")

    async def action_next_panel(self) -> None:
        if self._multi_panel or not self.dashboard.panels:
            return
        self._panel_index = (self._panel_index + 1) % len(self.dashboard.panels)
        await self._render_panels()

    async def action_prev_panel(self) -> None:
        if self._multi_panel or not self.dashboard.panels:
            return
        self._panel_index = (self._panel_index - 1) % len(self.dashboard.panels)
        await self._render_panels()
