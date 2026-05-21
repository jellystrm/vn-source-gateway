from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.infrastructure.activity import ActivityLog
from backend.infrastructure.config import Settings, save_settings, _generate_torznab_key, _ffmpeg_ok
from backend.infrastructure.jobs import JobStore
from backend.api.forms import form_to_config
from backend.application.grab_service import _enrich_with_tmdb
from backend.application.output_service import OutputService
from backend.domain.models import EpisodeWanted, GatewayJob, GatewayRelease, MovieWanted
from backend.infrastructure.downloader import HlsDownloader
from backend.interfaces.indexers.torznab import build_releases, search_response, _release_display_title, _release_grab_payload

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
async def health_check() -> JSONResponse:
    """Probe all external services and return status/latency for each."""
    import requests as req_lib  # already in requirements.txt

    settings = Settings.load()
    services: dict[str, str] = {
        "radarr":  settings.radarr_url  or "",
        "sonarr":  settings.sonarr_url  or "",
        "jellyfin":settings.jellyfin_url or "",
        "kkphim":  "https://phimapi.com",
        "ophim":   "https://ophim1.com/v1/api/home",
        "nguonc":  "https://phim.nguonc.com",
    }

    async def probe(name: str, url: str) -> tuple[str, dict]:
        if not url:
            return name, {"status": "unknown", "latency": None, "url": ""}

        def _sync() -> dict:
            t0 = time.monotonic()
            try:
                r = req_lib.get(url, timeout=8, allow_redirects=True)
                ms = round((time.monotonic() - t0) * 1000)
                status = "ok" if r.status_code < 400 else "warn"
                return {"status": status, "latency": ms, "url": url}
            except Exception as exc:
                return {"status": "error", "latency": None, "url": url,
                        "message": str(exc)[:120]}

        result = await asyncio.to_thread(_sync)
        return name, result

    pairs = await asyncio.gather(*[probe(n, u) for n, u in services.items()])
    return JSONResponse(dict(pairs))


@router.get("/api/check-ffmpeg")
def check_ffmpeg(path: str = "") -> JSONResponse:
    """Check whether the given ffmpeg path (or the configured one) is usable."""
    import subprocess, shutil
    check_path = path.strip() or Settings.load().ffmpeg_path or "ffmpeg"
    resolved = shutil.which(check_path)
    if not resolved:
        return JSONResponse({"ok": False, "path": check_path, "version": None,
                             "hint": "ffmpeg not found. Install: brew install ffmpeg  |  apt install ffmpeg  |  apk add ffmpeg"})
    try:
        out = subprocess.check_output([resolved, "-version"], stderr=subprocess.STDOUT, timeout=5).decode()
        version_line = out.splitlines()[0] if out else resolved
    except Exception as exc:
        return JSONResponse({"ok": False, "path": check_path, "version": None, "hint": str(exc)})
    return JSONResponse({"ok": True, "path": resolved, "version": version_line, "hint": None})


