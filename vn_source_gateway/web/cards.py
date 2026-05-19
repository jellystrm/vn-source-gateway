from __future__ import annotations

import html
import json
import time
from typing import Any

from vn_source_gateway.infrastructure.activity import ActivityLog


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'


def _poll_schedule_fields(config: dict[str, Any]) -> str:
    """Shared poll interval + max items row used by both Radarr and Sonarr cards."""
    return f"""
        <div class="row">
          <div class="field"><label class="field-label">Poll Interval (seconds)</label>
            <input name="poll_interval_seconds" type="number" min="10" value="{_attr(config["poll_interval_seconds"])}"></div>
          <div class="field"><label class="field-label">Max Items Per Poll</label>
            <input name="max_items_per_poll" type="number" min="1" value="{_attr(config["max_items_per_poll"])}"></div>
        </div>"""


def radarr_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="radarr">
      <div class="card-header">
        <div><div class="card-title">Radarr</div>
        <div class="card-desc">Movie manager — connection, polling schedule, and import</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Radarr URL</label>
            <input name="radarr_url" value="{_attr(config["radarr_url"])}" placeholder="http://radarr:7878"></div>
          <div class="field"><label class="field-label">Radarr API Key</label>
            <input name="radarr_api_key" type="password" value="{_attr(config["radarr_api_key"])}"></div>
        </div>
        <hr class="sep">
        {_poll_schedule_fields(config)}
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="movie_enabled" {_checked(config["movie_enabled"])}> Poll movies</label>
        </div>
      </div>
    </div>"""


def sonarr_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="sonarr">
      <div class="card-header">
        <div><div class="card-title">Sonarr</div>
        <div class="card-desc">Series manager — connection, polling schedule, and import</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Sonarr URL</label>
            <input name="sonarr_url" value="{_attr(config["sonarr_url"])}" placeholder="http://sonarr:8989"></div>
          <div class="field"><label class="field-label">Sonarr API Key</label>
            <input name="sonarr_api_key" type="password" value="{_attr(config["sonarr_api_key"])}"></div>
        </div>
        <hr class="sep">
        {_poll_schedule_fields(config)}
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="series_enabled" {_checked(config["series_enabled"])}> Poll series</label>
        </div>
      </div>
    </div>"""


def worker_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="worker">
      <div class="card-header">
        <div><div class="card-title">Worker</div>
        <div class="card-desc">State storage, retry policy, and UI settings</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Retry After (seconds)</label>
            <input name="retry_after_seconds" type="number" min="0" value="{_attr(config["retry_after_seconds"])}"></div>
          <div class="field"><label class="field-label">Job Detail Retention (hours)</label>
            <input name="job_detail_retention_hours" type="number" min="1" value="{_attr(config["job_detail_retention_hours"])}"></div>
          <div class="field"><label class="field-label">State Path</label>
            <input name="state_path" value="{_attr(config["state_path"])}"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="worker_enabled" {_checked(config["worker_enabled"])}> Worker Enabled</label>
          <label class="check-item"><input type="checkbox" name="ui_enabled" {_checked(config["ui_enabled"])}> UI Enabled</label>
        </div>
      </div>
    </div>"""


def media_managers_card(config: dict[str, Any]) -> str:
    return f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="radarr">
      {radarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Radarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Radarr</button>
      </div>
    </form>
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="sonarr">
      {sonarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Sonarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Sonarr</button>
      </div>
    </form>
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="worker">
      {worker_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Worker</button>
      </div>
    </form>"""


def sources_card(config: dict[str, Any], templates: str, source_order: str) -> str:
    return f"""
    <div class="card" id="sources">
      <div class="card-header">
        <div><div class="card-title">Sources</div><div class="card-desc">HLS source resolution order and source definitions</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Source Order (comma-separated)</label>
            <input name="source_order" value="{_attr(source_order)}" placeholder="kkphim,ophim"></div>
          <div class="field"><label class="field-label">TMDB API Key</label>
            <input name="tmdb_api_key" type="password" value="{_attr(config["tmdb_api_key"])}" placeholder="Required for TVDB → TMDB lookup"></div>
        </div>
        <hr class="sep">
        <div class="field"><label class="field-label">Direct HLS Template Sources (JSON)</label>
          <textarea name="hls_template_sources">{html.escape(templates)}</textarea>
        </div>
      </div>
    </div>"""


