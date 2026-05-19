from __future__ import annotations

import html
import json

from ..config import Settings
from ..download_clients import qbittorrent
from .cards import (
    _attr,
    downloader_card,
    indexer_card,
    jellyfin_card,
    jobs_card,
    sources_card,
    worker_card,
)
from .styles import CSS

_NAV = [
    ("worker", "&#9654;", "Worker"),
    ("sources", "&#9654;", "Sources"),
    ("indexer", "&#9654;", "Indexer"),
    ("downloader", "&#9654;", "Download Client"),
    ("jellyfin", "&#9654;", "Jellyfin"),
    ("jobs", "&#9654;", "Jobs"),
]

ALL_SECTIONS = {s for s, _, _ in _NAV}


def render_page(settings: Settings, message: str, section: str) -> str:
    config = settings.to_config_dict()
    templates = json.dumps(config["hls_template_sources"], indent=2)
    source_order = ",".join(config["source_order"])
    ffmpeg_args = ",".join(config["ffmpeg_extra_args"])
    worker_ok = "ok" if settings.radarr_url or settings.sonarr_url else ""
    sources_display = html.escape(",".join(settings.source_order) or "none configured")
    msg_html = f'<div class="notice">{html.escape(message)}</div>' if message else ""

    card_html, has_form = _section_card(section, settings, config, templates, source_order, ffmpeg_args)

    if has_form:
        actions = """
    <div class="actions">
      <button type="submit" class="btn btn-primary">&#10003; Save Changes</button>
      <button type="submit" formaction="/test" class="btn btn-ghost">Test Connections</button>
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
  <a class="sidebar-brand" href="/worker">
    <div class="brand-icon">V</div>
    <div>
      <div class="brand-name">vn-source-gateway</div>
      <div class="brand-sub">Media Source Gateway</div>
    </div>
  </a>
  <div class="nav-group">
    <div class="nav-group-label">Settings</div>
{nav_items}
  </div>
</nav>

<div class="topbar">
  <span class="topbar-title">Settings <span class="topbar-sub">{_attr(settings.config_path)}</span></span>
  <form method="post" action="/run-once" style="margin:0">
    <input type="hidden" name="_section" value="{html.escape(section)}">
    <button type="submit" class="btn btn-ghost">&#9654; Run Once</button>
  </form>
</div>

<main class="main">
  {msg_html}

  <div class="status-bar">
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
) -> tuple[str, bool]:
    if section == "worker":
        return worker_card(config), True
    if section == "sources":
        return sources_card(config, templates, source_order, ffmpeg_args), True
    if section == "indexer":
        return indexer_card(config), True
    if section == "downloader":
        return downloader_card(config), True
    if section == "jellyfin":
        return jellyfin_card(config), True
    if section == "jobs":
        return jobs_card(_jobs_html(settings)), False
    return worker_card(config), True


def _jobs_html(settings: Settings) -> str:
    try:
        jobs = qbittorrent.torrents_info(settings)
    except Exception as exc:
        return f"<p style='color:var(--muted)'>Could not load jobs: {html.escape(str(exc))}</p>"
    if not jobs:
        return "<p style='color:var(--muted);font-size:13px'>No jobs yet.</p>"
    rows = []
    for job in sorted(jobs, key=lambda item: item.get("added_on", 0), reverse=True)[:25]:
        state = str(job.get("state", ""))
        badge_cls = "running" if state in {"uploading", "downloading"} else (
            "error" if "error" in state.lower() else (
                "completed" if state == "pausedUP" else ""
            )
        )
        progress = int(float(job.get("progress", 0)) * 100)
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(job.get('name', '')))}</td>"
            f"<td><span class='badge {badge_cls}'>{html.escape(state)}</span></td>"
            f"<td>{progress}%</td>"
            f"<td style='color:var(--muted)'>{html.escape(str(job.get('save_path', '')))}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Name</th><th>State</th><th>Progress</th><th>Path</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
