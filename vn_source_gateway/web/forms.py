from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qs

import requests

from ..config import Settings

log = logging.getLogger(__name__)


def parse_multipart(body: bytes, content_type: str) -> dict[str, str]:
    marker = "boundary="
    if marker not in content_type:
        return {}
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    delimiter = ("--" + boundary).encode("utf-8")
    form: dict[str, str] = {}
    for part in body.split(delimiter):
        part = part.strip()
        if not part or part == b"--":
            continue
        headers_raw, _, value = part.partition(b"\r\n\r\n")
        if not value:
            continue
        headers = headers_raw.decode("utf-8", errors="ignore")
        name = None
        for header in headers.split("\r\n"):
            if header.lower().startswith("content-disposition:"):
                for segment in header.split(";"):
                    segment = segment.strip()
                    if segment.startswith("name="):
                        name = segment.split("=", 1)[1].strip('"')
        if name:
            form[name] = value.rstrip(b"\r\n-").decode("utf-8", errors="ignore")
    return form


def read_urlencoded(body: bytes) -> dict[str, str]:
    raw = body.decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def run_once(settings: Settings) -> None:
    from ..worker import Worker
    try:
        Worker(settings).run_once()
    except Exception:
        log.exception("Manual worker cycle failed")


def test_connections(settings: Settings) -> str:
    results: list[str] = []
    for name, url, key in [
        ("Radarr", settings.radarr_url, settings.radarr_api_key),
        ("Sonarr", settings.sonarr_url, settings.sonarr_api_key),
    ]:
        if not url or not key:
            results.append(f"{name}: missing URL or API key")
            continue
        try:
            response = requests.get(
                f"{url.rstrip('/')}/api/v3/system/status",
                headers={"X-Api-Key": key},
                timeout=10,
            )
            response.raise_for_status()
            version = response.json().get("version", "unknown")
            results.append(f"{name}: OK, version {version}")
        except Exception as exc:
            results.append(f"{name}: failed, {exc}")
    return " | ".join(results)


def form_to_config(form: dict[str, str], current: Settings) -> dict[str, Any]:
    def integer(name: str, default: int) -> int:
        value = form.get(name, "").strip()
        return default if value == "" else int(value)

    def csv(name: str) -> list[str]:
        return [part.strip() for part in form.get(name, "").split(",") if part.strip()]

    templates_raw = form.get("hls_template_sources", "").strip()
    templates = json.loads(templates_raw) if templates_raw else []
    if not isinstance(templates, list):
        raise ValueError("HLS template sources must be a JSON array")

    return {
        "radarr_url": form.get("radarr_url", "").strip().rstrip("/"),
        "radarr_api_key": form.get("radarr_api_key", ""),
        "sonarr_url": form.get("sonarr_url", "").strip().rstrip("/"),
        "sonarr_api_key": form.get("sonarr_api_key", ""),
        "download_root": form.get("download_root", current.download_root).strip(),
        "movie_strm_root": form.get("movie_strm_root", current.movie_strm_root).strip(),
        "series_strm_root": form.get("series_strm_root", current.series_strm_root).strip(),
        "state_path": form.get("state_path", current.state_path).strip(),
        "ui_enabled": "ui_enabled" in form,
        "ui_host": form.get("ui_host", current.ui_host).strip(),
        "ui_port": integer("ui_port", current.ui_port),
        "poll_interval_seconds": integer("poll_interval_seconds", current.poll_interval_seconds),
        "max_items_per_poll": integer("max_items_per_poll", current.max_items_per_poll),
        "retry_after_seconds": integer("retry_after_seconds", current.retry_after_seconds),
        "movie_enabled": "movie_enabled" in form,
        "series_enabled": "series_enabled" in form,
        "source_order": csv("source_order"),
        "default_output_mode": form.get("default_output_mode", current.default_output_mode).strip() or "strm",
        "expose_both_modes": "expose_both_modes" in form,
        "torznab_api_key": form.get("torznab_api_key", current.torznab_api_key),
        "public_base_url": form.get("public_base_url", current.public_base_url).strip().rstrip("/"),
        "qb_username": form.get("qb_username", current.qb_username),
        "qb_password": form.get("qb_password", current.qb_password),
        "tmdb_api_key": form.get("tmdb_api_key", current.tmdb_api_key),
        "jellyfin_url": form.get("jellyfin_url", current.jellyfin_url).strip().rstrip("/"),
        "jellyfin_api_key": form.get("jellyfin_api_key", current.jellyfin_api_key),
        "jellyfin_scan_after_strm": "jellyfin_scan_after_strm" in form,
        "download_container": form.get("download_container", current.download_container).strip() or "mkv",
        "import_mode": form.get("import_mode", current.import_mode).strip() or "Move",
        "ffmpeg_path": form.get("ffmpeg_path", current.ffmpeg_path).strip() or "ffmpeg",
        "ffmpeg_extra_args": csv("ffmpeg_extra_args"),
        "log_level": form.get("log_level", current.log_level).strip() or "INFO",
        "hls_template_sources": templates,
    }
