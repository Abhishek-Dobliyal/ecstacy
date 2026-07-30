from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ecstacy.core.dataset import DataSet
from ecstacy.sources.base import Source

if TYPE_CHECKING:
    from textual.timer import Timer
    from textual.worker import Worker


@dataclass
class Job:
    source: Source
    interval: float
    on_data: Callable[[DataSet], None]
    on_error: Callable[[Exception], None]
    keep_raw: bool = False
    in_flight: bool = field(default=False, init=False)


class Scheduler:
    """Runs source fetches on pool threads and delivers results to the UI.

    A job never overlaps with itself: ticks that arrive while the previous
    fetch is still running are skipped, so results can't arrive out of order
    and slow sources don't pile up threads.
    """

    def __init__(self, app, is_active: Callable[[], bool] | None = None) -> None:
        self._app = app
        self._is_active = is_active
        self._timers: list[Timer] = []
        self._workers: list[Worker] = []
        self._stopped = False

    def add(self, job: Job, run_immediately: bool = True) -> None:
        if run_immediately:
            self.run_now(job)
        if job.interval > 0:
            timer = self._app.set_interval(job.interval, lambda: self.run_now(job))
            self._timers.append(timer)

    def run_now(self, job: Job, force: bool = False) -> None:
        """Fetch a job now, unless its previous fetch is still running or the
        owning screen isn't on top (e.g. a modal is open)."""
        if self._stopped or job.in_flight:
            return
        if self._is_active is not None and not self._is_active():
            return
        job.in_flight = True
        # Prune finished workers so the list doesn't grow unbounded over a
        # long refresh session.
        self._workers = [w for w in self._workers if not w.is_finished]
        worker = self._app.run_worker(
            lambda: self._fetch(job, force=force),
            thread=True,
            exclusive=False,
            exit_on_error=False,
        )
        self._workers.append(worker)

    def _fetch(self, job: Job, force: bool = False) -> None:
        try:
            dataset = job.source.fetch(keep_raw=job.keep_raw, force=force)
        except Exception as error:  # surfaced to the UI, never crashes the loop
            self._deliver(job.on_error, error)
        else:
            self._deliver(job.on_data, dataset)
        finally:
            job.in_flight = False

    def _deliver(self, callback: Callable, payload: object) -> None:
        try:
            self._app.call_from_thread(callback, payload)
        except RuntimeError:
            # app is shutting down; drop the result
            pass

    def stop(self) -> None:
        self._stopped = True
        for timer in self._timers:
            timer.stop()
        self._timers.clear()
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
