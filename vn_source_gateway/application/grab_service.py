from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, replace

from vn_source_gateway.adapters.tmdb import TmdbClient
from vn_source_gateway.application.output_service import OutputService
from vn_source_gateway.domain.models import EpisodeWanted, GatewayJob, GatewayRelease, MovieWanted, SourceHit
from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.infrastructure.jobs import JobStore
from vn_source_gateway.sources import Source, build_sources

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
    release = _enrich_with_tmdb(settings, release)
    sources = build_sources(settings.hls_template_sources, tmdb_api_key=settings.tmdb_api_key)
    ordered = [release.source_name] if release.source_name else settings.source_order
    for source_name in ordered:
        if not source_name:
            continue
        source = sources.get(source_name)
        if not source:
            log.warning("Unknown or unconfigured source: %s", source_name)
            continue
        hit = _resolve_with_source(source, release)
        if hit:
            return hit
    return None


def _enrich_with_tmdb(settings: Settings, release: GatewayRelease) -> GatewayRelease:
    """Fill in missing tmdb_id via TMDB API lookup when we only have tvdb_id or imdb_id."""
    if release.tmdb_id:
        return release
    tmdb = TmdbClient(settings.tmdb_api_key)
    if not tmdb.enabled:
        return release
    tmdb_id: int | None = None
    if release.kind == "episode" and release.tvdb_id:
        tmdb_id = tmdb.tmdb_id_for_tvdb(release.tvdb_id)
        if tmdb_id:
            log.debug("TMDB lookup: tvdb=%s → tmdb=%s", release.tvdb_id, tmdb_id)
    if tmdb_id is None and release.imdb_id:
        kind = "movie" if release.kind == "movie" else "tv"
        tmdb_id = tmdb.tmdb_id_for_imdb(release.imdb_id, kind)
        if tmdb_id:
            log.debug("TMDB lookup: imdb=%s → tmdb=%s", release.imdb_id, tmdb_id)
    if tmdb_id is None:
        return release
    return replace(release, tmdb_id=tmdb_id)


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


def _resolve_with_source(source: Source, release: GatewayRelease) -> SourceHit | None:
    if release.kind == "movie":
        return source.resolve_movie(
            MovieWanted(
                radarr_id=0,
                title=release.query or release.title,
                year=release.year,
                tmdb_id=release.tmdb_id,
                imdb_id=release.imdb_id,
            )
        )
    return source.resolve_episode(
        EpisodeWanted(
            sonarr_episode_id=0,
            series_id=0,
            series_title=release.query or release.title,
            episode_title="",
            year=release.year,
            tmdb_id=release.tmdb_id,
            tvdb_id=release.tvdb_id,
            imdb_id=release.imdb_id,
            season_number=release.season_number or 1,
            episode_number=release.episode_number or 1,
        )
    )
