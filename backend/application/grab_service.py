from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, replace

from backend.adapters.tmdb import TmdbClient
from backend.application.output_service import OutputService
from backend.domain.models import EpisodeWanted, GatewayJob, GatewayRelease, MovieWanted, SourceHit
from backend.infrastructure.activity import ActivityLog
from backend.infrastructure.config import Settings
from backend.infrastructure.jobs import JobStore
from backend.sources import Source, build_sources

log = logging.getLogger(__name__)


def enqueue_from_url(settings: Settings, url: str, category: str = "deceptarr", paused: bool = False) -> GatewayJob:
    release = decode_release_from_url(url)
    category = _job_category_for_release(release, category)
    now = int(time.time())
    job_id = hashlib.sha1(encode_release(release).encode("utf-8")).hexdigest()[:40]
    store = JobStore(settings.state_path)
    existing = store.get(job_id)
    if existing and existing.status in {"queued", "running"}:
        return existing
    job = GatewayJob(
        job_id=job_id,
        release=release,
        status="queued",
        progress=0.0,
        created_at=now,
        updated_at=now,
        category=category or "deceptarr",
        paused=paused,
    )
    store.upsert(job)
    if not paused:
        threading.Thread(target=process_job, args=(settings, job_id), name=f"deceptarr-job-{job_id[:8]}", daemon=True).start()
    return job


def _job_category_for_release(release: GatewayRelease, requested: str = "") -> str:
    category = (requested or "").strip()
    if category and category != "deceptarr":
        return category
    return "radarr" if release.kind == "movie" else "sonarr"


def process_job(settings: Settings, job_id: str) -> None:
    store = JobStore(settings.state_path)
    job = store.get(job_id)
    if job is None or job.paused:
        return
    release = _enrich_with_tmdb(settings, job.release)
    if release != job.release:
        job = store.update(job_id, release=asdict(release))
    store.update(job_id, status="running", progress=0.05, error=None)
    title = release.title
    try:
        hit, search_log = resolve_release(settings, job.release)
        if hit is None:
            store.update(job_id, search_log=search_log)
            raise RuntimeError("No HLS source found")
        running = store.update(
            job_id,
            progress=0.35,
            hls_url=hit.hls_url,
            search_log=search_log,
            source_raw={
                "source": hit.source_name,
                "server": hit.server_name,
                "item": hit.item_name,
                "hls_url": hit.hls_url,
                "headers": hit.headers,
                "raw": hit.raw_data,
            },
        )
        ActivityLog.get().add("job", title, f"Resolved via {hit.source_name}", "ok", ref=job_id)
        output = OutputService(settings)
        completed = output.write_strm(running, hit) if job.release.output_mode == "strm" else output.download_hls(running, hit)
        store.upsert(replace(completed, updated_at=int(time.time())))
        ActivityLog.get().add("job", title, f"Done — {completed.save_path or ''}", "ok", ref=job_id)
    except Exception as exc:
        log.exception("Job failed: %s", job_id)
        store.update(job_id, status="error", progress=0.0, error=str(exc))
        ActivityLog.get().add("job", title, str(exc), "error", ref=job_id)


def resolve_release(settings: Settings, release: GatewayRelease) -> tuple[SourceHit | None, list[str]]:
    release = _enrich_with_tmdb(settings, release)
    sources = build_sources(tmdb_api_key=settings.tmdb_api_key)
    ordered = [release.source_name] if release.source_name else settings.source_order
    all_log: list[str] = []
    for source_name in ordered:
        if not source_name:
            continue
        source = sources.get(source_name)
        if not source:
            log.warning("Unknown or unconfigured source: %s", source_name)
            all_log.append(f"[{source_name}] not configured")
            continue
        hit = _resolve_with_source(source, release)
        src_log = getattr(source, "_last_log", [])
        for line in src_log:
            all_log.append(f"[{source_name}] {line}")
        if hit:
            return hit, all_log
    return None, all_log


def _enrich_with_tmdb(settings: Settings, release: GatewayRelease) -> GatewayRelease:
    """Fill in missing tmdb_id/title/year via TMDB API lookup."""
    tmdb = TmdbClient(settings.tmdb_api_key)
    if not tmdb.enabled:
        return release

    # Step 1: resolve tmdb_id if not present
    tmdb_id = release.tmdb_id
    if not tmdb_id:
        if release.kind == "episode" and release.tvdb_id:
            tmdb_id = tmdb.tmdb_id_for_tvdb(release.tvdb_id)
            if tmdb_id:
                log.debug("TMDB lookup: tvdb=%s → tmdb=%s", release.tvdb_id, tmdb_id)
        if tmdb_id is None and release.imdb_id:
            kind = "movie" if release.kind == "movie" else "tv"
            tmdb_id = tmdb.tmdb_id_for_imdb(release.imdb_id, kind)
            if tmdb_id:
                log.debug("TMDB lookup: imdb=%s → tmdb=%s", release.imdb_id, tmdb_id)

    # Step 2: enrich title + year from TMDB when title is a placeholder (no real name)
    updates: dict = {}
    if tmdb_id and tmdb_id != release.tmdb_id:
        updates["tmdb_id"] = tmdb_id
    if tmdb_id and _is_placeholder_title(release.title):
        if release.kind == "movie":
            info = tmdb.get_movie_title(tmdb_id)
            if info:
                real_title, real_year = info
                updates["title"] = real_title
                if _is_placeholder_title(release.query):
                    updates["query"] = real_title
                if real_year and not release.year:
                    updates["year"] = real_year
                log.debug("TMDB movie title: tmdb=%s → %r (%s)", tmdb_id, real_title, real_year)
        else:
            series = tmdb.get_series_info(tmdb_id)
            if series.title:
                updates["title"] = series.title
                if _is_placeholder_title(release.query):
                    updates["query"] = series.title
                if series.series_year and not release.year:
                    updates["year"] = series.series_year
                log.debug("TMDB series title: tmdb=%s → %r (%s)", tmdb_id, series.title, series.series_year)

    return replace(release, **updates) if updates else release


def _is_placeholder_title(title: str) -> bool:
    """True when the title is a generated placeholder rather than a real media name."""
    import re
    return not title.strip() or bool(re.match(
        r"^(TMDB|TVDB|VN Source|Untitled|Sonarr series|Radarr movie)\s*\d*$",
        title.strip(), re.I,
    ))


def encode_release(release: GatewayRelease) -> str:
    raw = json.dumps(asdict(release), separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_release(token: str) -> GatewayRelease:
    padded = token + "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    data = json.loads(raw.decode("utf-8"))
    # Backward compat: tokens encoded before server_label was added
    data.setdefault("server_label", "")
    data.setdefault("container", None)
    return GatewayRelease(**data)


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
                server_label=release.server_label,
            )
        )
    # Season pack (episode_number=None): not supported as a single grab — skip
    if release.episode_number is None:
        return None
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
            episode_number=release.episode_number,
            server_label=release.server_label,
        )
    )
