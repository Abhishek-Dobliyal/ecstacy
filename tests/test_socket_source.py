from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from ecstacy.sources.base import SourceError, SourceSpec, create_source


def _start_ws_server(records: list[Any]) -> tuple[str, threading.Thread, Any]:
    from websockets.asyncio.server import serve

    stop = asyncio.Event()
    server_holder: dict[str, Any] = {}

    async def handler(websocket):
        for record in records:
            import orjson

            await websocket.send(orjson.dumps(record))
        await websocket.close()

    async def _serve():
        async with serve(handler, "127.0.0.1", 0) as server:
            socks = server.sockets
            port = socks[0].getsockname()[1]
            server_holder["port"] = port
            server_holder["ready"].set()
            await stop.wait()

    server_holder["ready"] = threading.Event()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_serve())
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    server_holder["ready"].wait(timeout=5)
    port = server_holder["port"]

    def stop_server():
        # set stop via a fresh loop
        import asyncio as _a

        loop_for_stop = _a.new_event_loop()

        async def _set():
            stop.set()

        try:
            loop_for_stop.run_until_complete(_set())
        finally:
            loop_for_stop.close()

    url = f"ws://127.0.0.1:{port}"
    return url, thread, stop


def test_socket_source_fetches_records():
    records = [
        {"date": "2024-01-01", "region": "us", "value": 10.0},
        {"date": "2024-01-02", "region": "eu", "value": 15.0},
    ]
    url, thread, stop = _start_ws_server(records)
    try:
        spec = SourceSpec(
            kind="socket", id="ws", params={"url": url, "timeout": 3.0}
        )
        dataset = create_source(spec).fetch()
        assert dataset.meta.rows == 2
        assert "region" in dataset.frame.columns
    finally:
        stop.set()


def test_socket_source_no_messages_raises():
    url, thread, stop = _start_ws_server([])
    try:
        spec = SourceSpec(
            kind="socket", id="ws", params={"url": url, "timeout": 1.0}
        )
        with pytest.raises(SourceError):
            create_source(spec).fetch()
    finally:
        stop.set()


def test_socket_source_invalid_url_raises():
    spec = SourceSpec(
        kind="socket",
        id="ws",
        params={"url": "ws://127.0.0.1:1", "timeout": 1.0},
    )
    with pytest.raises(SourceError):
        create_source(spec).fetch()
