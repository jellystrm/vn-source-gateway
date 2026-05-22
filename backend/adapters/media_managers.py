from __future__ import annotations

import logging
from typing import Any

import requests

from backend.domain.models import EpisodeWanted, MovieWanted
from backend.infrastructure.util import as_int

log = logging.getLogger(__name__)


def _movie_title(movie: dict[str, Any]) -> str:
    title = str(movie.get("title") or movie.get("originalTitle") or "").strip()
    if title:
        return title
    tmdb_id = as_int(movie.get("tmdbId"))
    return f"TMDB {tmdb_id}" if tmdb_id else f"Radarr movie {movie.get('id', '')}".strip()


def _series_title(series: dict[str, Any]) -> str:
    title = str(series.get("title") or "").strip()
    if title:
        return title
    tmdb_id = as_int(series.get("tmdbId"))
    tvdb_id = as_int(series.get("tvdbId"))
    if tmdb_id:
        return f"TMDB {tmdb_id}"
    if tvdb_id:
        return f"TVDB {tvdb_id}"
    return f"Sonarr series {series.get('id', '')}".strip()


class ArrClient:
    def __init__(self, base_url: str, api_key: str, name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = name
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": api_key, "Accept": "application/json"})

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    def get(self, path: str, **params: object) -> Any:
        response = self.session.get(f"{self.base_url}/api/v3/{path.lstrip('/')}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.session.post(
            f"{self.base_url}/api/v3/{path.lstrip('/')}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        response = self.session.put(
            f"{self.base_url}/api/v3/{path.lstrip('/')}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def command(self, payload: dict[str, Any]) -> Any:
        log.info("%s command: %s", self.name, payload)
        return self.post("command", payload)


class RadarrClient(ArrClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url, api_key, "radarr")

    def missing_movies(self, limit: int) -> list[MovieWanted]:
        try:
            payload = self.get("wanted/missing", page=1, pageSize=limit, sortKey="title", sortDirection="ascending")
            records = payload.get("records", []) if isinstance(payload, dict) else []
            movies = [record.get("movie", record) for record in records if isinstance(record, dict)]
        except requests.HTTPError as exc:
            log.debug("Radarr wanted/missing failed, falling back to movie list: %s", exc)
            movies = [movie for movie in self.get("movie") if movie.get("monitored") and not movie.get("hasFile")]

        wanted: list[MovieWanted] = []
        for movie in movies[:limit]:
            wanted.append(
                MovieWanted(
                    radarr_id=int(movie["id"]),
                    title=_movie_title(movie),
                    year=as_int(movie.get("year")),
                    tmdb_id=as_int(movie.get("tmdbId")),
                    imdb_id=movie.get("imdbId"),
                )
            )
        return wanted

    def import_path(self, path: str, import_mode: str) -> None:
        self.command({"name": "DownloadedMoviesScan", "path": path, "importMode": import_mode})


class SonarrClient(ArrClient):
    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url, api_key, "sonarr")

    def missing_episodes(self, limit: int) -> list[EpisodeWanted]:
        payload = self.get("wanted/missing", page=1, pageSize=limit, sortKey="airDateUtc", sortDirection="ascending")
        records = payload.get("records", []) if isinstance(payload, dict) else []

        wanted: list[EpisodeWanted] = []
        for record in records[:limit]:
            series = record.get("series") or {}
            wanted.append(
                EpisodeWanted(
                    sonarr_episode_id=int(record["id"]),
                    series_id=int(record["seriesId"]),
                    series_title=_series_title(series),
                    episode_title=str(record.get("title") or ""),
                    year=as_int(series.get("year")),
                    tmdb_id=as_int(series.get("tmdbId")),
                    tvdb_id=as_int(series.get("tvdbId")),
                    tvdb_episode_id=as_int(record.get("tvdbId")),  # episode-level TVDB ID
                    imdb_id=series.get("imdbId"),
                    season_number=int(record["seasonNumber"]),
                    episode_number=int(record["episodeNumber"]),
                )
            )
        return wanted

    def import_path(self, path: str, import_mode: str) -> None:
        self.command({"name": "DownloadedEpisodesScan", "path": path, "importMode": import_mode})

    def import_episode_by_id(self, path: str, series_id: int, episode_id: int) -> None:
        """Register a STRM file as 'downloaded' in Sonarr using explicit episode ID.

        Uses ManualImport with episodeIds so Sonarr records the episode file and
        shows the episode as downloaded (green), bypassing filename-based matching.
        Falls back to set_episode_monitored(False) if ManualImport fails.
        """
        try:
            self.command({
                "name": "ManualImport",
                "files": [{
                    "path": path,
                    "seriesId": series_id,
                    "episodeIds": [episode_id],
                    "quality": {
                        "quality": {"id": 1, "name": "Unknown", "source": "unknown", "resolution": 0},
                        "revision": {"version": 1, "real": 0, "isRepack": False},
                    },
                    "languages": [{"id": 1, "name": "English"}],
                    "releaseGroup": "Deceptarr",
                }],
                "importMode": "hardLink",
            })
            log.info("Sonarr ManualImport episode %d path=%s", episode_id, path)
        except Exception as exc:
            log.warning("Sonarr ManualImport failed (%s) — falling back to unmonitored", exc)
            self.set_episode_monitored(episode_id, False)

    def set_episode_monitored(self, episode_id: int, monitored: bool) -> None:
        """Mark a specific episode as monitored or unmonitored by its Sonarr ID.

        Used after writing a STRM file — we've already delivered the content to
        the library, so we flip the episode to unmonitored so Sonarr stops
        requesting it.  This avoids relying on filename-based matching which
        would fail when TMDB-numbered STRM files don't match Sonarr's TVDB
        episode numbering.
        """
        try:
            # Fetch current episode to preserve all required fields
            ep = self.get(f"episode/{episode_id}")
            ep["monitored"] = monitored
            self.put(f"episode/{episode_id}", ep)
            log.info("Sonarr episode %d set monitored=%s", episode_id, monitored)
        except Exception as exc:
            log.warning("Sonarr set_episode_monitored(%d) failed: %s", episode_id, exc)
