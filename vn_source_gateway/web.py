from __future__ import annotations

import html
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from .config import Settings, save_settings
from .download_clients import qbittorrent
from .gateway import enqueue_from_url
from .torznab import caps_response, search_response
from .worker import Worker

log = logging.getLogger(__name__)


class UiServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.httpd = ThreadingHTTPServer((host, port), _handler_class())

    def start_background(self) -> None:
        thread = threading.Thread(target=self.serve_forever, name="vn-source-gateway-ui", daemon=True)
        thread.start()

    def serve_forever(self) -> None:
        log.info("UI listening on http://%s:%s", self.host, self.port)
        self.httpd.serve_forever()


def _handler_class() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "vn-source-gateway-ui/0.1"

        def log_message(self, fmt: str, *args: object) -> None:
            log.debug("UI: " + fmt, *args)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_html(_render_page(Settings.load(), ""))
                return
            if parsed.path == "/api/config":
                self._send_json(Settings.load().to_config_dict())
                return
            if parsed.path == "/api/jobs":
                self._send_json({"jobs": qbittorrent.torrents_info(Settings.load())})
                return
            if parsed.path == "/torznab/api":
                self._handle_torznab(parse_qs(parsed.query))
                return
            if parsed.path.startswith("/grab/"):
                self._send_text("VN Source release URL. Add this through Radarr/Sonarr, not directly.\n")
                return
            if parsed.path == "/api/v2/app/version":
                self._send_text("4.6.0\n")
                return
            if parsed.path == "/api/v2/app/webapiVersion":
                self._send_text("2.8.0\n")
                return
            if parsed.path == "/api/v2/app/preferences":
                self._send_json(qbittorrent.preferences(Settings.load()))
                return
            if parsed.path == "/api/v2/app/buildInfo":
                self._send_json(qbittorrent.build_info())
                return
            if parsed.path == "/api/v2/torrents/categories":
                self._send_json(qbittorrent.categories(Settings.load()))
                return
            if parsed.path == "/api/v2/torrents/info":
                self._send_json(qbittorrent.torrents_info(Settings.load()))
                return
            if parsed.path == "/api/v2/torrents/properties":
                self._send_json({})
                return
            if parsed.path == "/api/v2/torrents/files":
                self._send_json([])
                return
            if parsed.path == "/api/v2/sync/maindata":
                self._send_json(qbittorrent.sync_maindata(Settings.load()))
                return
            if parsed.path == "/api/v2/transfer/info":
                self._send_json(qbittorrent.transfer_info())
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/save":
                form = self._read_form()
                settings = Settings.load()
                try:
                    data = _form_to_config(form, settings)
                    save_settings(data, settings.config_path)
                    self._send_html(_render_page(Settings.load(), "Saved config. Restart not required for manual Run Once; the background worker reloads on its next cycle."))
                except Exception as exc:
                    self._send_html(_render_page(settings, f"Save failed: {exc}"), HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/test":
                settings = Settings.load()
                message = _test_connections(settings)
                self._send_html(_render_page(settings, message))
                return
            if parsed.path == "/run-once":
                settings = Settings.load()
                threading.Thread(target=_run_once, args=(settings,), name="vn-source-gateway-manual-run", daemon=True).start()
                self._send_html(_render_page(settings, "Started one worker cycle in the background. Check service logs for details."))
                return
            if parsed.path == "/api/v2/auth/login":
                self._handle_qbit_login()
                return
            if parsed.path == "/api/v2/torrents/add":
                self._handle_qbit_add()
                return
            if parsed.path == "/api/v2/torrents/delete":
                form = self._read_form()
                qbittorrent.delete(Settings.load(), form.get("hashes", ""))
                self._send_text("Ok.\n")
                return
            if parsed.path == "/api/v2/torrents/pause":
                form = self._read_form()
                qbittorrent.pause(Settings.load(), form.get("hashes", ""), True)
                self._send_text("Ok.\n")
                return
            if parsed.path == "/api/v2/torrents/resume":
                form = self._read_form()
                qbittorrent.pause(Settings.load(), form.get("hashes", ""), False)
                self._send_text("Ok.\n")
                return
            if parsed.path in {
                "/api/v2/torrents/setCategory",
                "/api/v2/torrents/createCategory",
                "/api/v2/torrents/editCategory",
                "/api/v2/torrents/removeCategories",
                "/api/v2/torrents/addTags",
                "/api/v2/torrents/removeTags",
            }:
                self._send_text("Ok.\n")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def _handle_torznab(self, query: dict[str, list[str]]) -> None:
            settings = Settings.load()
            api_key = query.get("apikey", [""])[0]
            if settings.torznab_api_key and api_key != settings.torznab_api_key:
                self.send_error(HTTPStatus.UNAUTHORIZED)
                return
            body = caps_response() if query.get("t", ["search"])[0] == "caps" else search_response(settings, query)
            self._send_xml(body)

        def _handle_qbit_login(self) -> None:
            settings = Settings.load()
            form = self._read_form()
            username = form.get("username", "")
            password = form.get("password", "")
            if username != settings.qb_username or password != settings.qb_password:
                self._send_text("Fails.\n", HTTPStatus.FORBIDDEN)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Set-Cookie", "SID=vn-source; HttpOnly; path=/")
            self.end_headers()
            self.wfile.write(b"Ok.\n")

        def _handle_qbit_add(self) -> None:
            settings = Settings.load()
            form = self._read_form()
            urls = form.get("urls", "")
            category = form.get("category", "vn-source")
            paused = form.get("paused", "").lower() in {"true", "1", "yes", "on"}
            added = []
            for url in urls.replace("\r", "\n").split("\n"):
                url = url.strip()
                if not url:
                    continue
                job = enqueue_from_url(settings, url, category=category, paused=paused)
                added.append(job.job_id)
            if not added:
                self.send_error(HTTPStatus.BAD_REQUEST, "No supported urls field")
                return
            self._send_text("Ok.\n")

        def _read_form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/form-data"):
                return _parse_multipart(body, content_type)
            raw = body.decode("utf-8")
            parsed = parse_qs(raw, keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}

        def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: Any) -> None:
            encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_xml(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_text(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _parse_multipart(body: bytes, content_type: str) -> dict[str, str]:
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


def _run_once(settings: Settings) -> None:
    try:
        Worker(settings).run_once()
    except Exception:
        log.exception("Manual worker cycle failed")


def _test_connections(settings: Settings) -> str:
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


def _form_to_config(form: dict[str, str], current: Settings) -> dict[str, Any]:
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


def _render_page(settings: Settings, message: str) -> str:
    config = settings.to_config_dict()
    templates = json.dumps(config["hls_template_sources"], indent=2)
    source_order = ",".join(config["source_order"])
    ffmpeg_args = ",".join(config["ffmpeg_extra_args"])
    status = _status(settings)
    msg_html = f'<div class="notice">{html.escape(message)}</div>' if message else ""
    jobs_html = _jobs_html(settings)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>vn-source-gateway</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #5d6875;
      --line: #d8dde5;
      --accent: #126d5b;
      --danger: #9f2f3d;
      --input: #ffffff;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101418;
        --panel: #171d23;
        --text: #ecf1f5;
        --muted: #a9b4bf;
        --line: #2d3640;
        --accent: #4bb69e;
        --danger: #ff7d8d;
        --input: #11171d;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    .wrap {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
    }}
    .top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 72px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    main {{
      padding: 24px 0 40px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .wide {{ grid-column: 1 / -1; }}
    h2 {{
      margin: 0 0 14px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    label {{
      display: block;
      margin: 12px 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}
    input, textarea, select {{
      display: block;
      width: 100%;
      margin-top: 6px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--input);
      color: var(--text);
      padding: 10px 11px;
      font: inherit;
      font-size: 14px;
    }}
    textarea {{
      min-height: 170px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    .checks {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .checks label {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: var(--text);
    }}
    .checks input {{
      width: auto;
      margin: 0;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 16px;
    }}
    button {{
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 10px 14px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }}
    button.secondary {{
      background: transparent;
      color: var(--accent);
    }}
    .status {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
    }}
    .metric b {{
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .metric span {{
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
      font-weight: 700;
    }}
    .notice {{
      border: 1px solid var(--accent);
      color: var(--text);
      background: color-mix(in srgb, var(--accent) 12%, transparent);
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      color: var(--muted);
      font-weight: 700;
    }}
    code {{
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    @media (max-width: 820px) {{
      .grid, .status {{ grid-template-columns: 1fr; }}
      .top {{ align-items: flex-start; flex-direction: column; padding: 16px 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap top">
      <div>
        <h1>vn-source-gateway</h1>
        <code>{html.escape(settings.config_path)}</code>
      </div>
      <form method="post" action="/run-once">
        <button type="submit" class="secondary">Run Once</button>
      </form>
    </div>
  </header>
  <main class="wrap">
    {msg_html}
    <div class="status">
      <div class="metric"><b>Radarr</b><span>{html.escape(status["radarr"])}</span></div>
      <div class="metric"><b>Sonarr</b><span>{html.escape(status["sonarr"])}</span></div>
      <div class="metric"><b>Sources</b><span>{html.escape(",".join(settings.source_order))}</span></div>
      <div class="metric"><b>Downloads</b><span>{html.escape(settings.download_root)}</span></div>
    </div>
    <form method="post" action="/save">
      <div class="grid">
        <section class="panel">
          <h2>Radarr</h2>
          <label>URL
            <input name="radarr_url" value="{_attr(config["radarr_url"])}" placeholder="http://radarr:7878">
          </label>
          <label>API Key
            <input name="radarr_api_key" type="password" value="{_attr(config["radarr_api_key"])}">
          </label>
        </section>
        <section class="panel">
          <h2>Sonarr</h2>
          <label>URL
            <input name="sonarr_url" value="{_attr(config["sonarr_url"])}" placeholder="http://sonarr:8989">
          </label>
          <label>API Key
            <input name="sonarr_api_key" type="password" value="{_attr(config["sonarr_api_key"])}">
          </label>
        </section>
        <section class="panel">
          <h2>Worker</h2>
          <label>Download Root
            <input name="download_root" value="{_attr(config["download_root"])}">
          </label>
          <label>Movie STRM Library Path
            <input name="movie_strm_root" value="{_attr(config["movie_strm_root"])}">
          </label>
          <label>Series STRM Library Path
            <input name="series_strm_root" value="{_attr(config["series_strm_root"])}">
          </label>
          <label>State Path
            <input name="state_path" value="{_attr(config["state_path"])}">
          </label>
          <label>Poll Interval Seconds
            <input name="poll_interval_seconds" type="number" min="10" value="{_attr(config["poll_interval_seconds"])}">
          </label>
          <label>Max Items Per Poll
            <input name="max_items_per_poll" type="number" min="1" value="{_attr(config["max_items_per_poll"])}">
          </label>
          <label>Retry After Seconds
            <input name="retry_after_seconds" type="number" min="0" value="{_attr(config["retry_after_seconds"])}">
          </label>
          <div class="checks">
            <label><input type="checkbox" name="movie_enabled" {_checked(config["movie_enabled"])}> Movies</label>
            <label><input type="checkbox" name="series_enabled" {_checked(config["series_enabled"])}> Series</label>
            <label><input type="checkbox" name="ui_enabled" {_checked(config["ui_enabled"])}> UI</label>
          </div>
        </section>
        <section class="panel">
          <h2>Runtime</h2>
          <label>Source Order
            <input name="source_order" value="{_attr(source_order)}">
          </label>
          <label>Default Output Mode
            <select name="default_output_mode">
              {_option("strm", config["default_output_mode"])}
              {_option("download", config["default_output_mode"])}
            </select>
          </label>
          <div class="checks">
            <label><input type="checkbox" name="expose_both_modes" {_checked(config["expose_both_modes"])}> Show STRM and HLS-DL releases</label>
          </div>
          <label>Download Container
            <select name="download_container">
              {_option("mkv", config["download_container"])}
              {_option("mp4", config["download_container"])}
            </select>
          </label>
          <label>Import Mode
            <select name="import_mode">
              {_option("Move", config["import_mode"])}
              {_option("Copy", config["import_mode"])}
              {_option("Auto", config["import_mode"])}
            </select>
          </label>
          <label>FFmpeg Path
            <input name="ffmpeg_path" value="{_attr(config["ffmpeg_path"])}">
          </label>
          <label>FFmpeg Extra Args
            <input name="ffmpeg_extra_args" value="{_attr(ffmpeg_args)}" placeholder="-user_agent,Something">
          </label>
          <label>Log Level
            <select name="log_level">
              {_option("DEBUG", config["log_level"])}
              {_option("INFO", config["log_level"])}
              {_option("WARNING", config["log_level"])}
              {_option("ERROR", config["log_level"])}
            </select>
          </label>
          <label>UI Host
            <input name="ui_host" value="{_attr(config["ui_host"])}">
          </label>
          <label>UI Port
            <input name="ui_port" type="number" min="1" max="65535" value="{_attr(config["ui_port"])}">
          </label>
        </section>
        <section class="panel">
          <h2>Indexer</h2>
          <label>Torznab URL
            <input readonly value="{_attr(config["public_base_url"] + "/torznab/api")}">
          </label>
          <label>Torznab API Key
            <input name="torznab_api_key" value="{_attr(config["torznab_api_key"])}">
          </label>
          <label>Public Base URL
            <input name="public_base_url" value="{_attr(config["public_base_url"])}">
          </label>
        </section>
        <section class="panel">
          <h2>Downloader</h2>
          <label>Compatibility
            <input readonly value="qBittorrent Web API">
          </label>
          <label>Username
            <input name="qb_username" value="{_attr(config["qb_username"])}">
          </label>
          <label>Password
            <input name="qb_password" type="password" value="{_attr(config["qb_password"])}">
          </label>
        </section>
        <section class="panel wide">
          <h2>Jellyfin</h2>
          <label>URL
            <input name="jellyfin_url" value="{_attr(config["jellyfin_url"])}" placeholder="http://jellyfin:8096">
          </label>
          <label>API Key
            <input name="jellyfin_api_key" type="password" value="{_attr(config["jellyfin_api_key"])}">
          </label>
          <div class="checks">
            <label><input type="checkbox" name="jellyfin_scan_after_strm" {_checked(config["jellyfin_scan_after_strm"])}> Scan after STRM created</label>
          </div>
        </section>
        <section class="panel wide">
          <h2>Direct HLS Template Sources</h2>
          <label>JSON
            <textarea name="hls_template_sources">{html.escape(templates)}</textarea>
          </label>
        </section>
        <section class="panel wide">
          <h2>Jobs</h2>
          {jobs_html}
        </section>
      </div>
      <div class="actions">
        <button type="submit">Save Config</button>
        <button type="submit" formaction="/test" class="secondary">Test Connections</button>
      </div>
    </form>
  </main>
</body>
</html>"""


def _status(settings: Settings) -> dict[str, str]:
    return {
        "radarr": "configured" if settings.radarr_url and settings.radarr_api_key else "missing config",
        "sonarr": "configured" if settings.sonarr_url and settings.sonarr_api_key else "missing config",
    }


def _jobs_html(settings: Settings) -> str:
    try:
        jobs = qbittorrent.torrents_info(settings)
    except Exception as exc:
        return f"<p>Could not load jobs: {html.escape(str(exc))}</p>"
    if not jobs:
        return "<p>No jobs yet.</p>"
    rows = []
    for job in sorted(jobs, key=lambda item: item.get("added_on", 0), reverse=True)[:25]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(job.get('name', '')))}</td>"
            f"<td>{html.escape(str(job.get('state', '')))}</td>"
            f"<td>{int(float(job.get('progress', 0)) * 100)}%</td>"
            f"<td>{html.escape(str(job.get('save_path', '')))}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Name</th><th>State</th><th>Progress</th><th>Path</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'
