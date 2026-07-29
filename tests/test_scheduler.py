from __future__ import annotations

from unittest import mock

import pandas as pd

from ecstacy.core.dataset import DataSet
from ecstacy.core.scheduler import Job, Scheduler


class _FakeApp:
    def __init__(self):
        self.workers = []
        self.timers = []

    def run_worker(self, fn, **kwargs):
        self.workers.append(fn)
        return mock.Mock()

    def set_interval(self, *args, **kwargs):
        timer = mock.Mock()
        self.timers.append(timer)
        return timer

    def call_from_thread(self, callback, *args):
        callback(*args)


def _dataset() -> DataSet:
    return DataSet.from_dataframe(pd.DataFrame({"a": [1]}), source_id="s", kind="test")


def _job(**overrides) -> Job:
    kwargs = {
        "source": mock.Mock(),
        "interval": 0,
        "on_data": lambda d: None,
        "on_error": lambda e: None,
    }
    kwargs.update(overrides)
    return Job(**kwargs)


def test_run_now_skips_while_in_flight():
    app = _FakeApp()
    scheduler = Scheduler(app)
    job = _job()
    job.in_flight = True
    scheduler.run_now(job)
    assert app.workers == []


def test_fetch_delivers_data_and_clears_in_flight():
    app = _FakeApp()
    scheduler = Scheduler(app)
    ds = _dataset()
    source = mock.Mock()
    source.fetch.return_value = ds
    received = []
    job = _job(source=source, on_data=received.append)
    scheduler.run_now(job)
    app.workers[0]()
    assert received == [ds]
    assert job.in_flight is False


def test_fetch_delivers_errors_and_clears_in_flight():
    app = _FakeApp()
    scheduler = Scheduler(app)
    source = mock.Mock()
    source.fetch.side_effect = ValueError("boom")
    errors = []
    job = _job(source=source, on_error=errors.append)
    scheduler.run_now(job)
    app.workers[0]()
    assert len(errors) == 1
    assert job.in_flight is False


def test_add_with_run_immediately_false_does_not_fetch():
    app = _FakeApp()
    scheduler = Scheduler(app)
    scheduler.add(_job(interval=5), run_immediately=False)
    assert app.workers == []
    assert len(app.timers) == 1


def test_stop_cancels_workers_and_blocks_run_now():
    app = _FakeApp()
    scheduler = Scheduler(app)
    scheduler.run_now(_job())
    scheduler.stop()
    scheduler.run_now(_job())
    assert len(app.workers) == 1  # no new worker after stop


def test_run_now_skips_when_is_active_returns_false():
    app = _FakeApp()
    scheduler = Scheduler(app, is_active=lambda: False)
    scheduler.run_now(_job())
    assert app.workers == []


def test_run_now_runs_when_is_active_returns_true():
    app = _FakeApp()
    scheduler = Scheduler(app, is_active=lambda: True)
    scheduler.run_now(_job())
    assert len(app.workers) == 1
