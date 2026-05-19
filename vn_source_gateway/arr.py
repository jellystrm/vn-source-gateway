from __future__ import annotations

import logging
from typing import Any

import requests

from .models import EpisodeWanted, MovieWanted
from .util import as_int

log = logging.getLogger(__name__)


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
                    title=str(movie.get("title") or movie.get("originalTitle") or "Untitled"),
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
                    series_title=str(series.get("title") or "Untitled"),
                    episode_title=str(record.get("title") or ""),
                    year=as_int(series.get("year")),
                    tmdb_id=as_int(series.get("tmdbId")),
                    tvdb_id=as_int(series.get("tvdbId")),
                    imdb_id=series.get("imdbId"),
                    season_number=int(record["seasonNumber"]),
                    episode_number=int(record["episodeNumber"]),
                )
            )
        return wanted

    def import_path(self, path: str, import_mode: str) -> None:
        self.command({"name": "DownloadedEpisodesScan", "path": path, "importMode": import_mode})
