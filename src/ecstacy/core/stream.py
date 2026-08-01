from __future__ import annotations

import asyncio
from collections.abc import Callable

from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source


def close_source(source: object) -> None:
    """Close ``source`` if it exposes a ``close()`` method (no-op otherwise)."""
    close = getattr(source, "close", None)
    if callable(close):
        close()


async def consume_stream(
    source: Source,
    screen: object,
    on_data: Callable[[DataSet], None],
    on_error: Callable[[Exception], None],
    keep_raw: bool = False,
    is_active: Callable[[], bool] | None = None,
    on_done: Callable[[], None] | None = None,
) -> None:
    if is_active is None:
        def is_active() -> bool:  # type: ignore[no-redef]
            return getattr(screen, "app", None) is not None and screen.app.screen is screen  # type: ignore[attr-defined]

    def _on_status(msg: str) -> None:
        attached = getattr(screen, "is_attached", False)
        if attached:
            app = getattr(screen, "app", None)
            notifier = getattr(screen, "notify", None)
            if app is not None and notifier is not None:
                app.call_from_thread(notifier, msg, severity="warning")

    stream = source.stream(keep_raw=keep_raw, on_status=_on_status)  # type: ignore[assignment]
    try:
        async for dataset in stream:  # type: ignore[attr-defined]
            if not is_active():
                continue
            on_data(dataset)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        on_error(error)
    finally:
        await stream.aclose()  # type: ignore[attr-defined]
        if on_done is not None:
            on_done()
