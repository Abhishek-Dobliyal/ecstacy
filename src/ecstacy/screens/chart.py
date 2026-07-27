from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header

from ecstacy.core.dataset import DataSet
from ecstacy.widgets import create_viz, viz_names
from ecstacy.widgets.base import ColumnMapping


class ChartScreen(Screen):
    BINDINGS = [
        ("right", "next_viz", "Next viz"),
        ("n", "next_viz", "Next viz"),
        ("left", "prev_viz", "Prev viz"),
        ("p", "prev_viz", "Prev viz"),
        ("t", "app.toggle_theme", "Theme"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(
        self,
        dataset: DataSet,
        viz_name: str = "table",
        mapping: ColumnMapping | None = None,
    ) -> None:
        super().__init__()
        self.dataset = dataset
        self.mapping = mapping
        self.names = viz_names()
        self.index = self.names.index(viz_name) if viz_name in self.names else 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(id="viz-holder")
        yield Footer()

    async def on_mount(self) -> None:
        await self._render_current()

    async def _render_current(self) -> None:
        holder = self.query_one("#viz-holder", Container)
        await holder.remove_children()
        name = self.names[self.index]
        widget = create_viz(name)
        await holder.mount(widget)
        widget.set_data(self.dataset, self.mapping)
        holder.border_title = f"{self.index + 1} {name}  |  {self.dataset.meta.source_id}"
        holder.border_subtitle = (
            f"{self.dataset.meta.rows} rows   n next  p prev  esc back"
        )
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
