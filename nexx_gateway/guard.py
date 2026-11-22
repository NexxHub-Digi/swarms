"""Process-local admission control (not a distributed billing or quota system)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from .config import Project


class TooManyRequests(Exception):
    pass


class TooManyConcurrentRuns(Exception):
    pass


class ExecutionGuard:
    def __init__(self, max_concurrent_runs: int, clock=None):
        self._max_concurrent_runs = max_concurrent_runs
        self._clock = clock or time.monotonic
        self._lock = Lock()
        self._active = 0
        self._recent: dict[str, deque[float]] = defaultdict(deque)

    def acquire(self, project: Project) -> None:
        now = self._clock()
        with self._lock:
            recent = self._recent[project.identifier]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= project.requests_per_minute:
                raise TooManyRequests()
            if self._active >= self._max_concurrent_runs:
                raise TooManyConcurrentRuns()
            self._active += 1
            recent.append(now)

    def release(self) -> None:
        with self._lock:
            self._active -= 1
