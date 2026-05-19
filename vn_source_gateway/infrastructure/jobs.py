from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Any

from vn_source_gateway.domain.models import GatewayJob, GatewayRelease


class JobStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._data: dict[str, Any] = {"jobs": {}}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            self._data = loaded
        self._data.setdefault("jobs", {})

    def list_jobs(self) -> list[GatewayJob]:
        return [self._decode_job(item) for item in self._data.get("jobs", {}).values()]

    def get(self, job_id: str) -> GatewayJob | None:
        raw = self._data.get("jobs", {}).get(job_id)
        return self._decode_job(raw) if raw else None

    def upsert(self, job: GatewayJob) -> None:
        self._data.setdefault("jobs", {})[job.job_id] = asdict(job)
        self.save()

    def update(self, job_id: str, **changes: Any) -> GatewayJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        data = asdict(job)
        data.update(changes)
        data["updated_at"] = int(time.time())
        updated = self._decode_job(data)
        self.upsert(updated)
        return updated

    def save(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, self.path)

    @staticmethod
    def _decode_job(raw: dict[str, Any]) -> GatewayJob:
        release = GatewayRelease(**raw["release"])
        return GatewayJob(
            job_id=raw["job_id"],
            release=release,
            status=raw.get("status", "queued"),
            progress=float(raw.get("progress", 0)),
            created_at=int(raw.get("created_at", time.time())),
            updated_at=int(raw.get("updated_at", time.time())),
            category=raw.get("category", "vn-source"),
            paused=bool(raw.get("paused", False)),
            save_path=raw.get("save_path"),
            hls_url=raw.get("hls_url"),
            error=raw.get("error"),
        )
