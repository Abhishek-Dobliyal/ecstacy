from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from ecstacy import __version__
from ecstacy.cli._options import (
    _export_option,
    _head_option,
    _max_rows_option,
    _refresh_option,
    _tail_option,
)
from ecstacy.cli.headless import _is_headless, _run_headless
from ecstacy.config.loader import (
    ensure_user_config,
    load_app_config,
    load_dashboard,
    user_config_path,
)
from ecstacy.config.schema import ConfigError, DashboardConfig
from ecstacy.sources.base import SourceSpec
from ecstacy.theming import theme_names
from ecstacy.widgets import viz_names
from ecstacy.widgets.base import ColumnMapping

app = typer.Typer(add_completion=False, help="Ecstacy - beautiful data in your terminal")
config_app = typer.Typer(help="Inspect Ecstacy configuration")
app.add_typer(config_app, name="config")


def _launch(
    open_spec: SourceSpec | None = None,
    viz: str = "table",
    mapping: ColumnMapping | None = None,
    dashboard: DashboardConfig | None = None,
    theme: str | None = None,
    refresh: str | None = None,
    max_rows: int | None = None,
    no_splash: bool = False,
) -> None:
    from ecstacy.app import EcstacyApp

    ensure_user_config()
    config = load_app_config({"theme": theme, "refresh": refresh, "max_rows": max_rows})
    EcstacyApp(
        config,
        open_spec=open_spec,
        viz=viz,
        mapping=mapping,
        dashboard=dashboard,
        show_splash=not no_splash,
    ).run()


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    theme: str | None = typer.Option(None, "--theme", help="Theme name"),
    no_splash: bool = typer.Option(False, "--no-splash", help="Skip the splash screen"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        _launch(theme=theme, no_splash=no_splash)


@app.command()
def open(  # noqa: A001
    target: str = typer.Argument(..., help="File path or http(s) URL"),
    chart: str = typer.Option("table", "--chart", help="Initial visualization"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    refresh: str | None = _refresh_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    from ecstacy.app import spec_from_target

    spec = spec_from_target(target)
    if max_rows is not None:
        spec.params["max_rows"] = max_rows
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(
        open_spec=spec,
        viz=chart,
        theme=theme,
        refresh=refresh,
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def file(
    path: str = typer.Argument(..., help="Path to csv/json/parquet/log or - for stdin"),
    chart: str = typer.Option("table", "--chart"),
    x: str | None = typer.Option(None, "--x"),
    y: list[str] | None = typer.Option(None, "--y"),  # noqa: B008
    category: str | None = typer.Option(None, "--category", help="Category column (bar)"),
    value: str | None = typer.Option(None, "--value", help="Value column (bar/histogram)"),
    fmt: str | None = typer.Option(None, "--format", help="Override file format"),
    sheet: str | None = typer.Option(None, "--sheet", help="Excel sheet name"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    refresh: str | None = _refresh_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    params: dict = {"path": str(Path(path).expanduser()) if path != "-" else "-"}
    if fmt:
        params["fmt"] = fmt
    if sheet:
        params["sheet"] = sheet
    if max_rows is not None:
        params["max_rows"] = max_rows
    spec = SourceSpec(kind="file", id=Path(path).name, params=params)
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    mapping = (
        ColumnMapping(x=x, y=list(y) if y else [], category=category, value=value)
        if (x or y or category or value)
        else None
    )
    _launch(
        open_spec=spec,
        viz=chart,
        mapping=mapping,
        theme=theme,
        refresh=refresh,
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def rest(
    url: str = typer.Argument(..., help="Endpoint URL"),
    json_path: str | None = typer.Option(None, "--json-path", help="Dotted path to records"),
    method: str = typer.Option("GET", "--method"),
    chart: str = typer.Option("table", "--chart"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    refresh: str | None = _refresh_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    params: dict[str, Any] = {"url": url, "method": method, "json_path": json_path}
    if max_rows is not None:
        params["max_rows"] = max_rows
    spec = SourceSpec(kind="rest", id=url, params=params)
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(
        open_spec=spec,
        viz=chart,
        theme=theme,
        refresh=refresh,
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def sql(
    query: str = typer.Argument(..., help="SQL query (DuckDB)"),
    db: str = typer.Option(":memory:", "--db", help="DuckDB file or :memory:"),
    chart: str = typer.Option("table", "--chart"),
    max_rows: int | None = _max_rows_option(),
    theme: str | None = typer.Option(None, "--theme"),
    refresh: str | None = _refresh_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    spec = SourceSpec(kind="sql", id="sql", params={"query": query, "db": db})
    if max_rows is not None:
        spec.params["max_rows"] = max_rows
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(open_spec=spec, viz=chart, theme=theme, refresh=refresh, no_splash=no_splash)


@app.command()
def sqlite(
    query: str = typer.Argument(..., help="SQL query (SQLite)"),
    db: str = typer.Option(":memory:", "--db", help="SQLite file or :memory:"),
    chart: str = typer.Option("table", "--chart"),
    max_rows: int | None = _max_rows_option(),
    theme: str | None = typer.Option(None, "--theme"),
    refresh: str | None = _refresh_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    spec = SourceSpec(
        kind="sqlite", id="sqlite", params={"query": query, "db": db}
    )
    if max_rows is not None:
        spec.params["max_rows"] = max_rows
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(
        open_spec=spec, viz=chart, theme=theme, refresh=refresh,
        max_rows=max_rows, no_splash=no_splash,
    )


@app.command()
def socket(
    url: str = typer.Argument(..., help="WebSocket URL ws:// or wss://"),
    chart: str = typer.Option("table", "--chart"),
    max_messages: int = typer.Option(100, "--max-messages", help="Max messages to collect"),
    timeout: float = typer.Option(5.0, "--timeout", help="Receive timeout in seconds"),
    theme: str | None = typer.Option(None, "--theme"),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    spec = SourceSpec(
        kind="socket",
        id=url,
        params={"url": url, "max_messages": max_messages, "timeout": timeout},
    )
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(open_spec=spec, viz=chart, theme=theme, no_splash=no_splash)


@app.command()
def dashboard(
    path: str = typer.Argument(..., help="Dashboard YAML file"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    try:
        config = load_dashboard(path)
    except ConfigError as error:
        typer.echo(f"cannot load dashboard: {error.message}", err=True)
        raise typer.Exit(1) from error
    _launch(
        dashboard=config,
        theme=theme,
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def themes() -> None:
    for name in theme_names():
        typer.echo(name)


@app.command("charts")
def charts() -> None:
    for name in viz_names():
        typer.echo(name)


@config_app.command("path")
def config_path() -> None:
    typer.echo(str(user_config_path()))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