@router.get("/api/output-path-test")
def output_path_test() -> JSONResponse:
    """Dry-run the paths Deceptarr will use for STRM and HLS-DL outputs."""
    settings = Settings.load()
    output = OutputService(settings)
    downloader = HlsDownloader(
        settings.download_root,
        settings.ffmpeg_path,
        settings.ffmpeg_extra_args,
        settings.download_container,
    )

    movie_release = GatewayRelease(
        title="Inception",
        kind="movie",
        output_mode="strm",
        source_name=None,
        query="Inception",
        year=2010,
        tmdb_id=27205,
    )
    episode_release = GatewayRelease(
        title="One Piece",
        kind="episode",
        output_mode="strm",
        source_name=None,
        query="One Piece",
        year=1999,
        tmdb_id=37854,
        season_number=1,
        episode_number=1,
    )
    movie_job = GatewayJob("path-test-movie", movie_release, "queued", 0, 0, 0)
    episode_job = GatewayJob("path-test-episode", episode_release, "queued", 0, 0, 0)
    movie = MovieWanted(0, "Inception", 2010, 27205, None)
    episode = EpisodeWanted(0, 0, "One Piece", "", 1999, 37854, None, None, 1, 1)

    warnings: list[str] = []
    if settings.movie_strm_root.rstrip("/") == settings.series_strm_root.rstrip("/"):
        warnings.append("Movie STRM root and Series STRM root are the same; Radarr/Sonarr scans may mix libraries.")
    if settings.movie_strm_root.rstrip("/") == settings.download_root.rstrip("/"):
        warnings.append("Movie STRM root equals Download root; STRM files and HLS-DL downloads may mix.")
    if settings.series_strm_root.rstrip("/") == settings.download_root.rstrip("/"):
        warnings.append("Series STRM root equals Download root; STRM files and HLS-DL downloads may mix.")

    return JSONResponse({
        "roots": {
            "download_root": settings.download_root,
            "movie_strm_root": settings.movie_strm_root,
            "series_strm_root": settings.series_strm_root,
            "download_container": settings.download_container,
        },
        "paths": [
            {
                "key": "movie_strm",
                "label": "Movie STRM",
                "owner": "Radarr scan",
                "path": output.strm_path(movie_job),
            },
            {
                "key": "series_strm",
                "label": "Series STRM",
                "owner": "Sonarr scan",
                "path": output.strm_path(episode_job),
            },
            {
                "key": "movie_download",
                "label": "Movie HLS-DL",
                "owner": "Radarr import",
                "path": downloader.movie_path(movie),
            },
            {
                "key": "series_download",
                "label": "Series HLS-DL",
                "owner": "Sonarr import",
                "path": downloader.episode_path(episode),
            },
        ],
        "warnings": warnings,
    })


@router.get("/api/config")
def config_get() -> JSONResponse:
    """Return the current resolved settings as a flat JSON object."""
    settings = Settings.load()
    return JSONResponse(settings.to_config_dict())


@router.post("/api/regen-torznab-key")
def regen_torznab_key() -> JSONResponse:
    """Generate a new Torznab API key, persist it, and return it."""
    settings = Settings.load()
    new_key = _generate_torznab_key()
    config_data = settings.to_config_dict()
    config_data["torznab_api_key"] = new_key
    save_settings(config_data, settings.config_path)
    return JSONResponse({"torznab_api_key": new_key})


@router.get("/api/pipeline")
def pipeline() -> JSONResponse:
    """Native job list — richer than /api/jobs (qBit format)."""
    settings = Settings.load()
    store = JobStore(settings.state_path)
    jobs = store.list_jobs()
    result = []
    for job in jobs:
        if job.status == "deleted":
            continue
        release = _enrich_with_tmdb(settings, job.release)
        if release != job.release:
            job = store.update(job.job_id, release=dataclasses.asdict(release))
        display_status = (
            "paused" if job.paused and job.status in {"queued", "running"} else job.status
        )
        result.append({
            "id": job.job_id,
            "title": job.release.title,
            "kind": job.release.kind,
            "media_type": "movie" if job.release.kind == "movie" else "tv",
            "source": job.release.source_name,
            "tmdb_id": job.release.tmdb_id,
            "tvdb_id": job.release.tvdb_id,
            "year": job.release.year,
            "season": job.release.season_number,
            "episode": job.release.episode_number,
            "server_label": getattr(job.release, "server_label", "") or "",
            "query": getattr(job.release, "query", "") or "",
            "output_mode": job.release.output_mode,
            "status": display_status,
            "progress": job.progress,
            "error": job.error,
            "hls_url": job.hls_url,
            "save_path": job.save_path,
            "search_log": job.search_log,
            "source_raw": job.source_raw or {
                "release": dataclasses.asdict(job.release),
                "hls_url": job.hls_url,
                "save_path": job.save_path,
                "search_log": job.search_log,
            },
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        })
    return JSONResponse(result)


@router.get("/api/activity")
def activity() -> JSONResponse:
    """Recent pipeline activity events (searches + grabs)."""
    events = ActivityLog.get().recent(50)
    return JSONResponse([dataclasses.asdict(e) for e in events])


@router.post("/api/activity/delete")
async def activity_delete(request: Request) -> JSONResponse:
    data = await request.json()
    ts = _int_or_none(data.get("ts"))
    title = str(data.get("title") or "")
    if ts is None or not title:
        return JSONResponse({"status": "error", "message": "Missing ts/title"}, status_code=400)
    deleted = ActivityLog.get().delete(ts, title)
    return JSONResponse({"status": "ok", "deleted": deleted})


