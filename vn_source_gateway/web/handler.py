from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from vn_source_gateway.application.grab_service import enqueue_from_url
from vn_source_gateway.infrastructure.config import Settings, save_settings
from vn_source_gateway.interfaces.download_clients import qbittorrent
from vn_source_gateway.interfaces.indexers.torznab import caps_response, search_response
from .forms import form_to_config, parse_multipart, read_urlencoded, run_once, test_connection, test_connections
from .page import ALL_SECTIONS, SECTION_ALIASES, render_page

log = logging.getLogger(__name__)


def build_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "vn-source-gateway-ui/0.1"

        def log_message(self, fmt: str, *args: object) -> None:
            log.debug("UI: " + fmt, *args)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path in {"/", "/index.html"}:
                self._redirect("/dashboard")
            elif path.lstrip("/") in ALL_SECTIONS:
                section = path.lstrip("/")
                settings_tab = qs.get("tab", [""])[0]
                msg = "Saved successfully." if "saved" in qs else (
                    "Started one worker cycle. Check logs." if "run" in qs else ""
                )
                self._send_html(render_page(Settings.load(), msg, section, settings_tab))
            elif path == "/api/config":
                self._send_json(Settings.load().to_config_dict())
            elif path == "/api/jobs":
                self._send_json({"jobs": qbittorrent.torrents_info(Settings.load())})
            elif path == "/torznab/api":
                self._handle_torznab(qs)
            elif path.startswith("/grab/"):
                self._send_text("VN Source release URL. Add this through Radarr/Sonarr, not directly.\n")
            elif path == "/api/v2/app/version":
                self._send_text("4.6.0\n")
            elif path == "/api/v2/app/webapiVersion":
                self._send_text("2.8.0\n")
            elif path == "/api/v2/app/preferences":
                self._send_json(qbittorrent.preferences(Settings.load()))
            elif path == "/api/v2/app/buildInfo":
                self._send_json(qbittorrent.build_info())
            elif path == "/api/v2/torrents/categories":
                self._send_json(qbittorrent.categories(Settings.load()))
            elif path == "/api/v2/torrents/info":
                self._send_json(qbittorrent.torrents_info(Settings.load()))
            elif path == "/api/v2/torrents/properties":
                self._send_json({})
            elif path == "/api/v2/torrents/files":
                self._send_json([])
            elif path == "/api/v2/sync/maindata":
                self._send_json(qbittorrent.sync_maindata(Settings.load()))
            elif path == "/api/v2/transfer/info":
                self._send_json(qbittorrent.transfer_info())
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/save":
                form = self._read_form()
                section = form.get("_section", "radarr")
                settings = Settings.load()
                try:
                    data = form_to_config(form, settings)
                    save_settings(data, settings.config_path)
                    self._redirect(_section_redirect(section, saved=True))
                except Exception as exc:
                    self._send_html(render_page(settings, f"Save failed: {exc}", section), HTTPStatus.BAD_REQUEST)
            elif path == "/test":
                form = self._read_form()
                section = form.get("_section", "radarr")
                settings = Settings.load()
                if section == "radarr":
                    message = test_connection("Radarr", settings.radarr_url, settings.radarr_api_key)
                elif section == "sonarr":
                    message = test_connection("Sonarr", settings.sonarr_url, settings.sonarr_api_key)
                else:
                    message = test_connections(settings)
                self._send_html(render_page(settings, message, section))
            elif path == "/run-once":
                form = self._read_form()
                section = form.get("_section", "radarr")
                settings = Settings.load()
                threading.Thread(target=run_once, args=(settings,), name="vn-source-gateway-manual-run", daemon=True).start()
                self._redirect(_section_redirect(section, run=True))
            elif path == "/tasks/action":
                form = self._read_form()
                settings = Settings.load()
                action = form.get("action", "")
                hashes = form.get("hashes", "")
                if action == "resume":
                    qbittorrent.pause(settings, hashes, False)
                elif action == "pause":
                    qbittorrent.pause(settings, hashes, True)
                elif action == "delete":
                    qbittorrent.delete(settings, hashes)
                else:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Unsupported task action")
                    return
                self._redirect("/download-tasks?saved=1")
            elif path == "/api/v2/auth/login":
                self._handle_qbit_login()
            elif path == "/api/v2/torrents/add":
                self._handle_qbit_add()
            elif path == "/api/v2/torrents/delete":
                form = self._read_form()
                qbittorrent.delete(Settings.load(), form.get("hashes", ""))
                self._send_text("Ok.\n")
            elif path == "/api/v2/torrents/pause":
                form = self._read_form()
                qbittorrent.pause(Settings.load(), form.get("hashes", ""), True)
                self._send_text("Ok.\n")
            elif path == "/api/v2/torrents/resume":
                form = self._read_form()
                qbittorrent.pause(Settings.load(), form.get("hashes", ""), False)
                self._send_text("Ok.\n")
            elif path in {
                "/api/v2/torrents/setCategory",
                "/api/v2/torrents/createCategory",
                "/api/v2/torrents/editCategory",
                "/api/v2/torrents/removeCategories",
                "/api/v2/torrents/addTags",
                "/api/v2/torrents/removeTags",
            }:
                self._send_text("Ok.\n")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _handle_torznab(self, query: dict[str, list[str]]) -> None:
            settings = Settings.load()
            api_key = query.get("apikey", [""])[0]
            if settings.torznab_api_key and api_key != settings.torznab_api_key:
                log.warning("Torznab request rejected: invalid API key")
                self.send_error(HTTPStatus.UNAUTHORIZED)
                return
            log.info(
                "Torznab request: t=%s q=%s tmdbid=%s tvdbid=%s season=%s ep=%s",
                query.get("t", ["search"])[0],
                query.get("q", [""])[0],
                query.get("tmdbid", [""])[0],
                query.get("tvdbid", [""])[0],
                query.get("season", [""])[0],
                query.get("ep", [""])[0],
            )
            body = caps_response() if query.get("t", ["search"])[0] == "caps" else search_response(settings, query)
            self._send_xml(body)

        def _handle_qbit_login(self) -> None:
            settings = Settings.load()
            form = self._read_form()
            if form.get("username", "") != settings.qb_username or form.get("password", "") != settings.qb_password:
                log.warning("Download client login rejected for user=%s", form.get("username", ""))
                self._send_text("Fails.\n", HTTPStatus.FORBIDDEN)
                return
            log.info("Download client login accepted for user=%s", form.get("username", ""))
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
                log.warning("Download client add rejected: missing urls field")
                self.send_error(HTTPStatus.BAD_REQUEST, "No supported urls field")
                return
            log.info("Download client add accepted: category=%s paused=%s jobs=%s", category, paused, ",".join(added))
            self._send_text("Ok.\n")

        def _read_form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/form-data"):
                return parse_multipart(body, content_type)
            return read_urlencoded(body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

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


def _section_redirect(section: str, *, saved: bool = False, run: bool = False) -> str:
    flag = "saved=1" if saved else "run=1" if run else ""
    if section in {"radarr", "sonarr", "worker", "indexer", "downloader", "jellyfin"}:
        return f"/settings?tab={section}" + (f"&{flag}" if flag else "")
    if section == "runtime":
        return "/settings?tab=output" + (f"&{flag}" if flag else "")
    target = SECTION_ALIASES.get(section, section)
    return f"/{target}" + (f"?{flag}" if flag else "")
