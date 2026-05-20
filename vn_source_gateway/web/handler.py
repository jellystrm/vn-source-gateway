from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from vn_source_gateway.application.grab_service import decode_release, encode_release, enqueue_from_url
from vn_source_gateway.infrastructure.activity import ActivityLog
from vn_source_gateway.infrastructure.config import Settings, save_settings
from vn_source_gateway.interfaces.download_clients import qbittorrent
from vn_source_gateway.interfaces.indexers.torznab import caps_response, search_response
from .forms import form_to_config, parse_multipart, parse_multipart_files, read_urlencoded, test_connection, test_connections
from .page import ALL_SECTIONS, SECTION_ALIASES, render_page
from .torrent import extract_announce, make_grab_torrent

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
                self._send_html(render_page(Settings.load(), "", section, settings_tab))
            elif path == "/api/config":
                self._send_json(Settings.load().to_config_dict())
            elif path == "/api/jobs":
                self._send_json({"jobs": qbittorrent.torrents_info(Settings.load())})
            elif path == "/torznab/api":
                self._handle_torznab(qs)
            elif path.startswith("/grab/"):
                self._handle_grab_download(path)
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
                except Exception:
                    log.exception("Save failed")
                self._redirect(_section_redirect(section))
            elif path == "/test":
                form = self._read_form()
                section = form.get("_section", "radarr")
                settings = Settings.load()
                if section == "radarr":
                    test_connection("Radarr", settings.radarr_url, settings.radarr_api_key)
                elif section == "sonarr":
                    test_connection("Sonarr", settings.sonarr_url, settings.sonarr_api_key)
                else:
                    test_connections(settings)
                self._redirect("/settings?tab=" + section)
            elif path == "/tasks/bulk":
                self._handle_tasks_bulk()
            elif path == "/api/manual-grab":
                self._handle_manual_grab()
            elif path == "/api/manual-grab-bulk":
                self._handle_manual_grab_bulk()
            elif path == "/api/source-test":
                self._handle_source_test()
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
                # AJAX fetch (no Accept: text/html) → plain 200 so the browser
                # doesn't follow a redirect; the JS caller will refresh #pipeline.
                # Regular form POST (browser navigation) → redirect as before.
                accept = self.headers.get("Accept", "")
                if "text/html" in accept:
                    self._redirect("/dashboard")
                else:
                    self._send_text("Ok.\n")
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

        def _handle_grab_download(self, path: str) -> None:
            """Return a minimal .torrent file whose ``announce`` URL is the grab URL.

            Radarr/Sonarr fetch this endpoint expecting a valid .torrent binary,
            then POST that binary to ``/api/v2/torrents/add`` as a multipart file
            upload.  We embed the original grab URL in the torrent so we can
            recover it when the upload arrives.
            """
            token = path[len("/grab/"):].strip("/").split("?")[0]
            if not token:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing grab token")
                return
            try:
                release = decode_release(token)
            except Exception:
                log.warning("Invalid grab token: %r", token)
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid grab token")
                return
            settings = Settings.load()
            grab_url = f"{settings.public_base_url}/grab/{token}"
            torrent_bytes = make_grab_torrent(grab_url, release.title)
            safe_name = release.title.replace("/", "-").replace("\\", "-")[:80]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/x-bittorrent")
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}.torrent"')
            self.send_header("Content-Length", str(len(torrent_bytes)))
            self.end_headers()
            self.wfile.write(torrent_bytes)

        def _handle_qbit_login(self) -> None:
            settings = Settings.load()
            form = self._read_form()
            got_user = form.get("username", "").strip()
            got_pass = form.get("password", "").strip()
            exp_user = (settings.qb_username or "").strip()
            exp_pass = (settings.qb_password or "").strip()
            log.info(
                "Download client login: got user=%r expected user=%r match=%s",
                got_user, exp_user, got_user == exp_user and got_pass == exp_pass,
            )
            if got_user != exp_user or got_pass != exp_pass:
                # qBittorrent returns HTTP 200 "Fails." for wrong credentials —
                # some Radarr versions reject HTTP 403 as a connection error.
                body = b"Fails."
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            body = b"Ok."
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Set-Cookie", "SID=vn-source; HttpOnly; path=/")
            self.end_headers()
            self.wfile.write(body)

        def _handle_qbit_add(self) -> None:
            settings = Settings.load()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")

            # Parse text fields (urls, category, paused, …)
            if content_type.startswith("multipart/form-data"):
                form = parse_multipart(body, content_type)
                files = parse_multipart_files(body, content_type)
            else:
                form = read_urlencoded(body)
                files = {}

            category = form.get("category", "vn-source")
            paused = form.get("paused", "").lower() in {"true", "1", "yes", "on"}

            # Collect candidate grab URLs from two sources:
            #   1. ``torrents`` file upload — Radarr/Sonarr send the .torrent bytes
            #      they fetched from /grab/{token}; we embedded the URL as ``announce``.
            #   2. ``urls`` text field — direct URL add (magnet or HTTP).
            candidate_urls: list[str] = []

            torrent_bytes = files.get("torrents")
            if torrent_bytes:
                announce = extract_announce(torrent_bytes)
                if announce and "/grab/" in announce:
                    log.debug("qbit add: extracted grab URL from torrent announce: %s", announce)
                    candidate_urls.append(announce)
                else:
                    log.warning("qbit add: torrent uploaded but no /grab/ announce URL found (announce=%r)", announce)

            urls_field = form.get("urls", "")
            for url in urls_field.replace("\r", "\n").split("\n"):
                url = url.strip()
                if url:
                    candidate_urls.append(url)

            added = []
            for url in candidate_urls:
                try:
                    job = enqueue_from_url(settings, url, category=category, paused=paused)
                    added.append(job.job_id)
                except Exception:
                    log.exception("qbit add: failed to enqueue %r", url)

            if not added:
                log.warning("Download client add rejected: no usable urls or torrents field")
                self.send_error(HTTPStatus.BAD_REQUEST, "No supported urls field")
                return

            log.info("Download client add accepted: category=%s paused=%s jobs=%s", category, paused, ",".join(added))
            from vn_source_gateway.infrastructure.jobs import JobStore
            store = JobStore(settings.state_path)
            for job_id in added:
                job = store.get(job_id)
                if job:
                    ActivityLog.get().add(
                        kind="grab",
                        title=job.release.title,
                        detail=f"source={job.release.source_name or 'auto'}  mode={job.release.output_mode}",
                        status="ok",
                        ref=job_id,
                    )
            self._send_text("Ok.\n")

        def _handle_tasks_bulk(self) -> None:
            """Bulk actions: resume_all, pause_all, clear_done."""
            form = self._read_form()
            settings = Settings.load()
            action = form.get("action", "")
            from vn_source_gateway.infrastructure.jobs import JobStore
            store = JobStore(settings.state_path)
            jobs = store.list_jobs()
            if action == "resume_all":
                hashes = ",".join(j.job_id for j in jobs if j.status in {"paused", "error", "queued"} and not j.paused)
                if hashes:
                    qbittorrent.pause(settings, hashes, False)
            elif action == "pause_all":
                hashes = ",".join(j.job_id for j in jobs if j.status == "running")
                if hashes:
                    qbittorrent.pause(settings, hashes, True)
            elif action == "clear_done":
                hashes = ",".join(j.job_id for j in jobs if j.status == "completed")
                if hashes:
                    qbittorrent.delete(settings, hashes)
            accept = self.headers.get("Accept", "")
            if "text/html" in accept:
                self._redirect("/dashboard")
            else:
                self._send_text("Ok.\n")

        def _handle_manual_grab(self) -> None:
            """Queue a release from a grab token with an optional output_mode/container override."""
            form = self._read_form()
            settings = Settings.load()
            token = form.get("token", "").strip()
            if not token:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing token")
                return
            try:
                release = decode_release(token)
            except Exception:
                log.warning("manual-grab: invalid token %r", token[:40])
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid token")
                return
            # Override output_mode and optional container
            from dataclasses import replace as _replace
            output_mode = form.get("output_mode", release.output_mode)
            container = form.get("container") or None
            new_release = _replace(release, output_mode=output_mode, container=container)  # type: ignore[arg-type]
            new_token = encode_release(new_release)
            grab_url = f"{settings.public_base_url}/grab/{new_token}"
            try:
                enqueue_from_url(settings, grab_url)
            except Exception:
                log.exception("manual-grab: enqueue failed for token=%r", token[:40])
            accept = self.headers.get("Accept", "")
            if "text/html" in accept:
                self._redirect("/dashboard")
            else:
                self._send_text("Ok.\n")

        def _handle_manual_grab_bulk(self) -> None:
            """Queue multiple releases from a JSON array of grab tokens with a shared output_mode/container."""
            form = self._read_form()
            settings = Settings.load()
            tokens_raw = form.get("tokens", "[]")
            output_mode = form.get("output_mode", "strm")
            container = form.get("container") or None
            try:
                tokens = json.loads(tokens_raw)
            except Exception:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid tokens JSON")
                return
            if not isinstance(tokens, list):
                self.send_error(HTTPStatus.BAD_REQUEST, "tokens must be a JSON array")
                return
            from dataclasses import replace as _replace
            for token in tokens:
                if not isinstance(token, str):
                    continue
                try:
                    release = decode_release(token)
                    new_release = _replace(release, output_mode=output_mode, container=container)  # type: ignore[arg-type]
                    new_token = encode_release(new_release)
                    grab_url = f"{settings.public_base_url}/grab/{new_token}"
                    enqueue_from_url(settings, grab_url)
                except Exception:
                    log.exception("manual-grab-bulk: failed for token %r", token[:40])
            accept = self.headers.get("Accept", "")
            if "text/html" in accept:
                self._redirect("/dashboard")
            else:
                self._send_text("Ok.\n")

        def _handle_source_test(self) -> None:
            """Test each configured source with a TMDB ID and return JSON results."""
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                params = json.loads(body.decode("utf-8"))
            except Exception:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
                return
            settings = Settings.load()
            tmdb_id_raw = params.get("tmdb_id")
            tmdb_id = int(tmdb_id_raw) if tmdb_id_raw else None
            media_type = str(params.get("media_type", "movie"))
            season = int(params.get("season", 1) or 1)
            episode = int(params.get("episode", 1) or 1)

            from vn_source_gateway.sources import build_sources
            from vn_source_gateway.domain.models import MovieWanted, EpisodeWanted
            sources = build_sources(settings.hls_template_sources, tmdb_api_key=settings.tmdb_api_key)
            results: dict[str, dict] = {}
            for source_name, source in sources.items():
                try:
                    if media_type == "movie":
                        wanted: MovieWanted | EpisodeWanted = MovieWanted(
                            radarr_id=0, title="", year=None, tmdb_id=tmdb_id, imdb_id=None
                        )
                        hit = source.resolve_movie(wanted)  # type: ignore[arg-type]
                    else:
                        wanted = EpisodeWanted(
                            sonarr_episode_id=0, series_id=0, series_title="", episode_title="",
                            year=None, tmdb_id=tmdb_id, tvdb_id=None, imdb_id=None,
                            season_number=season, episode_number=episode,
                        )
                        hit = source.resolve_episode(wanted)  # type: ignore[arg-type]
                    if hit:
                        results[source_name] = {"status": "ok", "url": hit.hls_url}
                    else:
                        results[source_name] = {"status": "error", "message": "Not found"}
                except Exception as exc:
                    results[source_name] = {"status": "error", "message": str(exc)[:200]}
            self._send_json(results)

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


def _section_redirect(section: str) -> str:
    if section in {"radarr", "sonarr", "worker", "tasks", "indexer", "downloader", "jellyfin"}:
        return f"/settings?tab={section}"
    if section == "sources":
        return "/sources"
    target = SECTION_ALIASES.get(section, section)
    return f"/{target}"
