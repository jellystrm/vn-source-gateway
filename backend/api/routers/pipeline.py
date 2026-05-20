from __future__ import annotations

import dataclasses
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.infrastructure.activity import ActivityLog
from backend.infrastructure.config import Settings, save_settings
from backend.infrastructure.jobs import JobStore
from backend.api.forms import form_to_config

log = logging.getLogger(__name__)
router = APIRouter()


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
