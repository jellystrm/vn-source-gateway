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
from backend.infrastructure.config import Settings, save_settings, _generate_torznab_key
from backend.infrastructure.jobs import JobStore
from backend.api.forms import form_to_config
from backend.application.grab_service import encode_release
from backend.interfaces.indexers.torznab import build_releases, search_response, _release_display_title

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
    jobs = JobStore(settings.state_path).list_jobs()
    result = []
    for job in jobs:
        if job.status == "deleted":
            continue
        display_status = (
            "paused" if job.paused and job.status in {"queued", "running"} else job.status
        )
        result.append({
            "id": job.job_id,
            "title": job.release.title,
            "kind": job.release.kind,
            "season": job.release.season_number,
            "episode": job.release.episode_number,
            "output_mode": job.release.output_mode,
            "status": display_status,
            "progress": job.progress,
            "error": job.error,
            "hls_url": job.hls_url,
            "save_path": job.save_path,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        })
    return JSONResponse(result)


@router.get("/api/activity")
def activity() -> JSONResponse:
    """Recent pipeline activity events (searches + grabs)."""
    events = ActivityLog.get().recent(50)
    return JSONResponse([dataclasses.asdict(e) for e in events])


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
        query["season"] = [str(season or 1)]
        query["ep"] = [str(episode or 1)]

    releases = build_releases(settings, query)
    result_titles = [_release_display_title(r) for r in releases]
    result_grabs = [
        {"title": _release_display_title(r), "token": encode_release(r)}
        for r in releases
    ]
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
        query["season"] = [str(season or 1)]
        query["ep"] = [str(episode or 1)]

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
