from __future__ import annotations

import html
import json

from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.interfaces.download_clients import qbittorrent
from .cards import (
    _attr,
    activity_log_card,
    download_tasks_card,
    settings_card,
    sources_card,
)
from .styles import CSS

# ---------------------------------------------------------------------------
# Dashboard live-update script
# Polls /dashboard every 5 s and replaces just the #pipeline card in-place,
# preserving the open/closed state of every <details> panel so the user
# doesn't lose their expanded rows on refresh.
# ---------------------------------------------------------------------------
_DASHBOARD_POLL_JS = r"""
(function () {
  var INTERVAL = 5000;

  function openKeys() {
    var keys = new Set();
    document.querySelectorAll('#pipeline details[open]').forEach(function (d) {
      var td = d.closest('td');
      if (td) keys.add(td.textContent.trim().slice(0, 80));
    });
    return keys;
  }

  function restoreOpen(keys) {
    document.querySelectorAll('#pipeline details').forEach(function (d) {
      var td = d.closest('td');
      if (td && keys.has(td.textContent.trim().slice(0, 80))) d.open = true;
    });
  }

  function refresh() {
    var open = openKeys();
    fetch('/dashboard', {cache: 'no-store'})
      .then(function (r) { return r.text(); })
      .then(function (text) {
        var tmp = document.createElement('div');
        tmp.innerHTML = text;
        var newCard = tmp.querySelector('#pipeline');
        var oldCard = document.getElementById('pipeline');
        if (newCard && oldCard) {
          oldCard.replaceWith(newCard);
          restoreOpen(open);
        }
      })
      .catch(function () {});
  }

  setInterval(refresh, INTERVAL);
})();
"""

