from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class Attempt:
    key: str
    path: str
    source: str
    attempted_at: int


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._data: dict[str, Any] = {"attempts": {}}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as handle:
            self._data = json.load(handle)
        self._data.setdefault("attempts", {})

    def recently_attempted(self, key: str, retry_after_seconds: int) -> bool:
        attempt = self._data["attempts"].get(key)
        if not attempt:
            return False
        return int(time.time()) - int(attempt.get("attempted_at", 0)) < retry_after_seconds

    def mark_attempt(self, key: str, path: str, source: str) -> None:
        self._data["attempts"][key] = {
            "path": path,
            "source": source,
            "attempted_at": int(time.time()),
        }
        self.save()

    def save(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)
