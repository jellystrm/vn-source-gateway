from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [part.strip() for part in raw.split(",") if part.strip()]


def _file_value(data: dict[str, Any], key: str, default: Any) -> Any:
    value = data.get(key)
    return default if value is None else value


def _value(data: dict[str, Any], key: str, env_name: str, default: Any) -> Any:
    raw = os.getenv(env_name)
    if raw is not None and raw.strip() != "":
        return raw
    return _file_value(data, key, default)


def _bool_value(data: dict[str, Any], key: str, env_name: str, default: bool) -> bool:
    raw = os.getenv(env_name)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(_file_value(data, key, default))


def _int_value(data: dict[str, Any], key: str, env_name: str, default: int) -> int:
    raw = _value(data, key, env_name, default)
    return int(raw)


def _list_value(data: dict[str, Any], key: str, env_name: str, default: list[str]) -> list[str]:
    raw_env = os.getenv(env_name)
    if raw_env is not None and raw_env.strip() != "":
        return [part.strip() for part in raw_env.split(",") if part.strip()]
    raw = _file_value(data, key, default)
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [str(part).strip() for part in raw if str(part).strip()]


@dataclass(frozen=True)
class Settings:
    radarr_url: str = ""
    radarr_api_key: str = ""
    sonarr_url: str = ""
    sonarr_api_key: str = ""
    download_root: str = "/downloads/vn"
    movie_strm_root: str = "/movies"
    series_strm_root: str = "/shows"
    state_path: str = "/state/state.json"
    config_path: str = "/config/config.json"
    ui_enabled: bool = True
    ui_host: str = "0.0.0.0"
    ui_port: int = 8765
    poll_interval_seconds: int = 300
    max_items_per_poll: int = 20
    retry_after_seconds: int = 86400
    run_once: bool = False
    movie_enabled: bool = True
    series_enabled: bool = True
    source_order: list[str] = field(default_factory=lambda: ["kkphim", "ophim"])
    default_output_mode: str = "strm"
    expose_both_modes: bool = True
    torznab_api_key: str = "vn-source"
    public_base_url: str = "http://127.0.0.1:8765"
    qb_username: str = "admin"
    qb_password: str = "adminadmin"
    tmdb_api_key: str = ""
    jellyfin_url: str = ""
    jellyfin_api_key: str = ""
    jellyfin_scan_after_strm: bool = False
    download_container: str = "mkv"
    import_mode: str = "Move"
    ffmpeg_path: str = "ffmpeg"
    ffmpeg_extra_args: list[str] = field(default_factory=list)
    log_level: str = "INFO"
    hls_template_sources: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def load() -> "Settings":
        config_path = os.getenv("CONFIG_PATH", "/config/config.json")
        file_data: dict[str, Any] = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                file_data = loaded

        raw_templates = os.getenv("HLS_TEMPLATE_SOURCES_JSON", "").strip()
        templates = _file_value(file_data, "hls_template_sources", [])
        if raw_templates:
            decoded = json.loads(raw_templates)
            if not isinstance(decoded, list):
                raise ValueError("HLS_TEMPLATE_SOURCES_JSON must be a JSON array")
            templates = decoded
        if not isinstance(templates, list):
            raise ValueError("hls_template_sources must be a JSON array")

        return Settings(
            radarr_url=str(_value(file_data, "radarr_url", "RADARR_URL", "")).rstrip("/"),
            radarr_api_key=str(_value(file_data, "radarr_api_key", "RADARR_API_KEY", "")),
            sonarr_url=str(_value(file_data, "sonarr_url", "SONARR_URL", "")).rstrip("/"),
            sonarr_api_key=str(_value(file_data, "sonarr_api_key", "SONARR_API_KEY", "")),
            download_root=str(_value(file_data, "download_root", "DOWNLOAD_ROOT", "/downloads/vn")),
            movie_strm_root=str(_value(file_data, "movie_strm_root", "MOVIE_STRM_ROOT", "/movies")),
            series_strm_root=str(_value(file_data, "series_strm_root", "SERIES_STRM_ROOT", "/shows")),
            state_path=str(_value(file_data, "state_path", "STATE_PATH", "/state/state.json")),
            config_path=config_path,
            ui_enabled=_bool_value(file_data, "ui_enabled", "UI_ENABLED", True),
            ui_host=str(_value(file_data, "ui_host", "UI_HOST", "0.0.0.0")),
            ui_port=_int_value(file_data, "ui_port", "UI_PORT", 8765),
            poll_interval_seconds=_int_value(file_data, "poll_interval_seconds", "POLL_INTERVAL_SECONDS", 300),
            max_items_per_poll=_int_value(file_data, "max_items_per_poll", "MAX_ITEMS_PER_POLL", 20),
            retry_after_seconds=_int_value(file_data, "retry_after_seconds", "RETRY_AFTER_SECONDS", 86400),
            run_once=_bool_value(file_data, "run_once", "RUN_ONCE", False),
            movie_enabled=_bool_value(file_data, "movie_enabled", "MOVIE_ENABLED", True),
            series_enabled=_bool_value(file_data, "series_enabled", "SERIES_ENABLED", True),
            source_order=_list_value(file_data, "source_order", "SOURCE_ORDER", ["kkphim", "ophim"]),
            default_output_mode=str(_value(file_data, "default_output_mode", "DEFAULT_OUTPUT_MODE", "strm")),
            expose_both_modes=_bool_value(file_data, "expose_both_modes", "EXPOSE_BOTH_MODES", True),
            torznab_api_key=str(_value(file_data, "torznab_api_key", "TORZNAB_API_KEY", "vn-source")),
            public_base_url=str(_value(file_data, "public_base_url", "PUBLIC_BASE_URL", "http://127.0.0.1:8765")).rstrip("/"),
            qb_username=str(_value(file_data, "qb_username", "QB_USERNAME", "admin")),
            qb_password=str(_value(file_data, "qb_password", "QB_PASSWORD", "adminadmin")),
            tmdb_api_key=str(_value(file_data, "tmdb_api_key", "TMDB_API_KEY", "")),
            jellyfin_url=str(_value(file_data, "jellyfin_url", "JELLYFIN_URL", "")).rstrip("/"),
            jellyfin_api_key=str(_value(file_data, "jellyfin_api_key", "JELLYFIN_API_KEY", "")),
            jellyfin_scan_after_strm=_bool_value(file_data, "jellyfin_scan_after_strm", "JELLYFIN_SCAN_AFTER_STRM", False),
            download_container=str(_value(file_data, "download_container", "DOWNLOAD_CONTAINER", "mkv")),
            import_mode=str(_value(file_data, "import_mode", "IMPORT_MODE", "Move")),
            ffmpeg_path=str(_value(file_data, "ffmpeg_path", "FFMPEG_PATH", "ffmpeg")),
            ffmpeg_extra_args=_list_value(file_data, "ffmpeg_extra_args", "FFMPEG_EXTRA_ARGS", []),
            log_level=str(_value(file_data, "log_level", "LOG_LEVEL", "INFO")),
            hls_template_sources=templates,
        )

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "radarr_url": self.radarr_url,
            "radarr_api_key": self.radarr_api_key,
            "sonarr_url": self.sonarr_url,
            "sonarr_api_key": self.sonarr_api_key,
            "download_root": self.download_root,
            "movie_strm_root": self.movie_strm_root,
            "series_strm_root": self.series_strm_root,
            "state_path": self.state_path,
            "ui_enabled": self.ui_enabled,
            "ui_host": self.ui_host,
            "ui_port": self.ui_port,
            "poll_interval_seconds": self.poll_interval_seconds,
            "max_items_per_poll": self.max_items_per_poll,
            "retry_after_seconds": self.retry_after_seconds,
            "movie_enabled": self.movie_enabled,
            "series_enabled": self.series_enabled,
            "source_order": self.source_order,
            "default_output_mode": self.default_output_mode,
            "expose_both_modes": self.expose_both_modes,
            "torznab_api_key": self.torznab_api_key,
            "public_base_url": self.public_base_url,
            "qb_username": self.qb_username,
            "qb_password": self.qb_password,
            "tmdb_api_key": self.tmdb_api_key,
            "jellyfin_url": self.jellyfin_url,
            "jellyfin_api_key": self.jellyfin_api_key,
            "jellyfin_scan_after_strm": self.jellyfin_scan_after_strm,
            "download_container": self.download_container,
            "import_mode": self.import_mode,
            "ffmpeg_path": self.ffmpeg_path,
            "ffmpeg_extra_args": self.ffmpeg_extra_args,
            "log_level": self.log_level,
            "hls_template_sources": self.hls_template_sources,
        }


def save_settings(data: dict[str, Any], path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    os.replace(tmp_path, path)