_NAV = [
    ("dashboard", "Dashboard"),
    ("sources", "Sources"),
    ("settings", "Settings"),
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
ALL_SECTIONS = {s for s, _ in _NAV} | set(SECTION_ALIASES)


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
        f'    <a href="/{s}" class="nav-item{"  active" if s == section else ""}">{label}</a>'
        for s, label in _NAV
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
{nav_items}
  </div>
</nav>

<div class="topbar">
  <span class="topbar-title">{section_title} <span class="topbar-sub">{_attr(settings.config_path)}</span></span>
</div>

<main class="main{'' if section == 'dashboard' else ' constrained'}">
  {msg_html}

  {content}

</main>

{'<script>' + _DASHBOARD_POLL_JS + '</script>' if section == "dashboard" else ""}
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
        return _pipeline_card(settings), False
    if section == "sources":
        return sources_card(config, templates, source_order), True
    if section == "settings":
        return settings_card(config, ffmpeg_args, settings_tab), False
    return _pipeline_card(settings), False


def _detail_panel(steps: list[tuple[str, str, str, str]], open_by_default: bool = True) -> str:
    """Build a collapsible <details> panel showing pipeline step details.

    steps: list of (icon, name, message, status)  — status is "ok" | "error" | ""
    """
    rows_html = ""
    for icon, name, msg, status in steps:
        if not msg:
            continue
        msg_class = "pipe-step-msg"
        if status == "ok":
            msg_class += " ok"
        elif status == "error":
            msg_class += " err"
        rows_html += (
            f"<div class='pipe-step'>"
            f"<span class='pipe-step-icon'>{icon}</span>"
            f"<span class='pipe-step-name'>{html.escape(name)}</span>"
            f"<span class='{msg_class}'>{html.escape(msg)}</span>"
            f"</div>"
        )
    if not rows_html:
        return ""
    open_attr = " open" if open_by_default else ""
    return (
        f"<details class='pipe-detail'{open_attr}>"
        f"<summary>details</summary>"
        f"<div class='pipe-steps'>{rows_html}</div>"
        f"</details>"
    )


def _pipeline_card(settings: Settings) -> str:
    from vn_source_gateway.infrastructure.activity import ActivityLog, ActivityEvent
    import time as _time

    # ── collect jobs ──────────────────────────────────────────────────────────
    try:
        jobs = sorted(
            qbittorrent.torrents_info(settings),
            key=lambda x: x.get("added_on", 0), reverse=True,
        )[:25]
    except Exception as exc:
        jobs = []

    # ── collect recent searches (no job yet) ──────────────────────────────────
    now = int(_time.time())
    events = ActivityLog.get().recent(50)
    job_hashes = {j.get("hash", "") for j in jobs}
    # searches in last 5 min with no matching job
    pending_searches: list[ActivityEvent] = [
        e for e in events
        if e.kind == "search" and (now - e.ts) < 300
    ]

    rows = []

    # index activity events by ref (job_id)
    events_by_ref: dict[str, list] = {}
    for ev in events:
        if ev.ref:
            events_by_ref.setdefault(ev.ref, []).append(ev)

    # ── pending searches (not grabbed yet) ───────────────────────────────────
    for ev in pending_searches[:5]:
        detail_html = _detail_panel([
            ("🔍", "Search", ev.detail, "ok"),
            ("·", "Matching", "waiting for grab...", ""),
            ("·", "Saving", "", ""),
            ("·", "Done", "", ""),
        ], open_by_default=False)
        rows.append(
            "<tr>"
            f"<td style='padding:12px 16px'>{html.escape(ev.title)}{detail_html}</td>"
            f"<td>{_pipeline_steps('search', False, 0)}</td>"
            f"<td style='color:var(--muted)'>—</td>"
            f"<td style='color:var(--muted)'>—</td>"
            "<td></td>"
            "</tr>"
        )

    # ── jobs ──────────────────────────────────────────────────────────────────
    for job in jobs:
        state = str(job.get("state", ""))
        progress = float(job.get("progress", 0))
        task_hash = _attr(job.get("hash", ""))
        job_id = str(job.get("hash", ""))
        is_error = "error" in state.lower()
        error_msg = str(job.get("error", "") or "")

        # pipeline stage
        if state in {"uploading", "pausedUP"}:
            stage = "done"
        elif is_error:
            stage = "error"
        elif state == "downloading":
            stage = "saving" if progress >= 0.35 else "matching"
        elif state == "pausedDL":
            stage = "paused"
        else:
            stage = "matching"

        pipeline_html = _pipeline_steps(stage, is_error, progress)

        # related activity events
        job_events = events_by_ref.get(job_id, [])
        grab_ev = next((e for e in job_events if e.kind == "grab"), None)
        resolved_ev = next((e for e in job_events if e.kind == "job" and "Resolved" in e.detail), None)
        done_ev = next((e for e in job_events if e.kind == "job" and "Done" in e.detail), None)
        err_ev = next((e for e in job_events if e.kind == "job" and e.status == "error"), None)

        save_path = str(job.get("save_path", "") or "")
        source = grab_ev.detail if grab_ev else (str(job.get("tags", "") or str(job.get("category", "") or "—")))
        path_display = save_path.split("/")[-1] if save_path else "—"

        # build detail panel rows
        search_msg = "grabbed from Radarr/Sonarr"
        search_status = "ok"

        if grab_ev:
            match_msg = grab_ev.detail
            match_status = "ok"
        elif stage in {"matching"} and not is_error:
            match_msg = "resolving source…"
            match_status = ""
        elif resolved_ev:
            match_msg = resolved_ev.detail
            match_status = "ok"
        else:
            match_msg = "—"
            match_status = ""

        if resolved_ev:
            match_msg = resolved_ev.detail
            match_status = "ok"

        if is_error:
            save_msg = error_msg or "failed"
            save_status = "error"
        elif stage == "saving":
            save_msg = f"writing… {int(progress * 100)}%"
            save_status = ""
        elif done_ev:
            save_msg = done_ev.detail.replace("Done — ", "")
            save_status = "ok"
        elif save_path:
            save_msg = save_path
            save_status = "ok"
        else:
            save_msg = "—"
            save_status = ""

        done_msg = "completed" if stage == "done" else ("—" if stage != "done" else "")
        done_status = "ok" if stage == "done" else ""

        detail_rows = [
            ("🔍", "Search", search_msg, search_status),
            ("⚙", "Matching", match_msg, match_status),
            ("💾", "Saving", save_msg, save_status),
            ("✓", "Done", done_msg, done_status),
        ]
        open_by_default = is_error or stage not in {"done"}
        detail_html = _detail_panel(detail_rows, open_by_default=open_by_default)

        # actions
        buttons = ""
        if is_error:
            buttons += "<button type='submit' name='action' value='resume' class='btn btn-ghost btn-small'>Retry</button>"
        elif state in {"downloading", "queuedDL"}:
            buttons += "<button type='submit' name='action' value='pause' class='btn btn-ghost btn-small'>Pause</button>"
        elif state == "pausedDL":
            buttons += "<button type='submit' name='action' value='resume' class='btn btn-ghost btn-small'>Resume</button>"
        buttons += "<button type='submit' name='action' value='delete' class='btn btn-danger btn-small'>Delete</button>"

        rows.append(
            "<tr>"
            f"<td style='padding:12px 16px'>{html.escape(str(job.get('name', '')))}{detail_html}</td>"
            f"<td style='white-space:nowrap'>{pipeline_html}</td>"
            f"<td style='color:var(--muted);font-size:12px'>{html.escape(source)}</td>"
            f"<td style='color:var(--muted);font-size:12px' title='{_attr(save_path)}'>{html.escape(path_display)}</td>"
            "<td style='white-space:nowrap'>"
            f"<form method='post' action='/tasks/action' class='task-actions'>"
            f"<input type='hidden' name='hashes' value='{task_hash}'>"
            f"{buttons}"
            "</form>"
            "</td>"
            "</tr>"
        )

    if not rows:
        body = "<p style='color:var(--muted);font-size:13px'>No activity yet. Search or grab from Radarr/Sonarr to get started.</p>"
    else:
        body = (
            "<table style='width:100%'><thead><tr>"
            "<th>Task Name</th><th>Progress</th><th>Source</th><th>Path</th><th>Actions</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )

    return f"""
  <div class="card" id="pipeline" style="margin:0">
    <div class="card-header">
      <div><div class="card-title">Download Tasks</div>
      <div class="card-desc">Full pipeline: search → matching → saving → done</div></div>
    </div>
    <div class="card-body" style="padding:0">
      <div style="overflow-x:auto">{body}</div>
    </div>
  </div>"""


def _pipeline_steps(stage: str, is_error: bool, progress: float) -> str:
    # stages in order
    STAGES = [
        ("search",   "Search"),
        ("matching", "Matching"),
        ("saving",   "Saving"),
        ("done",     "Done"),
    ]
    ORDER = [s for s, _ in STAGES]

    if is_error:
        # find last completed stage before error
        cur_idx = ORDER.index("matching") if stage == "error" else 0
    else:
        cur_idx = ORDER.index(stage) if stage in ORDER else 0

    parts = []
    for i, (key, label) in enumerate(STAGES):
        if is_error and i == cur_idx:
            cls = "ps-error"
        elif i < cur_idx or (not is_error and stage == "done"):
            cls = "ps-done"
        elif i == cur_idx:
            cls = "ps-active"
        else:
            cls = "ps-pending"

        # progress % inside active saving step
        extra = ""
        if key == "saving" and stage == "saving" and not is_error:
            pct = int(progress * 100)
            extra = f" {pct}%"

        parts.append(f"<span class='ps {cls}'>{label}{extra}</span>")
        if i < len(STAGES) - 1:
            parts.append("<span class='ps-sep'>›</span>")

    return "<span class='pipeline'>" + "".join(parts) + "</span>"
