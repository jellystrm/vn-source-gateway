from __future__ import annotations

import html
import json

from vn_source_gateway.infrastructure.config import Settings
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

  // Track open package IDs (tree view)
  function openPkgIds() {
    var ids = [];
    document.querySelectorAll('#pipeline .jd-tree-arr').forEach(function (a) {
      if (a.textContent.trim() === '▼') ids.push(a.id);
    });
    return ids;
  }
  function restorePkgIds(ids) {
    ids.forEach(function (arrowId) {
      var a = document.getElementById(arrowId);
      if (a && a.textContent.trim() === '▶') {
        window.jdTogglePkg(arrowId.slice(7)); // strip 'jd-arr-'
      }
    });
  }

  function activeTab() {
    var a = document.querySelector('#pipeline .jd-tab.active');
    return a ? a.dataset.tab : 'downloads';
  }

  window.jdSwitchTab = function(tab) {
    document.querySelectorAll('#pipeline .jd-tab').forEach(function(t) {
      t.classList.toggle('active', t.dataset.tab === tab);
    });
    document.querySelectorAll('#pipeline .jd-pane').forEach(function(p) {
      p.style.display = (p.id === 'jd-' + tab) ? '' : 'none';
    });
    document.querySelectorAll('#pipeline .jd-statusbar').forEach(function(s) {
      s.style.display = (s.id === 'jd-sb-' + tab) ? '' : 'none';
    });
  };

  window.jdTogglePkg = function(id) {
    var arrow = document.getElementById('jd-arr-' + id);
    if (!arrow) return;
    var opening = arrow.textContent.trim() === '▶';
    arrow.textContent = opening ? '▼' : '▶';
    document.querySelectorAll('.jd-c-' + id).forEach(function (r) {
      r.style.display = opening ? '' : 'none';
    });
  };

  function refresh() {
    var open = openKeys();
    var tab = activeTab();
    var pkgs = openPkgIds();
    fetch('/dashboard', {cache: 'no-store'})
      .then(function (r) { return r.text(); })
      .then(function (text) {
        var tmp = document.createElement('div');
        tmp.innerHTML = text;
        var newCard = tmp.querySelector('#pipeline');
        var oldCard = document.getElementById('pipeline');
        if (newCard && oldCard) {
          oldCard.replaceWith(newCard);
          window.jdSwitchTab(tab);
          restoreOpen(open);
          restorePkgIds(pkgs);
        }
      })
      .catch(function () {});
  }

  setInterval(refresh, INTERVAL);
  refresh(); // scan immediately on page load

  // Intercept task-action and manual-grab form submits via fetch
  document.addEventListener('submit', function (e) {
    if (!e.target.classList.contains('task-actions')) return;
    e.preventDefault();
    fetch(e.target.action, {method: 'POST', body: new FormData(e.target)})
      .catch(function () {})
      .finally(function () { refresh(); });
  });

  // Bulk toolbar actions (Start All / Pause All / Clear Done)
  window.jdBulkAction = function(action) {
    fetch('/tasks/bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: 'action=' + encodeURIComponent(action)
    }).catch(function(){}).finally(function() { refresh(); });
  };
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
    "tasks": "settings",
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
            "tasks": "tasks",
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

<main class="main{' dashboard' if section == 'dashboard' else ' constrained'}">
  {msg_html}

  {content}

</main>

{'<script>' + _DASHBOARD_POLL_JS + '</script>' if section == "dashboard" else ""}
{"<script>document.addEventListener('DOMContentLoaded',function(){var a=document.activeElement;if(a&&(a.tagName==='INPUT'||a.tagName==='TEXTAREA'||a.tagName==='SELECT'))a.blur();});</script>" if section == "settings" else ""}
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
        return sources_card(config, templates, source_order), False  # manages its own form
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


