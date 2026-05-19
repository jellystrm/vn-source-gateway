from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, replace

from vn_source_gateway.application.output_service import OutputService
from vn_source_gateway.application.resolver import SourceResolver
from vn_source_gateway.domain.models import GatewayJob, GatewayRelease, SourceHit
from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.infrastructure.jobs import JobStore


log = logging.getLogger(__name__)


def enqueue_from_url(settings: Settings, url: str, category: str = "vn-source", paused: bool = False) -> GatewayJob:
    release = decode_release_from_url(url)
    now = int(time.time())
    job_id = hashlib.sha1(encode_release(release).encode("utf-8")).hexdigest()[:40]
    store = JobStore(settings.state_path)
    existing = store.get(job_id)
    if existing and existing.status in {"queued", "running", "completed"}:
        return existing
    job = GatewayJob(
        job_id=job_id,
        release=release,
        status="queued",
        progress=0.0,
        created_at=now,
        updated_at=now,
        category=category or "vn-source",
        paused=paused,
    )
    store.upsert(job)
    if not paused:
        threading.Thread(target=process_job, args=(settings, job_id), name=f"vn-source-job-{job_id[:8]}", daemon=True).start()
    return job


def process_job(settings: Settings, job_id: str) -> None:
    store = JobStore(settings.state_path)
    job = store.get(job_id)
    if job is None or job.paused:
        return
    store.update(job_id, status="running", progress=0.05, error=None)
    try:
        hit = resolve_release(settings, job.release)
        if hit is None:
            raise RuntimeError("No HLS source found")
        running = store.update(job_id, progress=0.35, hls_url=hit.hls_url)
        output = OutputService(settings)
        completed = output.write_strm(running, hit) if job.release.output_mode == "strm" else output.download_hls(running, hit)
        store.upsert(replace(completed, updated_at=int(time.time())))
    except Exception as exc:
        log.exception("Job failed: %s", job_id)
        store.update(job_id, status="error", progress=0.0, error=str(exc))


def resolve_release(settings: Settings, release: GatewayRelease) -> SourceHit | None:
    return SourceResolver.from_settings(settings).resolve_release(release)


def encode_release(release: GatewayRelease) -> str:
    raw = json.dumps(asdict(release), separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_release(token: str) -> GatewayRelease:
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return GatewayRelease(**json.loads(raw.decode("utf-8")))


def decode_release_from_url(url: str) -> GatewayRelease:
    marker = "/grab/"
    if marker not in url:
        raise ValueError("Unsupported grab URL")
    token = url.split(marker, 1)[1].split("?", 1)[0].strip("/")
    return decode_release(token)
