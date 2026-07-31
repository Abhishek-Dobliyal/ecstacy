from __future__ import annotations

import sys

import typer

from ecstacy.sources.base import SourceError, SourceSpec, create_source

_EXPORT_FORMATS = ["csv", "json", "markdown"]


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
