from __future__ import annotations

import html
import json
import logging
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from vn_source_gateway.application.grab_service import encode_release, enqueue_from_url
from vn_source_gateway.application.worker_service import Worker
from vn_source_gateway.interfaces.download_clients import qbittorrent
from vn_source_gateway.interfaces.indexers.torznab import build_releases, caps_response, search_response
from vn_source_gateway.infrastructure.config import Settings, save_settings

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
                self.send_response(HTTPStatus.FOUND)
                self.send_header("Location", "/indexer")
                self.end_headers()
                return
            if parsed.path in {"/indexer", "/download-client", "/sources", "/settings"}:
                self._send_html(_render_page(Settings.load(), "", page=parsed.path.strip("/") or "indexer"))
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
                    self._send_html(_render_page(Settings.load(), "Saved settings. The background worker reloads on its next cycle.", page="settings"))
                except Exception as exc:
                    self._send_html(_render_page(settings, f"Save failed: {exc}", page="settings"), HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/test":
                settings = Settings.load()
                message = _test_connections(settings)
                self._send_html(_render_page(settings, message, page="settings"))
                return
            if parsed.path == "/run-once":
                settings = Settings.load()
                threading.Thread(target=_run_once, args=(settings,), name="vn-source-gateway-manual-run", daemon=True).start()
                self._send_html(_render_page(settings, "Started one worker cycle in the background. Check service logs for details.", page="settings"))
                return
            if parsed.path == "/indexer/search":
                settings = Settings.load()
                form = self._read_form()
                self._send_html(_render_page(settings, "", page="indexer", indexer_results=_indexer_results_html(settings, form)))
                return
            if parsed.path == "/resolver/preview":
                settings = Settings.load()
                form = self._read_form()
                self._send_html(_render_page(settings, "", page="sources", resolver_results=_resolver_preview_html(settings, form)))
                return
            if parsed.path == "/sources/add":
                settings = Settings.load()
                form = self._read_form()
                try:
                    _add_source(settings, form)
                    self._send_html(_render_page(Settings.load(), "Source added.", page="sources"))
                except Exception as exc:
                    self._send_html(_render_page(settings, f"Add source failed: {exc}", page="sources"), HTTPStatus.BAD_REQUEST)
                return
            if parsed.path == "/sources/delete":
                settings = Settings.load()
                form = self._read_form()
                _delete_source(settings, form.get("name", ""))
                self._send_html(_render_page(Settings.load(), "Source removed.", page="sources"))
                return
            if parsed.path == "/jobs/action":
                settings = Settings.load()
                form = self._read_form()
                hashes = form.get("hashes", "")
                action = form.get("action", "")
                if action == "pause":
                    qbittorrent.pause(settings, hashes, True)
                elif action == "resume":
                    qbittorrent.pause(settings, hashes, False)
                elif action == "delete":
                    qbittorrent.delete(settings, hashes)
                self._send_html(_render_page(Settings.load(), f"Task action completed: {action or 'none'}.", page="download-client"))
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
            return {
                key: "|".join(values) if key == "hashes" else values[-1] if values else ""
                for key, values in parsed.items()
            }

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

    rules_raw = form.get("resolver_rules", "").strip()
    resolver_rules = json.loads(rules_raw) if rules_raw else []
    if not isinstance(resolver_rules, list):
        raise ValueError("Resolver rules must be a JSON array")

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
        "resolver_rules": resolver_rules,
    }


