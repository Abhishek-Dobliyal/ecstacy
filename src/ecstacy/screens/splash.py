from __future__ import annotations

from pyfiglet import Figlet
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from ecstacy import TAGLINE, __version__

_PALETTE = [
    "#3ee06b",
    "#7cdf32",
    "#a5e83a",
    "#c8e832",
    "#e6dc32",
    "#ffcc00",
    "#e6dc32",
    "#c8e832",
    "#a5e83a",
    "#7cdf32",
]

_STAGES = ["core", "sources", "widgets", "themes", "ready"]
_SPINNER = "|/-\\"
_BAR_WIDTH = 42
_TICK = 0.08
_AUTO_DISMISS = 2.6


def _figlet(text: str) -> list[str]:
    for font in ("big", "slant", "ansi_shadow"):
        try:
            rendered = Figlet(font=font).renderText(text)
        except Exception:
            continue
        lines = [line for line in rendered.rstrip("\n").split("\n") if line.strip()]
        if lines:
            return lines
    return [text]


class SplashScreen(Screen):
    BINDINGS = [
        ("escape", "skip", "Skip"),
        ("enter", "skip", "Skip"),
        ("space", "skip", "Skip"),
        ("q", "skip", "Skip"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._lines = _figlet("ECSTACY")
        self._tick = 0
        self._total = max(1, int(_AUTO_DISMISS / _TICK))

    def compose(self):
        with Vertical(id="splash-inner"):
            yield Center(Static("", id="banner", markup=True))
            yield Center(
                Static(
                    f"[italic cyan]{TAGLINE}[/italic cyan]",
                    id="tagline",
                    markup=True,
                )
            )
            yield Center(Static("", id="progress", markup=True))
            yield Center(Static("", id="stages", markup=True))
            yield Center(
                Static(
                    f"[dim]v{__version__}   press any key to continue[/dim]",
                    id="version",
                    markup=True,
                )
            )
        yield Footer()

    def on_mount(self) -> None:
        self._repaint()
        self.set_interval(_TICK, self._advance)
        self.set_timer(_AUTO_DISMISS, self.action_skip)

    def _advance(self) -> None:
        self._tick += 1
        self._repaint()

    def _repaint(self) -> None:
        offset = self._tick // 2
        painted = []
        for idx, line in enumerate(self._lines):
            color = _PALETTE[(idx + offset) % len(_PALETTE)]
            painted.append(f"[{color}]{line}[/{color}]")
        self.query_one("#banner", Static).update("\n".join(painted))

        progress = min(1.0, self._tick / self._total)
        filled = int(progress * _BAR_WIDTH)
        filled_part = "[bright_green]" + "#" * filled + "[/bright_green]"
        empty_part = "[bright_black]" + "-" * (_BAR_WIDTH - filled) + "[/bright_black]"
        pct = int(progress * 100)
        spin = _SPINNER[self._tick % len(_SPINNER)]
        self.query_one("#progress", Static).update(
            f"[yellow]{spin}[/yellow]  {filled_part}{empty_part}  "
            f"[bright_green]{pct:>3}%[/bright_green]"
        )

        stage_idx = min(len(_STAGES) - 1, int(progress * len(_STAGES)))
        cells = []
        for i, name in enumerate(_STAGES):
            if progress >= 1.0 or i < stage_idx:
                cells.append(f"[bright_green]+[/bright_green] {name}")
            elif i == stage_idx:
                cells.append(f"[yellow]{spin}[/yellow] [bold]{name}[/bold]")
            else:
                cells.append(f"[bright_black]. {name}[/bright_black]")
        self.query_one("#stages", Static).update("   ".join(cells))

    def action_skip(self) -> None:
        if self.is_current:
            self.app.pop_screen()