def _time_ago(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _pipeline_card(settings: Settings) -> str:
    """JDownloader-style tabbed layout: LinkGrabber + Downloads tabs."""
    lg_html, lg_pkgs, lg_links, lg_errors = _indexer_card(settings)
    dl_html, dl_pkgs, dl_running, dl_errors = _download_card(settings)

    lg_statusbar = (
        f"<div class='jd-sb-row'>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Package(s):</span>"
        f"<span class='jd-stat-val'>{lg_pkgs}</span></span>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Link(s):</span>"
        f"<span class='jd-stat-val'>{lg_links}</span></span>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Online:</span>"
        f"<span class='jd-stat-val' style='color:var(--green)'>{lg_pkgs - lg_errors}</span></span>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Offline:</span>"
        f"<span class='jd-stat-val' style='color:#e06c75'>{lg_errors}</span></span>"
        f"</div>"
    )
    dl_statusbar = (
        f"<div class='jd-sb-row'>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Package(s):</span>"
        f"<span class='jd-stat-val'>{dl_pkgs}</span></span>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Running:</span>"
        f"<span class='jd-stat-val' style='color:var(--green)'>{dl_running}</span></span>"
        f"<span class='jd-stat'><span class='jd-stat-label'>Errors:</span>"
        f"<span class='jd-stat-val' style='color:#e06c75'>{dl_errors}</span></span>"
        f"</div>"
    )

    return (
        "<div id='pipeline' class='jd-wrap'>"
        # Toolbar
        "<div class='jd-toolbar'>"
        "<button class='jd-tb-btn' title='Resume all paused/error jobs' onclick='jdBulkAction(\"resume_all\")'>&#9654; Start All</button>"
        "<button class='jd-tb-btn' title='Pause all running jobs' onclick='jdBulkAction(\"pause_all\")'>&#9646;&#9646; Pause All</button>"
        "<div class='jd-tb-sep'></div>"
        "<button class='jd-tb-btn' title='Remove completed jobs' onclick='jdBulkAction(\"clear_done\")'>&#10005; Clear Done</button>"
        "<div class='jd-tb-sep'></div>"
        "<button class='jd-tb-btn' title='Refresh now' onclick='refresh()' style='margin-left:auto'>&#8635; Refresh</button>"
        "</div>"
        # Tabs
        "<div class='jd-tabbar'>"
        f"<div class='jd-tab' data-tab='linkgrabber' onclick='jdSwitchTab(\"linkgrabber\")'>"
        f"&#128279; LinkGrabber <span class='jd-badge'>{lg_pkgs}</span></div>"
        f"<div class='jd-tab active' data-tab='downloads' onclick='jdSwitchTab(\"downloads\")'>"
        f"&#11015; Downloads <span class='jd-badge'>{dl_pkgs}</span></div>"
        "</div>"
        # Panes
        f"<div id='jd-linkgrabber' class='jd-pane' style='display:none'>{lg_html}</div>"
        f"<div id='jd-downloads' class='jd-pane'>{dl_html}</div>"
        # Status bars
        f"<div id='jd-sb-linkgrabber' class='jd-statusbar' style='display:none'>{lg_statusbar}</div>"
        f"<div id='jd-sb-downloads' class='jd-statusbar'>{dl_statusbar}</div>"
        "</div>"
    )


def _grab_btns(token_esc: str) -> str:
    """Three tiny inline forms: STRM / MKV / MP4 (single token)."""
    def btn(mode: str, container: str, label: str) -> str:
        cont_field = f"<input type='hidden' name='container' value='{container}'>" if mode == "download" else ""
        return (
            f"<form method='post' action='/api/manual-grab' class='task-actions' style='display:inline;margin:0'>"
            f"<input type='hidden' name='token' value='{token_esc}'>"
            f"<input type='hidden' name='output_mode' value='{mode}'>"
            f"{cont_field}"
            f"<button type='submit' class='jd-tb-btn' style='height:20px;font-size:10px'>{label}</button>"
            f"</form>"
        )
    return btn("strm", "", "STRM") + btn("download", "mkv", "MKV") + btn("download", "mp4", "MP4")


def _bulk_grab_btns(tokens: list[str]) -> str:
    """Three tiny inline forms: STRM / MKV / MP4 (bulk — all tokens at once)."""
    import json as _json
    toks_esc = html.escape(_json.dumps(tokens), quote=True)

    def btn(mode: str, container: str, label: str) -> str:
        cont = f"<input type='hidden' name='container' value='{container}'>" if mode == "download" else ""
        return (
            f"<form method='post' action='/api/manual-grab-bulk' class='task-actions' style='display:inline;margin:0'>"
            f"<input type='hidden' name='tokens' value='{toks_esc}'>"
            f"<input type='hidden' name='output_mode' value='{mode}'>"
            f"{cont}"
            f"<button type='submit' class='jd-tb-btn' style='height:20px;font-size:10px'>{label}</button>"
            f"</form>"
        )
    return btn("strm", "", "STRM") + btn("download", "mkv", "MKV") + btn("download", "mp4", "MP4")


def _build_grab_tree(grabs: list[dict]) -> list[dict]:
    """Decode + group grab tokens into package tree nodes for the tree-view UI.

    Each node:
      title       – display label for the package row
      pkg_token   – base token (season pack if available)
      ep_tokens   – list of episode tokens for bulk grab
      children    – list of {title, token, r} for individual episodes
      kind        – "movie" | "episode"
    """
    from vn_source_gateway.application.grab_service import decode_release

    # Decode + deduplicate (prefer strm token as canonical per episode)
    seen: dict[tuple, dict] = {}
    for g in grabs:
        tok = g.get("token", "")
        title = g.get("title", "")
        for suf in (" [STRM]", " [HLS-DL]"):
            if title.endswith(suf):
                title = title[:-len(suf)]
                break
        try:
            r = decode_release(tok)
        except Exception:
            continue
        key = (r.source_name, r.kind, r.season_number, r.episode_number)
        existing = seen.get(key)
        if not existing or r.output_mode == "strm":
            seen[key] = {"title": title, "token": tok, "r": r}

    decoded = list(seen.values())
    pkg_map: dict[tuple, dict] = {}

    # Pass 1: movies and season packs become package headers
    for item in decoded:
        r = item["r"]
        if r.kind == "movie":
            key = ("mv", r.source_name, r.title)
            if key not in pkg_map:
                pkg_map[key] = {
                    "title": item["title"], "pkg_token": item["token"],
                    "ep_tokens": [item["token"]], "children": [], "kind": "movie",
                }
        elif r.kind == "episode" and r.episode_number is None:
            key = ("tv", r.source_name, r.season_number)
            if key not in pkg_map:
                pkg_map[key] = {
                    "title": item["title"], "pkg_token": item["token"],
                    "ep_tokens": [], "children": [], "kind": "episode",
                }
            else:
                pkg_map[key]["title"] = item["title"]
                pkg_map[key]["pkg_token"] = item["token"]

    # Pass 2: individual episodes → attach to their package
    for item in decoded:
        r = item["r"]
        if r.kind != "episode" or r.episode_number is None:
            continue
        key = ("tv", r.source_name, r.season_number)
        if key not in pkg_map:
            s = r.season_number
            auto = (
                f"{r.source_name or ''} S{s:02d}" if s is not None
                else f"{r.source_name or ''} S??"
            )
            pkg_map[key] = {
                "title": auto, "pkg_token": item["token"],
                "ep_tokens": [], "children": [], "kind": "episode",
            }
        pkg_map[key]["ep_tokens"].append(item["token"])
        pkg_map[key]["children"].append(item)

    for pkg in pkg_map.values():
        pkg["children"].sort(key=lambda x: (x["r"].episode_number or 0))

    return list(pkg_map.values())


def _indexer_card(settings: Settings) -> tuple[str, int, int, int]:
    """LinkGrabber tab — tree view of packages.  Returns (html, pkg_count, link_count, error_count)."""
    from vn_source_gateway.infrastructure.activity import ActivityLog
    import time as _time

    now = int(_time.time())
    events = ActivityLog.get().recent(100)
    searches = [e for e in events if e.kind == "search"][:20]

    if not searches:
        return "<div class='jd-empty'>No indexer queries yet.</div>", 0, 0, 0

    # Deduplicate by title (keep most-recent per show)
    seen_ev: dict[str, object] = {}
    for ev in searches:
        if ev.title not in seen_ev:
            seen_ev[ev.title] = ev
    deduped = list(seen_ev.values())

    error_count = sum(1 for ev in deduped if ev.status != "ok")
    total_pkgs = 0
    total_links = 0
    rows: list[str] = []
    pkg_counter = 0

    for ev in deduped:
        age = _time_ago(max(0, now - ev.ts))
        ev_grabs = getattr(ev, "grabs", []) or []
        ev_url = getattr(ev, "url", "") or ""
        dot_cls = "ok" if ev.status == "ok" else "err"

        if ": " in ev.title:
            kind_prefix, show_title = ev.title.split(": ", 1)
        else:
            kind_prefix, show_title = "", ev.title

        if not ev_grabs:
            # No grabs stored — just show a summary row
            detail = ev.detail.split(" — ")[0] if " — " in ev.detail else ev.detail
            rows.append(
                f"<tr style='background:rgba(0,0,0,0.06)'>"
                f"<td style='font-size:11px;color:var(--text);padding:5px 8px' colspan='2'>"
                f"{html.escape(show_title)} "
                f"<span style='color:var(--muted)'>— {html.escape(detail)}</span></td>"
                f"<td></td>"
                f"<td style='font-size:11px;color:var(--muted);white-space:nowrap'>{html.escape(age)}</td>"
                f"<td style='text-align:center'><span class='sdot {dot_cls}'></span></td>"
                f"</tr>"
            )
            continue

        packages = _build_grab_tree(ev_grabs)
        if not packages:
            continue

        n_pkgs = len(packages)
        n_links = sum(max(len(p["ep_tokens"]), 1) for p in packages)
        total_pkgs += n_pkgs
        total_links += n_links

        xml_a = (
            f" <a href='{html.escape(ev_url)}' target='_blank'"
            f" style='font-size:10px;color:var(--accent)' title='Open XML'>↗</a>"
        ) if ev_url else ""

        # Search-event group header (darker background, no expand — just a label)
        rows.append(
            f"<tr style='background:rgba(0,0,0,0.14)'>"
            f"<td style='font-size:11px;font-weight:600;color:var(--text);padding:5px 10px'>"
            f"{html.escape(show_title)}{xml_a}</td>"
            f"<td style='font-size:10px;color:var(--muted);white-space:nowrap'>"
            f"{html.escape(kind_prefix)} &middot; {n_pkgs} pkg &middot; {n_links} links</td>"
            f"<td></td>"
            f"<td style='font-size:11px;color:var(--muted);white-space:nowrap'>{html.escape(age)}</td>"
            f"<td style='text-align:center'><span class='sdot {dot_cls}'></span></td>"
            f"</tr>"
        )

        for pkg in packages:
            pkg_id = f"lg{pkg_counter}"
            pkg_counter += 1
            children = pkg["children"]
            ep_tokens = pkg["ep_tokens"] or [pkg["pkg_token"]]
            has_ch = bool(children)
            count_txt = f"{len(children)} ep" if children else ""
            btns = _bulk_grab_btns(ep_tokens)

            if has_ch:
                arrow = (
                    f"<span class='jd-tree-arr' id='jd-arr-{pkg_id}'"
                    f" style='color:var(--muted)'>&#9658;</span>"
                )
                toggle = f"onclick='jdTogglePkg(\"{pkg_id}\")'"
            else:
                arrow = "<span style='display:inline-block;width:12px'></span>"
                toggle = ""

            rows.append(
                f"<tr class='jd-pkg-row' {toggle}>"
                f"<td style='padding:4px 8px 4px 20px'>"
                f"<div style='display:flex;align-items:center;gap:6px'>"
                f"{arrow}"
                f"<span style='font-size:12px;font-weight:500'>{html.escape(pkg['title'])}</span>"
                f"</div></td>"
                f"<td style='font-size:10px;color:var(--muted);white-space:nowrap'>{count_txt}</td>"
                f"<td style='white-space:nowrap'>{btns}</td>"
                f"<td></td><td></td>"
                f"</tr>"
            )

            for child in children:
                r = child["r"]
                ep_n = r.episode_number
                ep_label = f"E{ep_n:02d}" if ep_n is not None else child["title"]
                tok_esc = html.escape(child["token"], quote=True)
                rows.append(
                    f"<tr class='jd-child-r jd-c-{pkg_id}' style='display:none'>"
                    f"<td style='padding:3px 8px 3px 42px;font-size:11px;color:var(--muted)'>"
                    f"{html.escape(ep_label)}</td>"
                    f"<td></td>"
                    f"<td style='white-space:nowrap'>{_grab_btns(tok_esc)}</td>"
                    f"<td></td><td></td>"
                    f"</tr>"
                )

    if not rows:
        return "<div class='jd-empty'>No indexer queries yet.</div>", 0, 0, 0

    body = (
        "<table class='jd-table'><thead><tr>"
        "<th style='padding-left:20px'>Name</th><th>Info</th><th>Actions</th><th>When</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    return body, total_pkgs, total_links, error_count


def _download_card(settings: Settings) -> tuple[str, int, int, int]:
    """Downloads tab — tree view of packages.  Returns (html, pkg_count, running_count, error_count)."""
    from vn_source_gateway.infrastructure.jobs import JobStore
    import time as _time

    now = int(_time.time())
    store = JobStore(settings.state_path)
    all_jobs = sorted(store.list_jobs(), key=lambda j: j.created_at, reverse=True)[:200]

    if not all_jobs:
        return "<div class='jd-empty'>No download tasks yet.</div>", 0, 0, 0

    # Group into packages — key order preserved (newest-first since all_jobs is sorted desc)
    pkg_order: list[tuple] = []
    pkg_map: dict[tuple, dict] = {}

    for job in all_jobs:
        r = job.release
        if r.kind == "movie":
            year = f" ({r.year})" if r.year else ""
            key: tuple = ("mv", r.title)
            label = f"{r.title}{year}"
        else:
            s = r.season_number if r.season_number is not None else 0
            key = ("tv", r.title, s)
            label = f"{r.title} S{s:02d}"

        if key not in pkg_map:
            pkg_order.append(key)
            pkg_map[key] = {"label": label, "kind": r.kind, "jobs": []}
        pkg_map[key]["jobs"].append(job)

    running_count = 0
    error_count = 0
    rows: list[str] = []

    for pi, key in enumerate(pkg_order):
        pkg_id = f"dl{pi}"
        pkg = pkg_map[key]
        jobs = pkg["jobs"]

        n_total = len(jobs)
        n_done = sum(1 for j in jobs if j.status == "completed")
        n_running = sum(1 for j in jobs if j.status == "running")
        n_error = sum(1 for j in jobs if j.status == "error")
        n_queued = sum(1 for j in jobs if j.status == "queued")
        running_count += n_running
        if n_error > 0:
            error_count += 1

        if n_error > 0:
            pkg_status = f"<span style='color:#e06c75'>{n_error} error{'s' if n_error > 1 else ''}</span>"
        elif n_running > 0:
            pct_done = int(n_done / n_total * 100) if n_total else 0
            pkg_status = (
                f"<span style='color:var(--green)'>{n_done}/{n_total}"
                f"<span style='color:var(--muted)'> &middot; {n_running} running</span></span>"
            )
        elif n_queued > 0:
            pkg_status = f"<span style='color:var(--muted)'>{n_done}/{n_total} &middot; {n_queued} queued</span>"
        elif n_done == n_total:
            pkg_status = f"<span style='color:var(--accent)'>&#10003; {n_done}/{n_total}</span>"
        else:
            pkg_status = f"<span style='color:var(--muted)'>{n_done}/{n_total}</span>"

        has_ch = n_total > 1
        toggle = f"onclick='jdTogglePkg(\"{pkg_id}\")'" if has_ch else ""
        if has_ch:
            arrow = (
                f"<span class='jd-tree-arr' id='jd-arr-{pkg_id}'"
                f" style='color:var(--muted)'>&#9658;</span>"
            )
        else:
            arrow = "<span style='display:inline-block;width:12px'></span>"

        # Package row
        rows.append(
            f"<tr class='jd-pkg-row' {toggle}>"
            f"<td style='padding:5px 10px'>"
            f"<div style='display:flex;align-items:center;gap:6px'>"
            f"{arrow}"
            f"<span style='font-size:12px;font-weight:500'>{html.escape(pkg['label'])}</span>"
            f"</div></td>"
            f"<td colspan='4' style='font-size:11px;padding:5px 10px'>{pkg_status}</td>"
            f"</tr>"
        )

        # Sort children: season → episode → source
        def _jkey(j: object) -> tuple:
            rel = j.release  # type: ignore[attr-defined]
            return (
                rel.season_number if rel.season_number is not None else 0,
                rel.episode_number if rel.episode_number is not None else 0,
                rel.source_name or "",
            )

        for job in sorted(jobs, key=_jkey):
            r = job.release
            if r.kind == "episode":
                ep_n = r.episode_number
                ep_label = f"E{ep_n:02d}" if ep_n is not None else "Season Pack"
                if r.source_name:
                    ep_label += f"  ·  {r.source_name}"
            else:
                ep_label = r.title

            progress = job.progress or 0.0
            status = job.status
            is_err = status == "error"

            if is_err:
                pct = max(5, int(progress * 100))
                bar_cls, status_txt = "fail", f"Error — {job.error[:40]}" if job.error else "Error"
                status_color = "#e06c75"
            elif status == "completed":
                pct, bar_cls, status_txt = 100, "done", "Done"
                status_color = "var(--accent)"
            elif status == "running":
                pct = max(5, int(progress * 100))
                bar_cls, status_txt = "pulse", f"{pct}%"
                status_color = "var(--green)"
            elif status == "paused":
                pct = max(5, int(progress * 100))
                bar_cls, status_txt = "pulse", "Paused"
                status_color = "var(--muted)"
            else:
                pct, bar_cls, status_txt = 5, "pulse", "Queued"
                status_color = "var(--muted)"

            pbar = (
                f"<div class='pbar' style='width:100px'>"
                f"<div class='pbar-fill {bar_cls}' style='width:{pct}%'></div>"
                f"<div class='pbar-txt'>{pct}%</div>"
                f"</div>"
            )

            task_hash = _attr(job.job_id)
            btns = ""
            if is_err:
                btns += "<button type='submit' name='action' value='resume' class='jd-tb-btn'>Retry</button>"
            elif status == "running":
                btns += "<button type='submit' name='action' value='pause' class='jd-tb-btn'>Pause</button>"
            elif status in {"paused", "queued"}:
                btns += "<button type='submit' name='action' value='resume' class='jd-tb-btn'>Resume</button>"
            btns += (
                "<button type='submit' name='action' value='delete' class='jd-tb-btn'"
                " style='color:#e06c75;border-color:rgba(224,108,117,0.4)'>&#10005;</button>"
            )

            save_path = job.save_path or ""
            path_display = save_path.split("/")[-1] if save_path else "—"

            rows.append(
                f"<tr class='jd-child-r jd-c-{pkg_id}' style='display:none'>"
                f"<td style='padding:3px 8px 3px 28px;font-size:11px;color:var(--muted)'>"
                f"{html.escape(ep_label)}</td>"
                f"<td style='padding:3px 8px'>{pbar}</td>"
                f"<td style='font-size:11px;color:{status_color};white-space:nowrap'>"
                f"{html.escape(status_txt)}</td>"
                f"<td style='font-size:10px;color:var(--muted);white-space:nowrap'"
                f" title='{_attr(save_path)}'>{html.escape(path_display)}</td>"
                f"<td style='white-space:nowrap'>"
                f"<form method='post' action='/tasks/action' class='task-actions' style='display:flex;gap:4px'>"
                f"<input type='hidden' name='hashes' value='{task_hash}'>"
                f"{btns}</form></td>"
                f"</tr>"
            )

    body = (
        "<table class='jd-table'><thead><tr>"
        "<th style='padding-left:10px'>Package</th><th>Progress</th>"
        "<th>Status</th><th>File</th><th>Actions</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    return body, len(pkg_order), running_count, error_count


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
