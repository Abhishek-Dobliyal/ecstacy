from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from ecstacy.sources.base import SourceError, SourceSpec, create_source
from ecstacy.sources.socket import SocketSource


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


# Reconnection with exponential backoff (P1.2)

@pytest.mark.asyncio
async def test_stream_reconnects_after_drop():
    """After the server closes the connection, the stream reconnects and
    yields another batch."""
    records = [{"v": 1}, {"v": 2}, {"v": 3}]
    url, thread, stop = _start_ws_server(records)
    try:
        source = SocketSource(
            id="ws",
            url=url,
            timeout=1.0,
            max_messages=3,
            reconnect=True,
            reconnect_base=0.01,
            reconnect_max=0.05,
        )
        batches = []
        async for dataset in source.stream():
            batches.append(dataset)
            if len(batches) >= 2:
                break
        assert len(batches) == 2
        assert batches[0].meta.rows == 3
        assert batches[1].meta.rows == 3
    finally:
        stop.set()


@pytest.mark.asyncio
async def test_stream_backoff_is_exponential(monkeypatch):
    """Backoff delay doubles on each failed attempt, capped at reconnect_max."""
    delays: list[float] = []

    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        delays.append(delay)
        if len(delays) >= 4:
            raise asyncio.CancelledError()

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=True,
        reconnect_base=1.0,
        reconnect_max=30.0,
    )
    with pytest.raises(asyncio.CancelledError):
        async for _ in source.stream():
            pass
    assert delays == [1.0, 2.0, 4.0, 8.0]


@pytest.mark.asyncio
async def test_stream_backoff_capped_at_max(monkeypatch):
    """Backoff delay never exceeds reconnect_max."""
    delays: list[float] = []

    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        delays.append(delay)
        if len(delays) >= 6:
            raise asyncio.CancelledError()

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=True,
        reconnect_base=1.0,
        reconnect_max=4.0,
    )
    with pytest.raises(asyncio.CancelledError):
        async for _ in source.stream():
            pass
    # 1, 2, 4, 4(capped), 4(capped), 4(capped)
    assert delays == [1.0, 2.0, 4.0, 4.0, 4.0, 4.0]


@pytest.mark.asyncio
async def test_stream_gives_up_after_bounded_attempts(monkeypatch):
    """With reconnect_attempts set, the stream raises SourceError after
    exhausting retries."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=True,
        reconnect_attempts=2,
        reconnect_base=0.1,
    )
    with pytest.raises(SourceError, match="2 reconnect attempt"):
        async for _ in source.stream():
            pass
    # Two backoff sleeps before giving up on the 3rd failure.
    assert sleeps == [0.1, 0.2]


@pytest.mark.asyncio
async def test_stream_cancellation_does_not_retry(monkeypatch):
    """Cancelling the consumer mid-backoff stops reconnecting immediately."""
    real_sleep = asyncio.sleep
    sleep_count = 0

    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        nonlocal sleep_count
        sleep_count += 1
        # Block long enough for the consumer to cancel us mid-sleep.
        await real_sleep(3600)

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=True,
        reconnect_base=1.0,
    )

    async def _consume_all() -> None:
        async for _ in source.stream():
            pass

    task = asyncio.create_task(_consume_all())
    # Let the first connect fail and the backoff sleep start.
    await real_sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert sleep_count == 1


@pytest.mark.asyncio
async def test_stream_on_status_called(monkeypatch):
    """The on_status callback is invoked with a reconnect message."""
    statuses: list[str] = []

    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=True,
        reconnect_attempts=1,
        reconnect_base=0.1,
    )
    with pytest.raises(SourceError):
        async for _ in source.stream(on_status=statuses.append):
            pass
    assert len(statuses) >= 1
    assert "reconnecting" in statuses[0]


@pytest.mark.asyncio
async def test_stream_no_reconnect_when_disabled(monkeypatch):
    """With reconnect=False, a connection failure raises immediately."""
    async def fake_sleep(delay: float, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("should not sleep/reconnect")

    monkeypatch.setattr("ecstacy.sources.socket.asyncio.sleep", fake_sleep)

    source = SocketSource(
        id="ws",
        url="ws://127.0.0.1:1",
        timeout=0.5,
        reconnect=False,
    )
    with pytest.raises(SourceError):
        async for _ in source.stream():
            pass
