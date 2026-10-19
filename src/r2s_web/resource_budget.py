"""Shared limits for native replay work in the web process."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class ReplayResourceBudget:
    """Bound native replay calls across all API services."""

    def __init__(self, max_concurrent: int = 1) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        self.max_concurrent = max_concurrent
        self._slots = threading.BoundedSemaphore(max_concurrent)

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self._slots.acquire()
        try:
            yield
        finally:
            self._slots.release()
