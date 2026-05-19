from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)

_BASE = "https://api.themoviedb.org/3"

# Process-lifetime cache — TMDB IDs and metadata are stable.
_cache: dict[str, Any] = {}
_lock = threading.Lock()


@dataclass
class TmdbSeason:
    season_number: int
    episode_count: int
    year: int


@dataclass
class TmdbSeriesInfo:
    series_year: int = 0
    season_years: dict[int, int] = field(default_factory=dict)
    seasons: list[TmdbSeason] = field(default_factory=list)
    total_episodes: int = 0
    total_seasons: int = 0
    title: str | None = None
    alternative_titles: list[str] = field(default_factory=list)


class TmdbClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        })

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # ── ID resolution ────────────────────────────────────────────────────────

    def tmdb_id_for_tvdb(self, tvdb_id: int) -> int | None:
        cache_key = f"tvdb:{tvdb_id}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result = self._find(str(tvdb_id), "tvdb_id", "tv_results")
        with _lock:
            _cache[cache_key] = result
        return result

    def tmdb_id_for_imdb(self, imdb_id: str, kind: str = "movie") -> int | None:
        cache_key = f"imdb:{imdb_id}:{kind}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result_key = "movie_results" if kind == "movie" else "tv_results"
        result = self._find(imdb_id, "imdb_id", result_key)
        with _lock:
            _cache[cache_key] = result
        return result

    # ── Series metadata ───────────────────────────────────────────────────────

    def get_series_info(self, tmdb_id: int) -> TmdbSeriesInfo:
        cache_key = f"series_info:{tmdb_id}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result = self._fetch_series_info(tmdb_id)
        with _lock:
            _cache[cache_key] = result
        return result

    def _fetch_series_info(self, tmdb_id: int) -> TmdbSeriesInfo:
        if not self.enabled:
            return TmdbSeriesInfo()
        try:
            # Try Vietnamese first, fall back to English
            data: dict[str, Any] = {}
            for lang in ("vi-VN", "en-US"):
                r = self.session.get(
                    f"{_BASE}/tv/{tmdb_id}",
                    params={"language": lang},
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("id"):
                        break

            if not data.get("id"):
                return TmdbSeriesInfo()

            raw_date = data.get("first_air_date") or ""
            series_year = int(raw_date[:4]) if raw_date[:4].isdigit() else 0

            seasons: list[TmdbSeason] = []
            season_years: dict[int, int] = {}
            for s in data.get("seasons") or []:
                s_num = s.get("season_number", 0)
                if s_num == 0:
                    continue
                s_date = s.get("air_date") or ""
                s_year = int(s_date[:4]) if s_date[:4].isdigit() else 0
                seasons.append(TmdbSeason(season_number=s_num, episode_count=s.get("episode_count", 0), year=s_year))
                season_years[s_num] = s_year

            main_title = data.get("name")
            orig_title = data.get("original_name")
            alt_titles: list[str] = []
            try:
                ar = self.session.get(f"{_BASE}/tv/{tmdb_id}/alternative_titles", timeout=10)
                if ar.status_code == 200:
                    alt_titles = [t.get("title") for t in ar.json().get("results", []) if t.get("title")]
            except Exception:
                pass
            if main_title:
                alt_titles.append(main_title)
            if orig_title:
                alt_titles.append(orig_title)
            alt_titles = list(dict.fromkeys(alt_titles))

            return TmdbSeriesInfo(
                series_year=series_year,
                season_years=season_years,
                seasons=seasons,
                total_episodes=data.get("number_of_episodes", 0),
                total_seasons=data.get("number_of_seasons", 0),
                title=main_title,
                alternative_titles=alt_titles,
            )
        except Exception as exc:
            log.debug("TMDB series info failed for %s: %s", tmdb_id, exc)
            return TmdbSeriesInfo()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _find(self, external_id: str, source: str, result_key: str) -> int | None:
        if not self.enabled:
            return None
        try:
            r = self.session.get(
                f"{_BASE}/find/{external_id}",
                params={"external_source": source},
                timeout=10,
            )
            r.raise_for_status()
            results: list[dict[str, Any]] = r.json().get(result_key, [])
            if results:
                return int(results[0]["id"])
            return None
        except Exception as exc:
            log.debug("TMDB find %s=%s failed: %s", source, external_id, exc)
            return None
