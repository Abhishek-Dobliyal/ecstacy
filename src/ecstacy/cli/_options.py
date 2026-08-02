from __future__ import annotations

from typing import Any

import typer


def _max_rows_option() -> Any:
    return typer.Option(None, "--max-rows", help="Maximum rows to load (file/REST/SQL sources)")


def _refresh_option() -> Any:
    return typer.Option(None, "--refresh", help="Auto-refresh interval (e.g. 5s, 1m)")


def _head_option() -> Any:
    return typer.Option(None, "--head", help="Print first N rows to stdout and exit (headless)")


def _tail_option() -> Any:
    return typer.Option(None, "--tail", help="Print last N rows to stdout and exit (headless)")


def _export_option() -> Any:
    return typer.Option(
        None,
        "--export",
        help="Export data to stdout and exit (headless). One of: csv, json, markdown",
    )


def _theme_option() -> Any:
    return typer.Option(None, "--theme", help="Theme name")


def _no_splash_option() -> Any:
    return typer.Option(True, "--no-splash/--splash", help="Skip the splash screen")
