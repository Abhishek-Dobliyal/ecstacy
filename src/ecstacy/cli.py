from __future__ import annotations

import sys
from pathlib import Path

import typer

from ecstacy import __version__
from ecstacy.config.loader import (
    ensure_user_config,
    load_app_config,
    load_dashboard,
    user_config_path,
)
from ecstacy.config.schema import DashboardConfig
from ecstacy.sources.base import SourceError, SourceSpec, create_source
from ecstacy.theming import theme_names
from ecstacy.widgets import viz_names
from ecstacy.widgets.base import ColumnMapping

app = typer.Typer(add_completion=False, help="Ecstacy - beautiful data in your terminal")
config_app = typer.Typer(help="Inspect Ecstacy configuration")
app.add_typer(config_app, name="config")

_EXPORT_FORMATS = ["csv", "json", "markdown"]


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
    ensure_user_config()
    if ctx.invoked_subcommand is None:
        _launch(theme=theme, no_splash=no_splash)


def _max_rows_option() -> typer.Option:
    return typer.Option(None, "--max-rows", help="Maximum rows to load from file/REST")


def _head_option() -> typer.Option:
    return typer.Option(None, "--head", help="Print first N rows to stdout and exit (headless)")


def _tail_option() -> typer.Option:
    return typer.Option(None, "--tail", help="Print last N rows to stdout and exit (headless)")


def _export_option() -> typer.Option:
    return typer.Option(
        None,
        "--export",
        help="Export data to stdout and exit (headless). One of: " + ", ".join(_EXPORT_FORMATS),
    )


def _is_headless(head: int | None, tail: int | None, export: str | None) -> bool:
    return head is not None or tail is not None or export is not None


def _slice_frame(frame, head: int | None, tail: int | None):
    if head is not None:
        return frame.head(head)
    if tail is not None:
        return frame.tail(tail)
    return frame


def _emit(frame, export: str | None) -> None:
    if export is None:
        typer.echo(frame.to_string(index=False))
    elif export == "csv":
        frame.to_csv(sys.stdout, index=False)
    elif export == "json":
        typer.echo(frame.to_json(orient="records", indent=2, date_format="iso"))
    elif export == "markdown":
        typer.echo(frame.to_markdown(index=False))
    else:
        raise typer.BadParameter(
            f"unknown export format {export!r}; expected one of {', '.join(_EXPORT_FORMATS)}"
        )


def _run_headless(
    spec: SourceSpec,
    head: int | None,
    tail: int | None,
    export: str | None,
) -> None:
    try:
        dataset = create_source(spec).fetch()
    except SourceError as error:
        typer.echo(
            f"failed to load {error.source_id or spec.id}: {error.message}",
            err=True,
        )
        raise typer.Exit(code=1) from error
    except Exception as error:
        typer.echo(f"failed to load: {error}", err=True)
        raise typer.Exit(code=1) from error
    frame = _slice_frame(dataset.frame, head, tail)
    _emit(frame, export)
    raise typer.Exit()


@app.command()
def open(  # noqa: A001 - intentional CLI verb
    target: str = typer.Argument(..., help="File path or http(s) URL"),
    chart: str = typer.Option("table", "--chart", help="Initial visualization"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    from ecstacy.app import spec_from_target

    spec = spec_from_target(target)
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(
        open_spec=spec,
        viz=chart,
        theme=theme,
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def file(
    path: str = typer.Argument(..., help="Path to csv/json/parquet/log or - for stdin"),
    chart: str = typer.Option("table", "--chart"),
    x: str | None = typer.Option(None, "--x"),
    y: list[str] | None = typer.Option(None, "--y"),
    category: str | None = typer.Option(None, "--category", help="Category column (bar)"),
    value: str | None = typer.Option(None, "--value", help="Value column (bar/histogram)"),
    fmt: str | None = typer.Option(None, "--format", help="Override file format"),
    sheet: str | None = typer.Option(None, "--sheet", help="Excel sheet name"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
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
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    params = {"url": url, "method": method, "json_path": json_path}
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
        max_rows=max_rows,
        no_splash=no_splash,
    )


@app.command()
def sql(
    query: str = typer.Argument(..., help="SQL query (DuckDB)"),
    db: str = typer.Option(":memory:", "--db", help="DuckDB file or :memory:"),
    chart: str = typer.Option("table", "--chart"),
    theme: str | None = typer.Option(None, "--theme"),
    head: int | None = _head_option(),
    tail: int | None = _tail_option(),
    export: str | None = _export_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    spec = SourceSpec(kind="sql", id="sql", params={"query": query, "db": db})
    if _is_headless(head, tail, export):
        _run_headless(spec, head, tail, export)
        return
    _launch(open_spec=spec, viz=chart, theme=theme, no_splash=no_splash)


@app.command()
def sqlite(
    query: str = typer.Argument(..., help="SQL query (SQLite)"),
    db: str = typer.Option(":memory:", "--db", help="SQLite file or :memory:"),
    chart: str = typer.Option("table", "--chart"),
    max_rows: int | None = _max_rows_option(),
    theme: str | None = typer.Option(None, "--theme"),
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
        open_spec=spec, viz=chart, theme=theme, max_rows=max_rows, no_splash=no_splash
    )


@app.command()
def socket(
    url: str = typer.Argument(..., help="WebSocket URL ws:// or wss://"),
    chart: str = typer.Option("table", "--chart"),
    max_messages: int = typer.Option(100, "--max-messages", help="Max messages to collect"),
    timeout: float = typer.Option(5.0, "--timeout", help="Receive timeout in seconds"),
    theme: str | None = typer.Option(None, "--theme"),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    spec = SourceSpec(
        kind="socket",
        id=url,
        params={"url": url, "max_messages": max_messages, "timeout": timeout},
    )
    _launch(open_spec=spec, viz=chart, theme=theme, no_splash=no_splash)


@app.command()
def dashboard(
    path: str = typer.Argument(..., help="Dashboard YAML file"),
    theme: str | None = typer.Option(None, "--theme"),
    max_rows: int | None = _max_rows_option(),
    no_splash: bool = typer.Option(True, "--no-splash/--splash"),
) -> None:
    _launch(
        dashboard=load_dashboard(path),
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