def _add_source(settings: Settings, form: dict[str, str]) -> None:
    name = form.get("name", "").strip()
    if not name:
        raise ValueError("source name is required")

    source_type = form.get("type", "template").strip()
    movie_url = form.get("movie_url", "").strip()
    series_url = form.get("series_url", "").strip()
    base_url = form.get("base_url", "").strip()
    if source_type == "phimapi" and not base_url:
        raise ValueError("base URL is required")
    if source_type != "phimapi" and not movie_url and not series_url:
        raise ValueError("movie URL or series URL is required")

    headers_raw = form.get("headers", "").strip()
    headers = json.loads(headers_raw) if headers_raw else {}
    if not isinstance(headers, dict):
        raise ValueError("headers must be a JSON object")

    source: dict[str, Any] = {"name": name, "type": source_type}
    if headers:
        source["headers"] = {str(key): str(value) for key, value in headers.items()}
    if source_type == "phimapi":
        source["base_url"] = base_url.rstrip("/")
    elif source_type == "resolver":
        if movie_url:
            source["movie_resolver_url_template"] = movie_url
        if series_url:
            source["series_resolver_url_template"] = series_url
    else:
        if movie_url:
            source["movie_url_template"] = movie_url
        if series_url:
            source["series_url_template"] = series_url

    data = settings.to_config_dict()
    templates = [item for item in settings.hls_template_sources if item.get("name") != name]
    templates.append(source)
    data["hls_template_sources"] = templates
    if name not in data["source_order"]:
        data["source_order"] = [*data["source_order"], name]
    save_settings(data, settings.config_path)


def _delete_source(settings: Settings, name: str) -> None:
    name = name.strip()
    if not name:
        return
    data = settings.to_config_dict()
    data["source_order"] = [source for source in settings.source_order if source != name]
    data["hls_template_sources"] = [
        source for source in settings.hls_template_sources if source.get("name") != name
    ]
    save_settings(data, settings.config_path)


