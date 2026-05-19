from __future__ import annotations

import threading
import time
from typing import Any

from ..config import Settings
from ..gateway import process_job
from ..jobs import JobStore
from ..models import GatewayJob


def torrents_info(settings: Settings) -> list[dict[str, Any]]:
    jobs = JobStore(settings.state_path).list_jobs()
    return [_job_to_qbit(job) for job in jobs if job.status != "deleted"]


def pause(settings: Settings, hashes: str, paused: bool) -> None:
    store = JobStore(settings.state_path)
    for job_id in _hashes(settings, hashes):
        job = store.get(job_id)
        if job:
            store.update(job_id, paused=paused)
            if not paused and job.status == "queued":
                threading.Thread(target=process_job, args=(settings, job_id), name=f"vn-source-job-{job_id[:8]}", daemon=True).start()


def delete(settings: Settings, hashes: str) -> None:
    store = JobStore(settings.state_path)
    for job_id in _hashes(settings, hashes):
        job = store.get(job_id)
        if job:
            store.update(job_id, status="deleted", progress=0.0)


def preferences(settings: Settings) -> dict[str, Any]:
    return {
        "save_path": settings.download_root,
        "temp_path": settings.download_root,
        "temp_path_enabled": False,
        "scan_dirs": {},
        "export_dir": "",
        "mail_notification_enabled": False,
        "web_ui_domain_list": "*",
        "web_ui_address": settings.ui_host,
        "web_ui_port": settings.ui_port,
        "bypass_local_auth": True,
        "use_https": False,
        "max_connec": -1,
        "max_connec_per_torrent": -1,
        "max_uploads": -1,
        "max_uploads_per_torrent": -1,
        "dl_limit": 0,
        "up_limit": 0,
    }


def build_info() -> dict[str, Any]:
    return {"qt": "6.6.0", "libtorrent": "2.0.9", "boost": "1.83.0", "openssl": "3.0.0", "bitness": 64}


def categories(settings: Settings) -> dict[str, Any]:
    return {"vn-source": {"name": "vn-source", "savePath": settings.download_root}}


def transfer_info() -> dict[str, int]:
    return {"dl_info_speed": 0, "up_info_speed": 0, "dl_info_data": 0, "up_info_data": 0}


def sync_maindata(settings: Settings) -> dict[str, Any]:
    return {"torrents": {job["hash"]: job for job in torrents_info(settings)}}


def _job_to_qbit(job: GatewayJob) -> dict[str, Any]:
    if job.paused and job.status in {"queued", "running"}:
        state = "pausedDL"
        progress = job.progress
    elif job.status == "completed":
        state = "uploading"
        progress = 1.0
    elif job.status == "error":
        state = "error"
        progress = 0.0
    elif job.status == "running":
        state = "downloading"
        progress = max(0.01, job.progress)
    else:
        state = "queuedDL"
        progress = 0.0
    now = int(time.time())
    return {
        "hash": job.job_id,
        "name": _job_name(job),
        "category": job.category,
        "state": state,
        "progress": progress,
        "size": 1024 * 1024 * 1024,
        "completed": int(progress * 1024 * 1024 * 1024),
        "amount_left": 0 if progress >= 1 else int((1 - progress) * 1024 * 1024 * 1024),
        "save_path": job.save_path or "",
        "content_path": job.save_path or "",
        "completion_path": job.save_path or "",
        "ratio": 1,
        "dlspeed": 0,
        "upspeed": 0,
        "eta": 0,
        "priority": 0,
        "added_on": job.created_at,
        "completion_on": job.updated_at if job.status == "completed" else 0,
        "last_activity": job.updated_at,
        "tracker": "vn-source",
        "tags": "strm" if job.release.output_mode == "strm" else "hls-dl",
        "seq_dl": False,
        "f_l_piece_prio": False,
        "seen_complete": job.updated_at if job.status == "completed" else now,
    }


def _job_name(job: GatewayJob) -> str:
    suffix = "STRM" if job.release.output_mode == "strm" else "HLS-DL"
    return f"{job.release.title} [{suffix}]"


def _hashes(settings: Settings, hashes: str) -> list[str]:
    if hashes == "all":
        return [job.job_id for job in JobStore(settings.state_path).list_jobs()]
    return [part.strip() for part in hashes.split("|") if part.strip()]
