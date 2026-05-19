from __future__ import annotations

import html
import json
from typing import Any


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'


def worker_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="worker">
      <div class="card-header">
        <div><div class="card-title">Worker</div>
        <div class="card-desc">Polling mode — gateway calls Radarr/Sonarr to find missing items and resolves them automatically</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Radarr URL</label>
            <input name="radarr_url" value="{_attr(config["radarr_url"])}" placeholder="http://radarr:7878"></div>
          <div class="field"><label class="field-label">Radarr API Key</label>
            <input name="radarr_api_key" type="password" value="{_attr(config["radarr_api_key"])}"></div>
          <div class="field"><label class="field-label">Sonarr URL</label>
            <input name="sonarr_url" value="{_attr(config["sonarr_url"])}" placeholder="http://sonarr:8989"></div>
          <div class="field"><label class="field-label">Sonarr API Key</label>
            <input name="sonarr_api_key" type="password" value="{_attr(config["sonarr_api_key"])}"></div>
          <div class="field"><label class="field-label">Poll Interval (seconds)</label>
            <input name="poll_interval_seconds" type="number" min="10" value="{_attr(config["poll_interval_seconds"])}"></div>
          <div class="field"><label class="field-label">Max Items Per Poll</label>
            <input name="max_items_per_poll" type="number" min="1" value="{_attr(config["max_items_per_poll"])}"></div>
          <div class="field"><label class="field-label">Retry After (seconds)</label>
            <input name="retry_after_seconds" type="number" min="0" value="{_attr(config["retry_after_seconds"])}"></div>
          <div class="field"><label class="field-label">State Path</label>
            <input name="state_path" value="{_attr(config["state_path"])}"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="movie_enabled" {_checked(config["movie_enabled"])}> Poll movies</label>
          <label class="check-item"><input type="checkbox" name="series_enabled" {_checked(config["series_enabled"])}> Poll series</label>
          <label class="check-item"><input type="checkbox" name="ui_enabled" {_checked(config["ui_enabled"])}> UI Enabled</label>
        </div>
      </div>
    </div>"""


def sources_card(config: dict[str, Any], templates: str, source_order: str, ffmpeg_args: str) -> str:
    return f"""
    <div class="card" id="sources">
      <div class="card-header">
        <div><div class="card-title">Sources</div><div class="card-desc">HLS source resolution and output settings</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Source Order (comma-separated)</label>
            <input name="source_order" value="{_attr(source_order)}" placeholder="kkphim,ophim"></div>
          <div class="field"><label class="field-label">TMDB API Key</label>
            <input name="tmdb_api_key" type="password" value="{_attr(config["tmdb_api_key"])}" placeholder="Required for TVDB → TMDB lookup"></div>
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
        <div class="checks" style="margin-bottom:18px">
          <label class="check-item"><input type="checkbox" name="expose_both_modes" {_checked(config["expose_both_modes"])}> Show both STRM and HLS-DL releases</label>
        </div>
        <div class="field"><label class="field-label">Direct HLS Template Sources (JSON)</label>
          <textarea name="hls_template_sources">{html.escape(templates)}</textarea>
        </div>
      </div>
    </div>"""


def indexer_card(config: dict[str, Any]) -> str:
    torznab_url = config["public_base_url"] + "/torznab/api"
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


def jobs_card(jobs_html: str) -> str:
    return f"""
  <div class="card" id="jobs" style="margin-top:14px">
    <div class="card-header">
      <div><div class="card-title">Jobs</div><div class="card-desc">Recent gateway jobs</div></div>
    </div>
    <div class="card-body">{jobs_html}</div>
  </div>"""
