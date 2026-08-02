from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd
from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Footer, Header, Label

from ecstacy.config.schema import DashboardConfig, PanelConfig
from ecstacy.core.dataset import DataSet, Meta, Schema
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.core.stream import close_source, consume_stream
from ecstacy.core.transforms import Transform, TransformError
from ecstacy.sources.base import Source, SourceError, SourceSpec, StreamableSource, create_source
from ecstacy.util.timeparse import parse_duration
from ecstacy.widgets import create_viz, resolve_viz
from ecstacy.widgets.base import ColumnMapping

if TYPE_CHECKING:
    from textual.worker import Worker


def _mapping_from_panel(panel: PanelConfig) -> ColumnMapping:
    return ColumnMapping(
        x=panel.x,
        y=list(panel.y),
        category=panel.category,
        value=panel.value,
        bins=panel.bins,
    )


def _panel_has_transform(panel: PanelConfig) -> bool:
    return bool(
        panel.where
        or panel.group_by
        or panel.select
        or panel.limit is not None
        or panel.agg != "sum"
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
        self._stream_workers: list[Worker] = []
        self._stream_sources: set[str] = set()
        self._panel_widgets: dict[int, Widget] = {}
        self._panel_cache: dict[int, tuple[int, DataSet]] = {}
        self._single_pool: dict[int, Container] = {}
        self._panel_widget_data: dict[int, int] = {}
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
            close_source(source)

    def _stop_scheduler(self) -> None:
        for worker in self._stream_workers:
            worker.cancel()
        self._stream_workers = []
        self._stream_sources = set()
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None
        self._jobs = []

    def _start_scheduler(self) -> None:
        self._stop_scheduler()
        interval = self._parse_refresh_interval()
        self._scheduler = Scheduler(self.app, is_active=lambda: self.app.screen is self)
        # Determine which sources need raw JSON for json-tree panels.
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
            keep_raw = spec.id in json_sources
            if isinstance(source, StreamableSource):
                self._start_stream(source, spec.id, keep_raw)
                continue
            job = Job(
                source=source,
                interval=interval,
                on_data=self._on_data(spec.id),
                on_error=self._on_error(spec.id),
                keep_raw=keep_raw,
            )
            self._jobs.append(job)
            self._scheduler.add(job)

    def _start_stream(self, source: Source, source_id: str, keep_raw: bool) -> None:
        # Seed with a one-shot fetch to avoid waiting for first stream batch.
        def _seed() -> None:
            try:
                dataset = source.fetch(keep_raw=keep_raw)
            except Exception as error:
                self._on_error(source_id)(error)
                return
            self._on_data(source_id)(dataset)

        self.run_worker(_seed, thread=True, exclusive=False, exit_on_error=False)
        # Start the async stream consumer for live updates.
        worker = self.run_worker(
            self._consume_stream(source, source_id, keep_raw=keep_raw),
            exclusive=True,
            exit_on_error=False,
        )
        self._stream_workers.append(worker)
        self._stream_sources.add(source_id)

    async def _consume_stream(
        self, source: Source, source_id: str, keep_raw: bool = False
    ) -> None:
        await consume_stream(
            source=source,
            screen=self,
            on_data=self._on_data(source_id),
            on_error=self._on_error(source_id),
            keep_raw=keep_raw,
        )

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
            if not self.is_attached:
                return
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
        # Missing or errored panels need a full rebuild. In single-panel
        # mode only the visible panel matters — hidden/unvisited panels are
        # created lazily by _show_single_panel.
        if self._multi_panel:
            needs_rebuild = any(
                panel.source == source_id and idx not in self._panel_widgets
                for idx, panel in enumerate(self.dashboard.panels)
            )
        else:
            needs_rebuild = (
                self.dashboard.panels[self._panel_index].source == source_id
                and self._panel_index not in self._panel_widgets
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
            # Offload transforms to a thread; skip via cache when unchanged.
            results: list[tuple[int, DataSet | TransformError]] = []
            upstream_id = dataset._id
            for idx, panel in targets:
                cached = self._panel_cache.get(idx)
                if cached is not None and cached[0] == upstream_id:
                    results.append((idx, cached[1]))
                    continue
                try:
                    frame = self._apply_transform(panel, dataset.frame)
                    transformed = self._build_transformed(panel, dataset, frame)
                except TransformError as error:
                    results.append((idx, error))
                else:
                    self._panel_cache[idx] = (upstream_id, transformed)
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
            if not self._multi_panel:
                container = self._single_pool.get(idx)
                if container is not None and not container.display:
                    # Hidden pooled panel — skip the paint/rebuild; it is
                    # refreshed lazily from _panel_cache when shown again.
                    continue
            widget.set_data(result, _mapping_from_panel(self.dashboard.panels[idx]))  # type: ignore[attr-defined]
            cached = self._panel_cache.get(idx)
            if cached is not None:
                self._panel_widget_data[idx] = cached[0]

    async def action_refresh(self) -> None:
        has_poll = self._scheduler is not None and bool(self._jobs)
        has_stream = bool(self._stream_sources)
        if has_poll:
            self.notify("refreshing...")
            assert self._scheduler is not None
            for job in self._jobs:
                self._scheduler.run_now(job, force=True)
        elif has_stream:
            self.notify("stream sources update automatically", severity="information")
        else:
            self.notify("nothing to refresh", severity="warning")

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
        self._single_pool = {}
        self._panel_widget_data = {}
        self._panels_built = False
        if not self.dashboard.panels:
            await holder.mount(Label("dashboard has no panels"))
            return
        if self._multi_panel:
            await self._render_multi(holder)
        else:
            await self._render_single(holder)
        self._panels_built = True
        # Reset focus so rebuild doesn't swallow navigation bindings.
        self.set_focus(None)

    async def _render_multi(self, holder: Container) -> None:
        self.app.sub_title = ""  # clear any stale single-panel subtitle
        cols, rows = _grid_size(len(self.dashboard.panels))
        grid = Grid(id="dashboard-grid")
        grid.styles.grid_size = (cols, rows)  # type: ignore[attr-defined]
        await holder.mount(grid)
        for idx, panel in enumerate(self.dashboard.panels):
            container, content = self._prepare_panel_widget(idx, panel)
            await grid.mount(container)
            if content is not None:
                await container.mount(content)
                if not isinstance(content, Label):
                    self._panel_widgets[idx] = content

    async def _render_single(self, holder: Container) -> None:
        await self._show_single_panel()

    async def _show_single_panel(self) -> None:
        """Show the current panel in single-panel mode.

        Panels are pooled (created lazily on first visit, then hidden with
        display=False) so cycling n/p doesn't tear down and rebuild widgets
        every time.  A panel whose source data changed while it was hidden
        is refreshed from _panel_cache on show.
        """
        holder = self.query_one("#dashboard-holder", Container)
        index = self._panel_index
        panel = self.dashboard.panels[index]
        for other in self._single_pool.values():
            other.display = False
        pooled = self._single_pool.get(index)
        has_data = self._datasets.get(panel.source) is not None
        if pooled is not None and (index in self._panel_widgets or not has_data):
            pooled.display = True
            widget = self._panel_widgets.get(index)
            cached = self._panel_cache.get(index)
            if (
                widget is not None
                and cached is not None
                and self._panel_widget_data.get(index) != cached[0]
            ):
                widget.set_data(cached[1], _mapping_from_panel(panel))  # type: ignore[attr-defined]
                self._panel_widget_data[index] = cached[0]
        else:
            if pooled is not None:
                # Stale placeholder (e.g. a "source not loaded" label whose
                # data has since arrived) — replace it with a real widget.
                await pooled.remove()
                del self._single_pool[index]
            container, content = self._prepare_panel_widget(index, panel)
            await holder.mount(container)
            self._single_pool[index] = container
            if content is not None:
                await container.mount(content)
                if not isinstance(content, Label):
                    self._panel_widgets[index] = content
        self.app.sub_title = (
            f"{panel.viz} ({index + 1}/{len(self.dashboard.panels)})"
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
        cached = self._panel_cache.get(index)
        if cached is not None and cached[0] == dataset._id:
            transformed = cached[1]
        else:
            try:
                frame = self._apply_transform(panel, dataset.frame)
            except TransformError as error:
                return container, Label(f"transform error: {error.message}")
            transformed = self._build_transformed(panel, dataset, frame)
            self._panel_cache[index] = (dataset._id, transformed)
        mapping = _mapping_from_panel(panel)
        if hasattr(widget, "set_on_note"):
            def _on_note(note: str | None) -> None:
                if container.is_attached:
                    value = note or ""
                    if value != getattr(container, "_last_subtitle", None):
                        container._last_subtitle = value  # type: ignore[attr-defined]
                        container.border_subtitle = value
            widget.set_on_note(_on_note)
        widget.set_data(transformed, mapping)  # type: ignore[attr-defined]
        self._panel_widget_data[index] = dataset._id
        return container, widget

    def _build_transformed(
        self, panel: PanelConfig, dataset: DataSet, frame: pd.DataFrame
    ) -> DataSet:
        """Build a DataSet from a transformed frame. Optimizes schema reuse
        for where-only and select/limit transforms; runs full inference for
        group/agg/resample."""
        if not _panel_has_transform(panel):
            return dataset
        has_grouping = bool(panel.group_by) or getattr(panel, "resample", None)
        has_select = bool(panel.select)
        has_where = bool(panel.where)
        source_id = dataset.meta.source_id
        kind = dataset.meta.kind
        # where-only: same columns, fewer rows
        if has_where and not has_grouping and not has_select:
            return DataSet(
                frame=frame,
                schema=dataset.schema,
                meta=Meta(source_id=source_id, kind=kind, rows=len(frame)),
            )
        # select/limit-only: schema is a subset of the upstream schema
        if (has_select or panel.limit is not None) and not has_where and not has_grouping:
            cols = [str(c) for c in frame.columns]
            sub_schema = Schema(
                columns=cols,
                dtypes={c: dataset.schema.dtypes.get(c, str(frame[c].dtype)) for c in cols},
                roles={c: dataset.schema.roles.get(c, "category") for c in cols},
            )
            return DataSet(
                frame=frame,
                schema=sub_schema,
                meta=Meta(source_id=source_id, kind=kind, rows=len(frame)),
            )
        # full transform (group_by/agg/resample): columns differ
        return DataSet.from_dataframe(
            frame, source_id=source_id, kind=kind, diet=False,
        )

    def _apply_transform(self, panel: PanelConfig, frame: pd.DataFrame) -> pd.DataFrame:
        if not _panel_has_transform(panel):
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
        await self._show_single_panel()

    async def action_prev_panel(self) -> None:
        if self._multi_panel or not self.dashboard.panels:
            return
        self._panel_index = (self._panel_index - 1) % len(self.dashboard.panels)
        await self._show_single_panel()
