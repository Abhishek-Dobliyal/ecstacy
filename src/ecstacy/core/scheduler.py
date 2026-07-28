from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source

if TYPE_CHECKING:
    from textual.timer import Timer


@dataclass
class Job:
    source: Source
    interval: float
    on_data: Callable[[DataSet], None]
    on_error: Callable[[Exception], None]


class Scheduler:
    def __init__(self, app) -> None:
        self._app = app
        self._timers: list[Timer] = []

    def add(self, job: Job) -> None:
        self._run_once(job)
        if job.interval > 0:
            timer = self._app.set_interval(job.interval, lambda: self._run_once(job))
            self._timers.append(timer)

    def _run_once(self, job: Job) -> None:
        self._app.run_worker(
            lambda: self._fetch(job), thread=True, exclusive=False
        )

    def _fetch(self, job: Job) -> None:
        try:
            dataset = job.source.fetch()
        except Exception as error:  # surfaced to the UI, never crashes the loop
            self._app.call_from_thread(job.on_error, error)
            return
        self._app.call_from_thread(job.on_data, dataset)

    def stop(self) -> None:
        for timer in self._timers:
            timer.stop()
        self._timers.clear()
