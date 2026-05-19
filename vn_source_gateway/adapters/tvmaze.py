from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import requests

log = logging.getLogger(__name__)

_BASE = "https://api.tvmaze.com"

# Process-lifetime cache — TVMaze IDs and episode lists are stable.
_cache: dict[str, Any] = {}
_lock = threading.Lock()


@dataclass
class TVMazeSeason:
    season_number: int
    episode_count: int


@dataclass
class TVMazeSeriesInfo:
    """TVDB-aligned series structure fetched from TVMaze."""
    seasons: list[TVMazeSeason] = field(default_factory=list)
    total_episodes: int = 0
    total_seasons: int = 0

    # Cumulative episode counts per season — used for absolute-episode mapping.
    # e.g. {1: 12, 2: 25, 3: 38} means S1=12 eps, S2=13 eps, S3=13 eps
    cumulative: dict[int, int] = field(default_factory=dict)


class TVMazeClient:
    """Thin TVMaze client for TVDB-aligned season/episode lookups.

    TVMaze is free (no API key), and its episode numbering mirrors TVDB,
    making it the correct source when Sonarr/TVDB season numbers are needed.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    # ── Public API ────────────────────────────────────────────────────────────

    def get_season_episodes(self, tvdb_id: int, season: int) -> list[int]:
        """Return ordered episode numbers for *season* of a show identified by *tvdb_id*.

        Uses TVDB-aligned numbering (i.e. the same numbers Sonarr sends).
        Returns an empty list on any error or miss.
        """
        cache_key = f"tvmaze:season_eps:{tvdb_id}:{season}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result = self._fetch_season_episodes(tvdb_id, season)
        with _lock:
            _cache[cache_key] = result
        return result

    def get_series_info(self, tvdb_id: int) -> TVMazeSeriesInfo:
        """Return TVDB-aligned series structure (season/episode counts).

        Use this instead of TMDB series info when you need to map absolute
        episode numbers to (season, episode) tuples in TVDB numbering.
        Returns an empty TVMazeSeriesInfo on miss.
        """
        cache_key = f"tvmaze:series_info:{tvdb_id}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result = self._fetch_series_info(tvdb_id)
        with _lock:
            _cache[cache_key] = result
        return result

    def season_for_abs_ep(self, tvdb_id: int, abs_ep: int) -> int | None:
        """Map an absolute episode number to its TVDB season number.

        Returns None when the show is not found or the episode is out of range.
        """
        info = self.get_series_info(tvdb_id)
        if not info.seasons:
            return None
        for s in info.seasons:
            if abs_ep <= info.cumulative.get(s.season_number, 0):
                return s.season_number
        return None

    # ── Internal ─────────────────────────────────────────────────────────────

    def _get_show_id(self, tvdb_id: int) -> int | None:
        cache_key = f"tvmaze:show:{tvdb_id}"
        with _lock:
            if cache_key in _cache:
                return _cache[cache_key]
        result = self._fetch_show_id(tvdb_id)
        with _lock:
            _cache[cache_key] = result
        return result

    def _fetch_show_id(self, tvdb_id: int) -> int | None:
        try:
            r = self.session.get(
                f"{_BASE}/lookup/shows",
                params={"thetvdb": tvdb_id},
                timeout=10,
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return int(data["id"])
        except Exception as exc:
            log.debug("TVMaze show lookup failed for tvdb_id=%s: %s", tvdb_id, exc)
            return None

    def _fetch_season_episodes(self, tvdb_id: int, season: int) -> list[int]:
        show_id = self._get_show_id(tvdb_id)
        if not show_id:
            return []
        try:
            r = self.session.get(
                f"{_BASE}/shows/{show_id}/episodes",
                timeout=10,
            )
            if r.status_code != 200:
                return []
            episodes: list[dict[str, Any]] = r.json()
            return sorted(
                e["number"]
                for e in episodes
                if e.get("season") == season and e.get("number")
            )
        except Exception as exc:
            log.debug("TVMaze episodes failed for show=%s season=%s: %s", show_id, season, exc)
            return []

    def _fetch_series_info(self, tvdb_id: int) -> TVMazeSeriesInfo:
        show_id = self._get_show_id(tvdb_id)
        if not show_id:
            return TVMazeSeriesInfo()
        try:
            r = self.session.get(
                f"{_BASE}/shows/{show_id}/episodes",
                timeout=10,
            )
            if r.status_code != 200:
                return TVMazeSeriesInfo()
            episodes: list[dict[str, Any]] = r.json()
            # Count episodes per season (regular only, season > 0)
            season_counts: dict[int, int] = {}
            for e in episodes:
                s = e.get("season")
                if s and s > 0 and e.get("number"):
                    season_counts[s] = season_counts.get(s, 0) + 1
            if not season_counts:
                return TVMazeSeriesInfo()
            seasons = [
                TVMazeSeason(season_number=s, episode_count=c)
                for s, c in sorted(season_counts.items())
            ]
            cumulative: dict[int, int] = {}
            total = 0
            for s in seasons:
                total += s.episode_count
                cumulative[s.season_number] = total
            return TVMazeSeriesInfo(
                seasons=seasons,
                total_episodes=total,
                total_seasons=len(seasons),
                cumulative=cumulative,
            )
        except Exception as exc:
            log.debug("TVMaze series info failed for show=%s: %s", show_id, exc)
            return TVMazeSeriesInfo()