def output_card(config: dict[str, Any], ffmpeg_args: str) -> str:
    return f"""
    <div class="card" id="output">
      <div class="card-header">
        <div><div class="card-title">Output</div><div class="card-desc">Release exposure, ffmpeg, container, and import settings</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Default Output Mode</label>
            <select name="default_output_mode">
              {_option("strm", config["default_output_mode"])}
              {_option("download", config["default_output_mode"])}
            </select></div>
          <div class="field"><label class="field-label">Download Container</label>
            <select name="download_container">
              {_option("mkv", config["download_container"])}
              {_option("mp4", config["download_container"])}
            </select></div>
          <div class="field"><label class="field-label">Import Mode</label>
            <select name="import_mode">
              {_option("Move", config["import_mode"])}
              {_option("Copy", config["import_mode"])}
              {_option("Auto", config["import_mode"])}
            </select></div>
          <div class="field"><label class="field-label">FFmpeg Path</label>
            <input name="ffmpeg_path" value="{_attr(config["ffmpeg_path"])}"></div>
          <div class="field"><label class="field-label">FFmpeg Extra Args</label>
            <input name="ffmpeg_extra_args" value="{_attr(ffmpeg_args)}" placeholder="-user_agent,Something"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="expose_both_modes" {_checked(config["expose_both_modes"])}> Show both STRM and HLS-DL releases</label>
        </div>
      </div>
    </div>"""


def indexer_card(config: dict[str, Any]) -> str:
    torznab_url = config["public_base_url"] + "/torznab/api"
    server_labels_val = ", ".join(config.get("server_labels") or [])
    return f"""
    <div class="card" id="indexer">
      <div class="card-header">
        <div><div class="card-title">Indexer</div><div class="card-desc">Torznab API endpoint for Radarr/Sonarr</div></div>
      </div>
      <div class="card-body">
        <div class="row cols-3">
          <div class="field"><label class="field-label">Torznab URL</label>
            <input readonly value="{_attr(torznab_url)}"></div>
          <div class="field"><label class="field-label">API Key</label>
            <input name="torznab_api_key" value="{_attr(config["torznab_api_key"])}"></div>
          <div class="field"><label class="field-label">Public Base URL</label>
            <input name="public_base_url" value="{_attr(config["public_base_url"])}"></div>
        </div>
        <hr class="sep">
        <div class="row">
          <div class="field">
            <label class="field-label">Server Labels (comma-separated)</label>
            <input name="server_labels" value="{_attr(server_labels_val)}" placeholder="ViệtSub, Lồng Tiếng, Thuyết Minh">
            <span style="font-size:11px;color:var(--muted)">Labels generate separate release entries so Radarr/Sonarr can select ViệtSub vs Lồng Tiếng. Leave empty for a single undifferentiated release.</span>
          </div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="torznab_group_sources" {_checked(config.get("torznab_group_sources", False))}> Group sources — one result per episode (auto-selects best source at grab time)</label>
        </div>
      </div>
    </div>"""


def downloader_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="downloader">
      <div class="card-header">
        <div><div class="card-title">Download Client</div><div class="card-desc">qBittorrent-compatible API endpoint</div></div>
      </div>
      <div class="card-body">
        <div class="row cols-3">
          <div class="field"><label class="field-label">Host</label>
            <input name="ui_host" value="{_attr(config["ui_host"])}"></div>
          <div class="field"><label class="field-label">Port</label>
            <input name="ui_port" type="number" min="1" max="65535" value="{_attr(config["ui_port"])}"></div>
          <div class="field"><label class="field-label">Compatibility</label>
            <input readonly value="qBittorrent Web API"></div>
          <div class="field"><label class="field-label">Username</label>
            <input name="qb_username" value="{_attr(config["qb_username"])}"></div>
          <div class="field"><label class="field-label">Password</label>
            <input name="qb_password" type="password" value="{_attr(config["qb_password"])}"></div>
          <div class="field"><label class="field-label">Log Level</label>
            <select name="log_level">
              {_option("DEBUG", config["log_level"])}
              {_option("INFO", config["log_level"])}
              {_option("WARNING", config["log_level"])}
              {_option("ERROR", config["log_level"])}
            </select></div>
        </div>
      </div>
    </div>"""


def jellyfin_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="jellyfin">
      <div class="card-header">
        <div><div class="card-title">Jellyfin</div><div class="card-desc">Optional library scan integration</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">URL</label>
            <input name="jellyfin_url" value="{_attr(config["jellyfin_url"])}" placeholder="http://jellyfin:8096"></div>
          <div class="field"><label class="field-label">API Key</label>
            <input name="jellyfin_api_key" type="password" value="{_attr(config["jellyfin_api_key"])}"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="jellyfin_scan_after_strm" {_checked(config["jellyfin_scan_after_strm"])}> Scan library after STRM created</label>
        </div>
      </div>
    </div>"""


