"""In-memory activity log: ring buffer of recent pipeline events."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

_MAX = 100


@dataclass
class ActivityEvent:
    ts: int
    kind: str          # "search" | "grab" | "job"
    title: str
    detail: str = ""
    status: str = ""   # "ok" | "error" | ""
    ref: str = ""      # job_id for correlation
    results: list = field(default_factory=list)  # release titles for search events


class ActivityLog:
    _instance: ActivityLog | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._events: list[ActivityEvent] = []
        self._mu = threading.Lock()

    @classmethod
    def get(cls) -> ActivityLog:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ActivityLog()
        return cls._instance

    def add(self, kind: str, title: str, detail: str = "", status: str = "", ref: str = "",
            results: list | None = None) -> None:
        event = ActivityEvent(ts=int(time.time()), kind=kind, title=title,
                              detail=detail, status=status, ref=ref,
                              results=results or [])
        with self._mu:
            self._events.append(event)
            if len(self._events) > _MAX:
                self._events = self._events[-_MAX:]

    def recent(self, n: int = 50) -> list[ActivityEvent]:
        with self._mu:
            return list(reversed(self._events[-n:]))
