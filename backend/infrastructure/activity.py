"""Activity log: ring buffer of recent pipeline events, persisted to disk."""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field

_MAX = 200  # keep last 200 events on disk


@dataclass
class ActivityEvent:
    ts: int
    kind: str          # "search" | "grab" | "job"
    title: str
    detail: str = ""
    status: str = ""   # "ok" | "error" | ""
    ref: str = ""      # job_id for correlation
    results: list = field(default_factory=list)  # release titles for search events
    url: str = ""      # full torznab query URL for search events
    grabs: list = field(default_factory=list)    # [{title, token}] per release — for manual download


class ActivityLog:
    _instance: ActivityLog | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._events: list[ActivityEvent] = []
        self._path: str | None = None
        self._mu = threading.Lock()

    @classmethod
    def get(cls) -> ActivityLog:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ActivityLog()
        return cls._instance

    @classmethod
    def init(cls, path: str) -> None:
        """Set the persistence path and load existing events from disk.

        Call once at startup before any other code uses the log.
        """
        instance = cls.get()
        with instance._mu:
            instance._path = path
            instance._events = _load(path)

    def add(self, kind: str, title: str, detail: str = "", status: str = "", ref: str = "",
            results: list | None = None, url: str = "", grabs: list | None = None) -> None:
        event = ActivityEvent(ts=int(time.time()), kind=kind, title=title,
                              detail=detail, status=status, ref=ref,
                              results=results or [], url=url, grabs=grabs or [])
        with self._mu:
            self._events.append(event)
            if len(self._events) > _MAX:
                self._events = self._events[-_MAX:]
            if self._path:
                _save(self._path, self._events)

    def recent(self, n: int = 50) -> list[ActivityEvent]:
        with self._mu:
            return list(reversed(self._events[-n:]))

    def delete(self, ts: int, title: str) -> bool:
        with self._mu:
            before = len(self._events)
            self._events = [e for e in self._events if not (e.ts == ts and e.title == title)]
            changed = len(self._events) != before
            if changed and self._path:
                _save(self._path, self._events)
            return changed


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------

def _load(path: str) -> list[ActivityEvent]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        events = []
        for item in raw:
            item.setdefault("results", [])
            item.setdefault("url", "")
            item.setdefault("grabs", [])
            events.append(ActivityEvent(**{k: item[k] for k in ActivityEvent.__dataclass_fields__ if k in item}))
        return events
    except Exception:
        return []


def _save(path: str, events: list[ActivityEvent]) -> None:
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([asdict(e) for e in events], fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass  # never crash the caller over a log write failure