def activity_log_card() -> str:
    events = ActivityLog.get().recent(30)
    if not events:
        body = "<p style='color:var(--muted);font-size:13px'>No activity yet.</p>"
    else:
        KIND_ICON = {"search": "&#128269;", "grab": "&#128229;", "job": "&#9881;"}
        KIND_LABEL = {"search": "Search", "grab": "Grab", "job": "Job"}
        rows = []
        now = int(time.time())
        for ev in events:
            age = now - ev.ts
            if age < 60:
                age_str = f"{age}s ago"
            elif age < 3600:
                age_str = f"{age // 60}m ago"
            else:
                age_str = f"{age // 3600}h ago"
            icon = KIND_ICON.get(ev.kind, "•")
            label = KIND_LABEL.get(ev.kind, ev.kind)
            status_cls = {"ok": "running", "error": "error"}.get(ev.status, "")
            rows.append(
                f"<tr>"
                f"<td style='color:var(--muted);white-space:nowrap'>{age_str}</td>"
                f"<td><span class='badge {status_cls}'>{icon} {label}</span></td>"
                f"<td>{html.escape(ev.title)}</td>"
                f"<td style='color:var(--muted)'>{html.escape(ev.detail)}</td>"
                f"</tr>"
            )
        body = (
            "<table><thead><tr><th>When</th><th>Type</th><th>Title</th><th>Detail</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )
    return f"""
  <div class="card" id="activity-log">
    <div class="card-header">
      <div><div class="card-title">Activity Log</div>
      <div class="card-desc">Indexer searches, grabs, and job results — live pipeline view</div></div>
    </div>
    <div class="card-body">{body}</div>
  </div>"""


def download_tasks_card(tasks_html: str) -> str:
    return f"""
  <div class="card" id="download-tasks">
    <div class="card-header">
      <div><div class="card-title">Download Tasks</div><div class="card-desc">Queued, running, paused, completed, and failed gateway tasks</div></div>
    </div>
    <div class="card-body">{tasks_html}</div>
  </div>"""


def settings_card(config: dict[str, Any], ffmpeg_args: str, active_tab: str) -> str:
    tabs = [
        ("radarr", "Radarr"),
        ("sonarr", "Sonarr"),
        ("worker", "Worker"),
        ("output", "Output"),
        ("indexer", "Indexer"),
        ("downloader", "Download Client"),
        ("jellyfin", "Jellyfin"),
    ]
    valid_tabs = {key for key, _ in tabs}
    active_tab = active_tab if active_tab in valid_tabs else "radarr"
    tab_html = "\n      ".join(
        f'<a href="/settings?tab={_attr(key)}" class="settings-tab{" active" if key == active_tab else ""}">{html.escape(label)}</a>'
        for key, label in tabs
    )

    if active_tab == "radarr":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="radarr">
      {radarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Radarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Radarr</button>
      </div>
    </form>"""
    elif active_tab == "sonarr":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="sonarr">
      {sonarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Sonarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Sonarr</button>
      </div>
    </form>"""
    elif active_tab == "worker":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="worker">
      {worker_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Worker</button>
      </div>
    </form>"""
    elif active_tab == "output":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="runtime">
      {output_card(config, ffmpeg_args)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Output</button>
      </div>
    </form>"""
    elif active_tab == "indexer":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="indexer">
      {indexer_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Indexer</button>
      </div>
    </form>"""
    elif active_tab == "downloader":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="downloader">
      {downloader_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Download Client</button>
      </div>
    </form>"""
    else:
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="jellyfin">
      {jellyfin_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Jellyfin</button>
      </div>
    </form>"""

    return f"""
    <div class="settings-tabs" role="tablist">
      {tab_html}
    </div>
    {form}"""
