from __future__ import annotations

import math

from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from ecstacy.config.schema import DashboardConfig, PanelConfig
from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler
from ecstacy.core.store import Store
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
        self, dashboard: DashboardConfig, store: Store, max_rows: int | None = None
    ) -> None:
        super().__init__()
        self.dashboard = dashboard
        self.store = store
        self._max_rows = max_rows
        self._datasets: dict[str, DataSet] = {}
        self._sources: dict[str, Source] = {}
        self._panel_index = 0
        self._multi_panel = True
        self._scheduler: Scheduler | None = None
        self._refresh_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(id="dashboard-holder")
        yield Footer()

    async def on_mount(self) -> None:
        await self._show_loading()
        await self._fetch_all_async()
        await self._render_panels()
        self._start_refresh()

    async def on_unmount(self) -> None:
        self._stop_refresh()

    def _stop_refresh(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None
        if self._scheduler is not None:
            self._scheduler.stop()
            self._scheduler = None

    def _start_refresh(self) -> None:
        self._stop_refresh()
        if not self.dashboard.refresh:
            return
        try:
            interval = parse_duration(self.dashboard.refresh)
        except Exception:
            return
        if interval <= 0:
            return
        self._refresh_timer = self.set_interval(interval, self._on_refresh_tick)

    async def _show_loading(self) -> None:
        holder = self.query_one("#dashboard-holder", Container)
        await holder.remove_children()
        await holder.mount(Label("loading dashboard...", id="dashboard-loading"))

    async def _fetch_all_async(self) -> None:
        self.run_worker(self._fetch_all, thread=True, exclusive=True)

    def _fetch_all(self) -> None:
        results: dict[str, DataSet] = {}
        errors: list[str] = []
        for spec in self.dashboard.sources:
            enriched = self._with_max_rows(spec)
            try:
                source = create_source(enriched)
                dataset = source.fetch()
            except SourceError as error:
                errors.append(str(error))
                continue
            except Exception as error:
                errors.append(f"failed to load {spec.id}: {error}")
                continue
            results[spec.id] = dataset
            self._sources[spec.id] = source
            self.store.set(spec.id, dataset)
        self.app.call_from_thread(self._apply_fetch_results, results, errors)

    def _apply_fetch_results(
        self, results: dict[str, DataSet], errors: list[str]
    ) -> None:
        self._datasets.update(results)
        for msg in errors:
            self.notify(msg, severity="error")

    def _on_refresh_tick(self) -> None:
        self.run_worker(self._fetch_all, thread=True, exclusive=True)
        self.call_from_thread(self._render_panels_safe)

    async def _render_panels_safe(self) -> None:
        await self._render_panels()

    async def action_refresh(self) -> None:
        self.notify("refreshing...")
        self.run_worker(self._fetch_all, thread=True, exclusive=True)
        await self._render_panels()

    def _with_max_rows(self, spec: SourceSpec) -> SourceSpec:
        if self._max_rows is None or spec.kind == "sql":
            return spec
        params = dict(spec.params)
        params.setdefault("max_rows", self._max_rows)
        return SourceSpec(kind=spec.kind, id=spec.id, params=params)

    async def _render_panels(self) -> None:
        holder = self.query_one("#dashboard-holder", Container)
        await holder.remove_children()
        if not self.dashboard.panels:
            await holder.mount(Label("dashboard has no panels"))
            return
        if self._multi_panel:
            await self._render_multi(holder)
        else:
            await self._render_single(holder)

    async def _render_multi(self, holder: Container) -> None:
        cols, rows = _grid_size(len(self.dashboard.panels))
        grid = Grid(id="dashboard-grid")
        grid.styles.grid_size = (cols, rows)
        await holder.mount(grid)
        for idx, panel in enumerate(self.dashboard.panels):
            container, content = self._prepare_panel_widget(idx, panel)
            await grid.mount(container)
            if content is not None:
                await container.mount(content)

    async def _render_single(self, holder: Container) -> None:
        panel = self.dashboard.panels[self._panel_index]
        container, content = self._prepare_panel_widget(self._panel_index, panel)
        await holder.mount(container)
        if content is not None:
            await container.mount(content)
        self.app.sub_title = (
            f"{panel.viz} ({self._panel_index + 1}/{len(self.dashboard.panels)})"
        )

    def _prepare_panel_widget(
        self, index: int, panel: PanelConfig
    ) -> tuple[Container, "Widget | Label | None"]:
        from textual.widget import Widget

        container = Container(id=f"panel-{index}-{panel.source}")
        container.border_title = f"{panel.viz} · {panel.source}"
        dataset = self._datasets.get(panel.source)
        if dataset is None:
            return container, Label(f"source {panel.source!r} not loaded")
        try:
            widget: Widget = create_viz(panel.viz)
        except Exception as error:
            return container, Label(f"cannot create widget {panel.viz!r}: {error}")
        mapping = _mapping_from_panel(panel)
        widget.set_data(dataset, mapping)
        return container, widget

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