def _render_page(
    settings: Settings,
    message: str,
    page: str = "indexer",
    indexer_results: str = "",
    resolver_results: str = "",
) -> str:
    config = settings.to_config_dict()
    templates = json.dumps(config["hls_template_sources"], indent=2)
    resolver_rules = json.dumps(config["resolver_rules"], indent=2)
    source_order = ",".join(config["source_order"])
    ffmpeg_args = ",".join(config["ffmpeg_extra_args"])
    msg_html = f'<div class="notice">{html.escape(message)}</div>' if message else ""
    jobs_html = _jobs_html(settings, selectable=True)
    indexer_results = indexer_results or "<p>No manual search yet.</p>"
    resolver_results = resolver_results or "<p>No resolver preview yet.</p>"
    sources_html = _sources_html(settings)
    page = page if page in {"indexer", "download-client", "sources", "settings"} else "indexer"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>vn-source-gateway</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #1b1b1b;
      --panel: #202020;
      --panel-soft: #181818;
      --top: #252525;
      --sidebar: #2a2a2a;
      --sidebar-active: #333333;
      --text: #e7edf3;
      --muted: #9aa7b4;
      --line: #353535;
      --accent: #f5c12f;
      --accent-strong: #f5c12f;
      --danger: #e05f5f;
      --input: #161616;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
    }}
    .app {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }}
    .sidebar {{
      background: var(--sidebar);
      border-right: 1px solid var(--line);
      min-height: 100vh;
    }}
    .brand {{
      display: flex;
      align-items: center;
      height: 74px;
      padding: 0 34px;
      color: var(--accent);
      font-size: 34px;
      font-weight: 900;
      letter-spacing: 0;
    }}
    .brand span {{
      color: #f0f0f0;
      font-size: 13px;
      font-weight: 700;
      margin-left: 8px;
      margin-top: 12px;
    }}
    .main {{
      min-width: 0;
      background: var(--bg);
    }}
    .topbar {{
      height: 74px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 0 28px;
      background: var(--top);
      border-bottom: 1px solid var(--line);
    }}
    .search {{
      display: flex;
      align-items: center;
      gap: 10px;
      width: min(360px, 45vw);
      color: var(--muted);
    }}
    .search input {{
      border: 0;
      border-bottom: 1px solid #d8d8d8;
      border-radius: 0;
      background: transparent;
      padding: 6px 0;
      color: var(--text);
    }}
    .top-icons {{
      display: flex;
      align-items: center;
      gap: 14px;
      color: #f0f0f0;
      font-weight: 800;
    }}
    .heart {{
      color: #e53f5b;
    }}
    main {{
      padding: 0 28px 36px;
    }}
    nav {{
      padding: 12px 0 28px;
    }}
    nav a {{
      display: flex;
      align-items: center;
      min-height: 62px;
      padding: 0 34px;
      color: #e0e0e0;
      text-decoration: none;
      font-size: 20px;
      font-weight: 700;
    }}
    nav a:hover {{
      background: var(--sidebar-active);
      color: var(--accent);
    }}
    nav a.active {{
      background: var(--sidebar-active);
      color: var(--accent);
    }}
    .nav-icon {{
      display: inline-flex;
      width: 32px;
      color: inherit;
      font-size: 18px;
    }}
    .stack {{
      display: grid;
      gap: 14px;
      padding-top: 0;
    }}
    .page-section {{
      display: none;
    }}
    .page-indexer #indexer,
    .page-download-client #download-client,
    .page-sources #sources,
    .page-settings #settings-form {{
      display: block;
    }}
    .section {{
      border: 0;
      background: transparent;
      border-radius: 0;
      overflow: hidden;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 0;
      padding: 34px 0 18px;
    }}
    .section-head p {{
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0;
      padding: 0;
      background: var(--panel);
      border-top: 1px solid var(--line);
    }}
    .panel {{
      border-bottom: 1px solid var(--line);
      padding: 18px 28px;
    }}
    .panel:last-child {{ border-bottom: 0; }}
    .wide {{ grid-column: 1 / -1; }}
    h2 {{
      margin: 0;
      display: inline-block;
      border-bottom: 1px solid #d0d0d0;
      padding-bottom: 3px;
      font-size: 30px;
      font-weight: 500;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
      color: var(--text);
    }}
    label {{
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      align-items: center;
      gap: 14px;
      margin: 10px 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }}
    input, textarea, select {{
      display: block;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 2px;
      background: var(--input);
      color: var(--text);
      padding: 8px 10px;
      font: inherit;
      font-size: 14px;
    }}
    input[readonly] {{
      color: var(--muted);
      background: var(--panel-soft);
    }}
    textarea {{
      min-height: 170px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      line-height: 1.45;
    }}
    .checks {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      margin: 12px 0 0 220px;
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
      padding: 14px 16px 16px;
      border-top: 1px solid var(--line);
      background: var(--panel);
    }}
    button {{
      border: 1px solid var(--accent);
      border-radius: 4px;
      background: var(--accent);
      color: #081016;
      padding: 8px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{
      background: transparent;
      color: var(--accent);
    }}
    button.danger {{
      border-color: var(--danger);
      background: transparent;
      color: var(--danger);
    }}
    .notice {{
      border: 1px solid var(--accent);
      color: var(--text);
      background: color-mix(in srgb, var(--accent) 12%, transparent);
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 16px;
      margin-top: 18px;
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
    .task-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 14px 16px 16px;
      border-top: 1px solid var(--line);
    }}
    .task-table {{
      padding: 16px;
      overflow-x: auto;
    }}
    .source-table {{
      overflow-x: auto;
    }}
    .inline-form {{
      display: inline;
    }}
    .mini-button {{
      padding: 4px 8px;
      font-size: 12px;
    }}
    .select-cell {{
      width: 34px;
    }}
    .select-cell input {{
      width: auto;
      margin: 0;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    @media (max-width: 820px) {{
      .app {{ grid-template-columns: 1fr; }}
      .sidebar {{ min-height: auto; }}
      nav a {{ min-height: 48px; font-size: 16px; }}
      label {{ grid-template-columns: 1fr; gap: 6px; }}
      .checks {{ margin-left: 0; }}
      .topbar {{ padding: 12px 16px; height: auto; align-items: flex-start; flex-direction: column; }}
      main {{ padding: 0 16px 28px; }}
    }}
  </style>
</head>
<body class="page-{_attr(page)}">
  <div class="app">
    <aside class="sidebar">
      <div class="brand">VNS<span>GATEWAY</span></div>
      <nav>
        <a href="/indexer" class="{_active(page, "indexer")}"><span class="nav-icon">▶</span>Indexer</a>
        <a href="/download-client" class="{_active(page, "download-client")}"><span class="nav-icon">▦</span>Download Client</a>
        <a href="/sources" class="{_active(page, "sources")}"><span class="nav-icon">◆</span>Sources</a>
        <a href="/settings" class="{_active(page, "settings")}"><span class="nav-icon">⚙</span>Settings</a>
      </nav>
    </aside>
    <div class="main">
      <div class="topbar">
        <div class="search"><span>⌕</span><input placeholder="Search"></div>
        <div class="top-icons"><span class="heart">♥</span><span>A↔</span><span>●</span></div>
      </div>
      <main>
        {msg_html}
      <div class="stack">
        <section class="section page-section" id="indexer">
          <div class="section-head">
            <div>
              <h2>Indexer</h2>
              <p>Manage search output exposed through the Torznab indexer.</p>
            </div>
          </div>
          <form method="post" action="/indexer/search">
            <div class="grid">
              <div class="panel">
                <h3>Manual Search</h3>
                <label>Type
                  <select name="t">
                    <option value="movie">Movie</option>
                    <option value="tvsearch">TV Episode</option>
                  </select>
                </label>
                <label>Query
                  <input name="q" placeholder="Title">
                </label>
                <label>Year
                  <input name="year" type="number" placeholder="2026">
                </label>
                <label>TMDB ID
                  <input name="tmdbid" inputmode="numeric">
                </label>
                <label>TVDB ID
                  <input name="tvdbid" inputmode="numeric">
                </label>
                <label>Season / Episode
                  <input name="season_ep" placeholder="1x02">
                </label>
              </div>
              <div class="panel">
                <h3>Generated Releases</h3>
                {indexer_results}
              </div>
            </div>
            <div class="actions">
              <button type="submit">Search Releases</button>
            </div>
          </form>
        </section>

        <section class="section page-section" id="download-client">
          <div class="section-head">
            <div>
              <h2>Download Client</h2>
              <p>Manage queued, running, completed, and failed grab jobs.</p>
            </div>
          </div>
          <form method="post" action="/jobs/action">
            <div class="task-table">
              {jobs_html}
            </div>
            <div class="task-actions">
              <button type="submit" name="action" value="resume" class="secondary">Resume</button>
              <button type="submit" name="action" value="pause" class="secondary">Pause</button>
              <button type="submit" name="action" value="delete" class="danger">Delete</button>
            </div>
          </form>
        </section>

        <section class="section page-section" id="sources">
          <div class="section-head">
            <div>
              <h2>Sources</h2>
              <p>Manage source providers and preview the resolver rules used to turn Radarr/Sonarr input into HLS links.</p>
            </div>
          </div>
          <div class="grid">
            <div class="panel">
              <h3>Configured Sources</h3>
              {sources_html}
            </div>
            <div class="panel">
              <h3>Add / Update Source</h3>
              <form method="post" action="/sources/add">
                <label>Name
                  <input name="name" placeholder="vidsrc">
                </label>
                <label>Type
                  <select name="type">
                    <option value="phimapi">PhimAPI Compatible</option>
                    <option value="template">Direct HLS Template</option>
                    <option value="resolver">Resolver Endpoint</option>
                  </select>
                </label>
                <label>Base URL
                  <input name="base_url" placeholder="https://phimapi.com">
                </label>
                <label>Movie URL
                  <input name="movie_url" placeholder="https://resolver/movie/{{tmdb_id}}.m3u8">
                </label>
                <label>Series URL
                  <input name="series_url" placeholder="https://resolver/tv/{{tvdb_id}}/s{{season:02d}}e{{episode:02d}}.m3u8">
                </label>
                <label>Headers JSON
                  <textarea name="headers" placeholder='{{"Referer":"https://example/"}}'></textarea>
                </label>
                <div class="actions">
                  <button type="submit">Save Source</button>
                </div>
              </form>
            </div>
            <div class="panel wide">
              <h3>Resolver Preview</h3>
              <form method="post" action="/resolver/preview">
                <label>Type
                  <select name="kind">
                    <option value="movie">Movie</option>
                    <option value="episode">Episode</option>
                  </select>
                </label>
                <label>Title
                  <input name="title" placeholder="Original title from Radarr/Sonarr">
                </label>
                <div class="actions">
                  <button type="submit">Preview Resolver</button>
                </div>
              </form>
              {resolver_results}
            </div>
          </div>
        </section>

        <form method="post" action="/save" class="stack page-section" id="settings-form">
          <section class="section" id="settings">
            <div class="section-head">
              <div>
                <h2>Settings</h2>
                <p>Configuration for indexer, download client, resolver, sources, Radarr/Sonarr, output, and system.</p>
              </div>
            </div>
            <div class="grid">
              <div class="panel">
                <h3>Indexer</h3>
                <label>Indexer URL
                  <input readonly class="mono" value="{_attr(config["public_base_url"] + "/torznab/api")}">
                </label>
                <label>API Key
                  <input name="torznab_api_key" value="{_attr(config["torznab_api_key"])}">
                </label>
                <label>Public Base URL
                  <input name="public_base_url" value="{_attr(config["public_base_url"])}">
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
              </div>
              <div class="panel">
                <h3>Download Client</h3>
                <label>Host
                  <input readonly value="{_attr(settings.ui_host)}">
                </label>
                <label>Port
                  <input readonly value="{_attr(settings.ui_port)}">
                </label>
                <label>Category
                  <input readonly value="vn-source">
                </label>
                <label>Username
                  <input name="qb_username" value="{_attr(config["qb_username"])}">
                </label>
                <label>Password
                  <input name="qb_password" type="password" value="{_attr(config["qb_password"])}">
                </label>
              </div>
              <div class="panel">
                <h3>Sources / Resolver</h3>
                <label>Source Order
                  <input name="source_order" value="{_attr(source_order)}" placeholder="kkphim,ophim,vidsrc,embed">
                </label>
                <label>Resolver Rules
                  <textarea name="resolver_rules" placeholder='[{{"kind":"movie","match":"Original Title","title":"Vietnamese Title","source_order":["kkphim"]}}]'>{html.escape(resolver_rules)}</textarea>
                </label>
                <label>JSON
                  <textarea name="hls_template_sources">{html.escape(templates)}</textarea>
                </label>
              </div>
              <div class="panel">
                <h3>Radarr</h3>
                <label>URL
                  <input name="radarr_url" value="{_attr(config["radarr_url"])}" placeholder="http://radarr:7878">
                </label>
                <label>API Key
                  <input name="radarr_api_key" type="password" value="{_attr(config["radarr_api_key"])}">
                </label>
              </div>
              <div class="panel">
                <h3>Sonarr</h3>
                <label>URL
                  <input name="sonarr_url" value="{_attr(config["sonarr_url"])}" placeholder="http://sonarr:8989">
                </label>
                <label>API Key
                  <input name="sonarr_api_key" type="password" value="{_attr(config["sonarr_api_key"])}">
                </label>
              </div>
              <div class="panel wide">
                <h3>Radarr / Sonarr Polling</h3>
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
                </div>
              </div>
              <div class="panel">
                <h3>Output Paths</h3>
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
              </div>
              <div class="panel">
                <h3>ffmpeg</h3>
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
              </div>
              <div class="panel wide">
                <h3>Jellyfin</h3>
                <label>URL
                  <input name="jellyfin_url" value="{_attr(config["jellyfin_url"])}" placeholder="http://jellyfin:8096">
                </label>
                <label>API Key
                  <input name="jellyfin_api_key" type="password" value="{_attr(config["jellyfin_api_key"])}">
                </label>
                <div class="checks">
                  <label><input type="checkbox" name="jellyfin_scan_after_strm" {_checked(config["jellyfin_scan_after_strm"])}> Scan after STRM created</label>
                </div>
              </div>
              <div class="panel">
                <h3>UI</h3>
                <label>UI Host
                  <input name="ui_host" value="{_attr(config["ui_host"])}">
                </label>
                <label>UI Port
                  <input name="ui_port" type="number" min="1" max="65535" value="{_attr(config["ui_port"])}">
                </label>
                <div class="checks">
                  <label><input type="checkbox" name="ui_enabled" {_checked(config["ui_enabled"])}> UI enabled</label>
                </div>
              </div>
              <div class="panel">
                <h3>Logs</h3>
                <label>Log Level
                  <select name="log_level">
                    {_option("DEBUG", config["log_level"])}
                    {_option("INFO", config["log_level"])}
                    {_option("WARNING", config["log_level"])}
                    {_option("ERROR", config["log_level"])}
                  </select>
                </label>
              </div>
            </div>
            <div class="actions">
              <button type="submit">Save Settings</button>
              <button type="submit" formaction="/test" class="secondary">Test Connections</button>
              <button type="submit" formaction="/run-once" class="secondary">Run Polling Once</button>
            </div>
          </section>
        </form>
      </div>
      </main>
    </div>
  </div>
</body>
</html>"""


def _jobs_html(settings: Settings, selectable: bool = False) -> str:
    try:
        jobs = qbittorrent.torrents_info(settings)
    except Exception as exc:
        return f"<p>Could not load jobs: {html.escape(str(exc))}</p>"
    if not jobs:
        return "<p>No jobs yet.</p>"
    rows = []
    for job in sorted(jobs, key=lambda item: item.get("added_on", 0), reverse=True)[:25]:
        select_cell = ""
        if selectable:
            select_cell = f'<td class="select-cell"><input type="checkbox" name="hashes" value="{_attr(job.get("hash", ""))}"></td>'
        rows.append(
            "<tr>"
            f"{select_cell}"
            f"<td>{html.escape(str(job.get('name', '')))}</td>"
            f"<td>{html.escape(str(job.get('state', '')))}</td>"
            f"<td>{int(float(job.get('progress', 0)) * 100)}%</td>"
            f"<td>{html.escape(str(job.get('save_path', '')))}</td>"
            "</tr>"
        )
    checkbox_header = '<th class="select-cell"></th>' if selectable else ""
    return (
        "<table><thead><tr>"
        f"{checkbox_header}<th>Name</th><th>State</th><th>Progress</th><th>Path</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _indexer_results_html(settings: Settings, form: dict[str, str]) -> str:
    query = _indexer_form_to_query(form)
    releases = build_releases(settings, query)
    if not releases:
        return "<p>No releases generated.</p>"
    rows = []
    for release in releases:
        token = encode_release(release)
        link = f"{settings.public_base_url}/grab/{token}"
        ep = ""
        if release.kind == "episode":
            ep = f"S{release.season_number or 1:02d}E{release.episode_number or 1:02d}"
        rows.append(
            "<tr>"
            f"<td>{html.escape(release.title)}</td>"
            f"<td>{html.escape(release.kind)}</td>"
            f"<td>{html.escape(ep)}</td>"
            f"<td>{html.escape(release.source_name or '')}</td>"
            f"<td>{html.escape(release.output_mode)}</td>"
            f'<td><code>{html.escape(link)}</code></td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Title</th><th>Kind</th><th>Episode</th><th>Source</th><th>Mode</th><th>Grab URL</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _indexer_form_to_query(form: dict[str, str]) -> dict[str, list[str]]:
    query = {
        "t": [form.get("t", "movie")],
        "q": [form.get("q", "").strip()],
        "year": [form.get("year", "").strip()],
        "tmdbid": [form.get("tmdbid", "").strip()],
        "tvdbid": [form.get("tvdbid", "").strip()],
    }
    season_ep = form.get("season_ep", "").strip().lower()
    match = re.match(r"^\s*(\d+)\s*x\s*(\d+)\s*$", season_ep)
    if match:
        query["season"] = [match.group(1)]
        query["ep"] = [match.group(2)]
    else:
        query["season"] = [form.get("season", "").strip()]
        query["ep"] = [form.get("ep", "").strip()]
    return query


def _sources_html(settings: Settings) -> str:
    rows = []
    for source in settings.hls_template_sources:
        name = str(source.get("name") or "")
        if not name:
            continue
        if str(source.get("type") or "").lower() == "phimapi":
            kind = "PhimAPI compatible"
            target = source.get("base_url") or ""
        elif source.get("movie_resolver_url_template") or source.get("series_resolver_url_template"):
            kind = "Resolver endpoint"
            target = source.get("movie_resolver_url_template") or source.get("series_resolver_url_template") or ""
        else:
            kind = "Direct HLS template"
            target = source.get("movie_url_template") or source.get("series_url_template") or ""
        rows.append(_source_row(name, kind, str(target)))
    return (
        '<div class="source-table"><table><thead><tr>'
        "<th>Name</th><th>Type</th><th>Primary Target</th><th></th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _source_row(name: str, kind: str, target: str) -> str:
    action = (
        '<form method="post" action="/sources/delete" class="inline-form">'
        f'<input type="hidden" name="name" value="{_attr(name)}">'
        '<button type="submit" class="danger mini-button">Delete</button>'
        "</form>"
    )
    return (
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f"<td>{html.escape(kind)}</td>"
        f"<td><code>{html.escape(target)}</code></td>"
        f"<td>{action}</td>"
        "</tr>"
    )


def _resolver_preview_html(settings: Settings, form: dict[str, str]) -> str:
    kind = form.get("kind", "movie").strip().lower()
    title = form.get("title", "").strip()
    if not title:
        return "<p>Enter a title to preview matching rules.</p>"

    rows = []
    final_title = title
    source_order = settings.source_order
    for rule in settings.resolver_rules:
        rule_kind = str(rule.get("kind") or "").strip().lower()
        if rule_kind and rule_kind != kind:
            continue
        pattern = str(rule.get("match") or rule.get("regex") or "").strip()
        if not pattern:
            continue
        try:
            matched = bool(re.search(pattern, title, flags=re.IGNORECASE))
        except re.error as exc:
            rows.append(
                "<tr>"
                f"<td>{html.escape(pattern)}</td><td>invalid</td><td>{html.escape(str(exc))}</td>"
                "</tr>"
            )
            continue
        if not matched:
            continue
        replacement = str(rule.get("title") or rule.get("query") or rule.get("search_title") or "").strip()
        if replacement:
            final_title = replacement
        raw_sources = rule.get("source_order")
        if isinstance(raw_sources, str):
            source_order = [part.strip() for part in raw_sources.split(",") if part.strip()]
        elif isinstance(raw_sources, list):
            source_order = [str(part).strip() for part in raw_sources if str(part).strip()]
        rows.append(
            "<tr>"
            f"<td>{html.escape(pattern)}</td>"
            f"<td>matched</td>"
            f"<td>{html.escape(json.dumps(rule, ensure_ascii=False))}</td>"
            "</tr>"
        )

    summary = (
        f"<p><b>Final title:</b> {html.escape(final_title)}<br>"
        f"<b>Source order:</b> {html.escape(','.join(source_order))}</p>"
    )
    if not rows:
        return summary + "<p>No rules matched.</p>"
    return (
        summary
        + "<table><thead><tr><th>Pattern</th><th>Status</th><th>Rule</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _active(current: str, expected: str) -> str:
    return "active" if current == expected else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'
