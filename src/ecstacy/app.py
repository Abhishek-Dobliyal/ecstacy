from __future__ import annotations

from pathlib import Path

from textual.app import App

from ecstacy.config.loader import load_dashboard
from ecstacy.config.schema import AppConfig, ConfigError, DashboardConfig
from ecstacy.core.dataset import DataSet
from ecstacy.screens.chart import ChartScreen
from ecstacy.screens.dashboard import DashboardScreen
from ecstacy.screens.home import HomeScreen
from ecstacy.screens.splash import SplashScreen
from ecstacy.sources.base import Source, SourceError, SourceSpec, create_source
from ecstacy.theming import register_themes, theme_names
from ecstacy.util.timeparse import parse_duration
from ecstacy.widgets.base import ColumnMapping

_CSS_PATH = str(Path(__file__).parent / "theming" / "ecstacy.tcss")
_PROGRESSIVE_BATCH = 1000


class EcstacyApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(
        self,
        config: AppConfig,
        open_spec: SourceSpec | None = None,
        viz: str = "table",
        mapping: ColumnMapping | None = None,
        dashboard: DashboardConfig | None = None,
        show_splash: bool = True,
    ) -> None:
        super().__init__()
        self.config = config
        self.recents: list[tuple[str, SourceSpec]] = []
        self._open_spec = open_spec
        self._viz = viz
        self._mapping = mapping
        self._dashboard = dashboard
        self._show_splash = show_splash
        self._inflight_opens: dict[tuple[str, str], object] = {}

    def on_mount(self) -> None:
        register_themes(self)
        self.theme = (
            self.config.theme
            if self.config.theme in self.available_themes
            else "ecstacy-dark"
        )
        self.push_screen(HomeScreen())
        if self._open_spec is not None:
            self.open_source(self._open_spec, self._viz, self._mapping)
        elif self._dashboard is not None:
            self.open_dashboard(self._dashboard)
        elif self.config.splash and self._show_splash:
            self.push_screen(SplashScreen())

    def action_toggle_theme(self) -> None:
        names = theme_names()
        index = names.index(self.theme) if self.theme in names else -1
        self.theme = names[(index + 1) % len(names)]
        self.notify(f"theme: {self.theme}")

    def open_path(self, text: str, viz: str = "table") -> None:
        self.open_source(spec_from_target(text), viz)

    def open_dashboard_path(self, path: str) -> None:
        try:
            dashboard = load_dashboard(path)
        except ConfigError as error:
            self.notify(f"cannot read dashboard: {error.message}", severity="error")
            return
        except Exception as error:
            self.notify(f"cannot read dashboard: {error}", severity="error")
            return
        self.open_dashboard(dashboard)

    def open_dashboard(self, dashboard: DashboardConfig) -> None:
        if dashboard.theme and dashboard.theme in self.available_themes:
            self.theme = dashboard.theme
        if not dashboard.sources:
            self.notify("dashboard has no sources", severity="warning")
            return
        self.push_screen(DashboardScreen(dashboard, self.config.max_rows))

    def open_source(
        self, spec: SourceSpec, viz: str = "table", mapping: ColumnMapping | None = None
    ) -> None:
        key = (spec.kind, spec.id)
        if key in self._inflight_opens:
            self.notify(f"already loading {spec.id}")
            return
        self._inflight_opens[key] = self.screen
        self.run_worker(
            lambda: self._fetch_and_show(spec, viz, mapping),
            thread=True,
            exclusive=False,
            exit_on_error=False,
        )

    def _fetch_and_show(
        self, spec: SourceSpec, viz: str, mapping: ColumnMapping | None
    ) -> None:
        from ecstacy.widgets import resolve_viz

        keep_raw = resolve_viz(viz) == "json"
        key = (spec.kind, spec.id)
        try:
            source = create_source(spec)
        except SourceError as error:
            self._deliver(
                self._open_failed,
                key,
                f"failed to load {error.source_id or spec.id}: {error.message}",
            )
            return
        except Exception as error:
            self._deliver(self._open_failed, key, f"failed to load: {error}")
            return

        user_max_rows = getattr(source, "max_rows", None)
        progressive = (
            getattr(source, "supports_progressive", False)
            and (user_max_rows is None or user_max_rows > _PROGRESSIVE_BATCH)
        )

        if progressive:
            source.max_rows = _PROGRESSIVE_BATCH
        try:
            dataset = source.fetch(keep_raw=keep_raw)
        except SourceError as error:
            self._deliver(
                self._open_failed,
                key,
                f"failed to load {error.source_id or spec.id}: {error.message}",
            )
            return
        except Exception as error:
            self._deliver(self._open_failed, key, f"failed to load: {error}")
            return
        self._deliver(self._show_dataset, key, spec, source, dataset, viz, mapping)

        if progressive:
            source.max_rows = user_max_rows
            try:
                full_dataset = source.fetch(keep_raw=keep_raw)
            except Exception as error:
                self._deliver(
                    self._progressive_failed, key, spec, str(error),
                )
                return
            self._deliver(
                self._progressive_update, key, spec, full_dataset,
            )

    def _deliver(self, callback, *args) -> None:
        try:
            self.call_from_thread(callback, *args)
        except RuntimeError:
            pass  # app is shutting down

    def _open_failed(self, key: tuple[str, str], message: str) -> None:
        self._inflight_opens.pop(key, None)
        self.notify(message, severity="error")

    def _progressive_update(
        self, key: tuple[str, str], spec: SourceSpec, dataset: DataSet
    ) -> None:
        screen = self.screen
        if not isinstance(screen, ChartScreen) or screen.spec is not spec:
            return
        screen._on_refresh_data(dataset)

    def _progressive_failed(
        self, key: tuple[str, str], spec: SourceSpec, error: str
    ) -> None:
        screen = self.screen
        if not isinstance(screen, ChartScreen) or screen.spec is not spec:
            return
        self.notify(
            f"showing first {_PROGRESSIVE_BATCH} rows — full load failed: {error}",
            severity="warning",
        )

    def _show_dataset(
        self,
        key: tuple[str, str],
        spec: SourceSpec,
        source: Source,
        dataset: DataSet,
        viz: str,
        mapping: ColumnMapping | None,
    ) -> None:
        origin = self._inflight_opens.pop(key, None)
        # Don't push a chart if the user navigated away while fetching.
        if origin is not None and self.screen is not origin:
            return
        self._remember(source.describe(), spec)
        # AppConfig validates refresh at load time, so this always parses
        refresh_seconds = parse_duration(self.config.refresh)
        self.push_screen(
            ChartScreen(
                dataset,
                viz,
                mapping,
                spec=spec,
                refresh=refresh_seconds,
            )
        )

    def _remember(self, label: str, spec: SourceSpec) -> None:
        self.recents = [(label, spec)] + [r for r in self.recents if r[0] != label]


def spec_from_target(text: str) -> SourceSpec:
    target = text.strip()
    if target.startswith("http://") or target.startswith("https://"):
        return SourceSpec(kind="rest", id=target, params={"url": target})
    path = Path(target).expanduser()
    return SourceSpec(kind="file", id=path.name, params={"path": str(path)})