@router.post("/api/test-grabber")
async def test_grabber(request: Request) -> JSONResponse:
    """Create a fake LinkGrabber search event from test input."""
    data = await request.json()
    settings = Settings.load()

    media_type = str(data.get("media_type", "movie"))
    title = str(data.get("title") or "").strip()
    tmdb_id = _int_or_none(data.get("tmdb_id"))
    year = _int_or_none(data.get("year"))
    season = _int_or_none(data.get("season"))
    episode = _int_or_none(data.get("episode"))

    query: dict[str, list[str]] = {
        "t": ["tvsearch" if media_type == "tv" else "movie"],
        "q": [title],
    }
    if tmdb_id is not None:
        query["tmdbid"] = [str(tmdb_id)]
    if year is not None:
        query["year"] = [str(year)]
    if media_type == "tv":
        if season is not None:
            query["season"] = [str(season)]
        if episode is not None:
            query["ep"] = [str(episode)]

    releases = build_releases(settings, query)
    result_titles = [_release_display_title(r) for r in releases]
    result_grabs = [_release_grab_payload(r) for r in releases]
    display_title = title or (f"TMDB {tmdb_id}" if tmdb_id else "Test query")
    kind = "TV" if media_type == "tv" else "Movie"
    query_url = f"{settings.public_base_url}/torznab/api?test=linkgrabber"

    ActivityLog.get().add(
        kind="search",
        title=f"{kind}: {display_title}",
        detail=f"{len(releases)} fake result(s) - sources: {', '.join(settings.source_order) or 'none'}",
        status="ok" if releases else "error",
        results=result_titles,
        url=query_url,
        grabs=result_grabs,
    )
    return JSONResponse({"status": "ok", "count": len(releases), "results": result_titles})


@router.post("/api/test-indexer")
async def test_indexer(request: Request) -> JSONResponse:
    """Simulate a Radarr/Sonarr Torznab search using the configured API key."""
    data = await request.json()
    settings = Settings.load()

    media_type = str(data.get("media_type", "movie"))
    title = str(data.get("title") or "").strip()
    tmdb_id = _int_or_none(data.get("tmdb_id"))
    year = _int_or_none(data.get("year"))
    season = _int_or_none(data.get("season"))
    episode = _int_or_none(data.get("episode"))

    query: dict[str, list[str]] = {
        "apikey": [settings.torznab_api_key],
        "t": ["tvsearch" if media_type == "tv" else "movie"],
        "q": [title],
        "cat": ["5000,5040" if media_type == "tv" else "2000,2040"],
    }
    if tmdb_id is not None:
        query["tmdbid"] = [str(tmdb_id)]
    if year is not None:
        query["year"] = [str(year)]
    if media_type == "tv":
        if season is not None:
            query["season"] = [str(season)]
        if episode is not None:
            query["ep"] = [str(episode)]

    xml = search_response(settings, query)
    root = ET.fromstring(xml)
    titles = [
        (item.findtext("title") or "").strip()
        for item in root.findall(".//item")
        if (item.findtext("title") or "").strip()
    ]
    flat = {k: v[0] for k, v in query.items() if v and k != "apikey"}
    url = f"{settings.public_base_url}/torznab/api?apikey=***&{urlencode(flat)}"
    return JSONResponse({
        "status": "ok" if titles else "error",
        "count": len(titles),
        "results": titles,
        "url": url,
        "key_required": bool(settings.torznab_api_key),
    })


@router.post("/api/settings")
async def settings_save(request: Request) -> JSONResponse:
    """Save a settings section from a JSON payload.

    Accepts the same field names as the form-based /save endpoint, but with
    JSON types: booleans are True/False (checkbox fields become present/absent).
    """
    data = await request.json()
    current = Settings.load()
    # Convert JSON to form-like dict so form_to_config can handle it unchanged:
    # booleans: True → "on", False → absent (mirroring HTML checkboxes)
    form: dict[str, str] = {}
    for key, val in data.items():
        if isinstance(val, bool):
            if val:
                form[key] = "on"
        elif val is not None:
            form[key] = str(val)
    try:
        config_data = form_to_config(form, current)
        save_settings(config_data, current.config_path)
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        log.exception("settings_save failed")
        return JSONResponse({"status": "error", "message": str(exc)}, status_code=400)


def _int_or_none(value: object) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
