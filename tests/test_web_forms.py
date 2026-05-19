"""Tests for web/forms.py — form parsing and config conversion."""
from __future__ import annotations

import pytest
from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.web.forms import form_to_config, parse_multipart


# ── parse_multipart ───────────────────────────────────────────────────────────

class TestParseMultipart:
    def _build_multipart(self, boundary: str, fields: dict[str, str]) -> bytes:
        parts = []
        for name, value in fields.items():
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n'
                f"\r\n"
                f"{value}"
            )
        parts.append(f"--{boundary}--\r\n")
        return "".join(parts).encode("utf-8")

    def test_basic_fields(self):
        body = self._build_multipart("abc123", {"username": "admin", "password": "secret"})
        result = parse_multipart(body, "multipart/form-data; boundary=abc123")
        assert result["username"] == "admin"
        assert result["password"] == "secret"

    def test_missing_boundary_returns_empty(self):
        assert parse_multipart(b"data", "multipart/form-data") == {}

    def test_unicode_values(self):
        body = self._build_multipart("xyz", {"title": "Phim Việt Nam"})
        result = parse_multipart(body, "multipart/form-data; boundary=xyz")
        assert result["title"] == "Phim Việt Nam"

    def test_empty_value(self):
        body = self._build_multipart("bb", {"empty_field": ""})
        result = parse_multipart(body, "multipart/form-data; boundary=bb")
        assert result.get("empty_field", None) is not None


# ── form_to_config ─────────────────────────────────────────────────────────────

class TestFormToConfig:
    @pytest.fixture
    def current(self) -> Settings:
        return Settings.load()

    def _base_form(self) -> dict[str, str]:
        return {
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "radarr-key",
            "sonarr_url": "http://sonarr:8989",
            "sonarr_api_key": "sonarr-key",
            "download_root": "/downloads",
            "movie_strm_root": "/movies",
            "series_strm_root": "/shows",
            "state_path": "/state/state.json",
            "ui_host": "0.0.0.0",
            "ui_port": "8765",
            "poll_interval_seconds": "300",
            "max_items_per_poll": "10",
            "retry_after_seconds": "3600",
            "source_order": "kkphim,ophim",
            "default_output_mode": "strm",
            "download_container": "mkv",
            "import_mode": "Move",
            "ffmpeg_path": "ffmpeg",
            "ffmpeg_extra_args": "",
            "log_level": "INFO",
            "torznab_api_key": "vn-source",
            "public_base_url": "http://localhost:8765",
            "qb_username": "admin",
            "qb_password": "adminadmin",
            "tmdb_api_key": "tmdb-key-123",
            "jellyfin_url": "",
            "jellyfin_api_key": "",
            "hls_template_sources": "[]",
        }

    def test_basic_fields_parsed(self, current):
        data = form_to_config(self._base_form(), current)
        assert data["radarr_url"] == "http://radarr:7878"
        assert data["sonarr_url"] == "http://sonarr:8989"
        assert data["tmdb_api_key"] == "tmdb-key-123"

    def test_source_order_csv(self, current):
        form = self._base_form()
        form["source_order"] = "kkphim, ophim, my-source"
        data = form_to_config(form, current)
        assert data["source_order"] == ["kkphim", "ophim", "my-source"]

    def test_checkboxes_present(self, current):
        form = self._base_form()
        form["movie_enabled"] = "on"
        form["series_enabled"] = "on"
        form["ui_enabled"] = "on"
        data = form_to_config(form, current)
        assert data["movie_enabled"] is True
        assert data["series_enabled"] is True
        assert data["ui_enabled"] is True

    def test_checkboxes_absent(self, current):
        # No checkbox keys → False
        data = form_to_config(self._base_form(), current)
        assert data["movie_enabled"] is False
        assert data["series_enabled"] is False

    def test_integer_fields(self, current):
        form = self._base_form()
        form["ui_port"] = "9999"
        form["poll_interval_seconds"] = "120"
        data = form_to_config(form, current)
        assert data["ui_port"] == 9999
        assert data["poll_interval_seconds"] == 120

    def test_integer_empty_uses_default(self, current):
        form = self._base_form()
        form["ui_port"] = ""
        data = form_to_config(form, current)
        assert data["ui_port"] == current.ui_port

    def test_url_trailing_slash_stripped(self, current):
        form = self._base_form()
        form["radarr_url"] = "http://radarr:7878/"
        data = form_to_config(form, current)
        assert not data["radarr_url"].endswith("/")

    def test_hls_template_sources_json(self, current):
        form = self._base_form()
        form["hls_template_sources"] = '[{"name":"my-src","movie_url_template":"https://x/{tmdb_id}"}]'
        data = form_to_config(form, current)
        assert len(data["hls_template_sources"]) == 1
        assert data["hls_template_sources"][0]["name"] == "my-src"

    def test_invalid_hls_json_raises(self, current):
        form = self._base_form()
        form["hls_template_sources"] = "not json"
        with pytest.raises(Exception):
            form_to_config(form, current)

    def test_hls_template_non_list_raises(self, current):
        form = self._base_form()
        form["hls_template_sources"] = '{"name":"single-object"}'
        with pytest.raises(ValueError, match="JSON array"):
            form_to_config(form, current)

    def test_ffmpeg_args_csv(self, current):
        form = self._base_form()
        form["ffmpeg_extra_args"] = "-loglevel,quiet,-threads,4"
        data = form_to_config(form, current)
        assert data["ffmpeg_extra_args"] == ["-loglevel", "quiet", "-threads", "4"]
