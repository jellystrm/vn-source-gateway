from __future__ import annotations

import html
import json

from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.interfaces.download_clients import qbittorrent
from .cards import (
    _attr,
    download_tasks_card,
    settings_card,
    sources_card,
)
from .styles import CSS

_NAV = [
    ("dashboard", "&#9654;", "Dashboard"),
    ("sources", "&#9654;", "Sources"),
    ("settings", "&#9654;", "Settings"),
]

SECTION_ALIASES = {
    "download-tasks": "dashboard",
    "jobs": "dashboard",
    "media-managers": "settings",
    "radarr": "settings",
    "sonarr": "settings",
    "worker": "settings",
    "indexer": "settings",
    "downloader": "settings",
    "jellyfin": "settings",
}
ALL_SECTIONS = {s for s, _, _ in _NAV} | set(SECTION_ALIASES)


def render_page(settings: Settings, message: str, section: str, settings_tab: str = "") -> str:
    requested_section = section
    section = SECTION_ALIASES.get(section, section)
    if section == "settings" and not settings_tab:
        settings_tab = {
            "media-managers": "radarr",
            "radarr": "radarr",
            "sonarr": "sonarr",
            "worker": "worker",
            "indexer": "indexer",
            "downloader": "downloader",
            "jellyfin": "jellyfin",
        }.get(requested_section, "")
    config = settings.to_config_dict()
    templates = json.dumps(config["hls_template_sources"], indent=2)
    source_order = ",".join(config["source_order"])
    ffmpeg_args = ",".join(config["ffmpeg_extra_args"])
    radarr_ok = "ok" if settings.radarr_url and settings.radarr_api_key else ""
    sonarr_ok = "ok" if settings.sonarr_url and settings.sonarr_api_key else ""
    worker_ok = "ok" if settings.radarr_url or settings.sonarr_url else ""
    sources_display = html.escape(",".join(settings.source_order) or "none configured")
    msg_html = f'<div class="notice">{html.escape(message)}</div>' if message else ""
    section_title = {
        "dashboard": "Dashboard",
        "sources": "Sources",
        "settings": "Settings",
    }.get(section, "Dashboard")

    card_html, has_form = _section_card(section, settings, config, templates, source_order, ffmpeg_args, settings_tab)

    if has_form:
        test_button = ""
        if section in {"radarr", "sonarr"}:
            label = "Test Radarr" if section == "radarr" else "Test Sonarr"
            test_button = f'\n      <button type="submit" formaction="/test" class="btn btn-ghost">{label}</button>'
        actions = """
    <div class="actions">
      <button type="submit" class="btn btn-primary">&#10003; Save Changes</button>""" + test_button + """
    </div>"""
        content = f"""
  <form method="post" action="/save">
    <input type="hidden" name="_section" value="{html.escape(section)}">
    {card_html}
    {actions}
  </form>"""
    else:
        content = card_html

    nav_items = "\n".join(
        f'    <a href="/{s}" class="nav-item{"  active" if s == section else ""}"><span class="nav-icon">{icon}</span> {label}</a>'
        for s, icon, label in _NAV
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>vn-source-gateway</title>
  <style>{CSS}</style>
</head>
<body>

<nav class="sidebar">
  <a class="sidebar-brand" href="/dashboard">
    <div class="brand-icon">V</div>
    <div>
      <div class="brand-name">vn-source-gateway</div>
      <div class="brand-sub">Media Source Gateway</div>
    </div>
  </a>
  <div class="nav-group">
    <div class="nav-group-label">Navigation</div>
{nav_items}
  </div>
</nav>

<div class="topbar">
  <span class="topbar-title">{section_title} <span class="topbar-sub">{_attr(settings.config_path)}</span></span>
  <form method="post" action="/run-once" style="margin:0">
    <input type="hidden" name="_section" value="{html.escape(section)}">
    <button type="submit" class="btn btn-ghost">&#9654; Run Once</button>
  </form>
</div>

<main class="main">
  {msg_html}

  <div class="status-bar">
    <div class="pill {radarr_ok}">
      <span class="dot"></span><span class="pill-label">Radarr</span>
      <span>{"configured" if radarr_ok else "not configured"}</span>
    </div>
    <div class="pill {sonarr_ok}">
      <span class="dot"></span><span class="pill-label">Sonarr</span>
      <span>{"configured" if sonarr_ok else "not configured"}</span>
    </div>
    <div class="pill {worker_ok}">
      <span class="dot"></span><span class="pill-label">Worker</span>
      <span>{"configured" if settings.radarr_url or settings.sonarr_url else "not configured"}</span>
    </div>
    <div class="pill">
      <span class="dot"></span><span class="pill-label">Sources</span>
      <span>{sources_display}</span>
    </div>
  </div>

  {content}

</main>
</body>
</html>"""


def _section_card(
    section: str,
    settings: Settings,
    config: dict,
    templates: str,
    source_order: str,
    ffmpeg_args: str,
    settings_tab: str,
) -> tuple[str, bool]:
    if section == "dashboard":
        return download_tasks_card(_tasks_html(settings)), False
    if section == "sources":
        return sources_card(config, templates, source_order), True
    if section == "settings":
        return settings_card(config, ffmpeg_args, settings_tab), False
    return download_tasks_card(_tasks_html(settings)), False


def _tasks_html(settings: Settings) -> str:
    try:
        jobs = qbittorrent.torrents_info(settings)
    except Exception as exc:
        return f"<p style='color:var(--muted)'>Could not load jobs: {html.escape(str(exc))}</p>"
    if not jobs:
        return "<p style='color:var(--muted);font-size:13px'>No download tasks yet.</p>"
    rows = []
    for job in sorted(jobs, key=lambda item: item.get("added_on", 0), reverse=True)[:25]:
        state = str(job.get("state", ""))
        badge_cls = "running" if state in {"uploading", "downloading"} else (
            "error" if "error" in state.lower() else (
                "completed" if state == "pausedUP" else ""
            )
        )
        progress = int(float(job.get("progress", 0)) * 100)
        task_hash = _attr(job.get("hash", ""))
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(job.get('name', '')))}</td>"
            f"<td><span class='badge {badge_cls}'>{html.escape(state)}</span></td>"
            f"<td>{progress}%</td>"
            f"<td style='color:var(--muted)'>{html.escape(str(job.get('save_path', '')))}</td>"
            "<td>"
            f"<form method='post' action='/tasks/action' class='task-actions'>"
            f"<input type='hidden' name='hashes' value='{task_hash}'>"
            "<button type='submit' name='action' value='resume' class='btn btn-ghost btn-small'>Resume</button>"
            "<button type='submit' name='action' value='pause' class='btn btn-ghost btn-small'>Pause</button>"
            "<button type='submit' name='action' value='delete' class='btn btn-danger btn-small'>Delete</button>"
            "</form>"
            "</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Name</th><th>State</th><th>Progress</th><th>Path</th><th>Actions</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )
