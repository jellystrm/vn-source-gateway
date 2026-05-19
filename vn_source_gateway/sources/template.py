from __future__ import annotations

from typing import Any

import requests

from vn_source_gateway.domain.models import EpisodeWanted, MovieWanted, SourceHit
from .base import Source


def _movie_fields(movie: MovieWanted) -> dict[str, object]:
    return {
        "title": movie.title,
        "year": movie.year or "",
        "tmdb_id": movie.tmdb_id or "",
        "imdb_id": movie.imdb_id or "",
        "tvdb_id": "",
        "season": "",
        "episode": "",
    }


def _episode_fields(episode: EpisodeWanted) -> dict[str, object]:
    return {
        "title": episode.series_title,
        "year": episode.year or "",
        "tmdb_id": episode.tmdb_id or "",
        "tvdb_id": episode.tvdb_id or "",
        "imdb_id": episode.imdb_id or "",
        "season": episode.season_number,
        "episode": episode.episode_number,
    }


class DirectHlsTemplateSource(Source):
    def __init__(self, config: dict[str, Any]) -> None:
        self.name = str(config["name"])
        self.movie_template = config.get("movie_url_template")
        self.series_template = config.get("series_url_template")
        self.movie_resolver_template = config.get("movie_resolver_url_template")
        self.series_resolver_template = config.get("series_resolver_url_template")
        self.headers = {str(k): str(v) for k, v in (config.get("headers") or {}).items()}
        self.session = requests.Session()

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        fields = _movie_fields(movie)
        if self.movie_resolver_template:
            return self._resolve_url(self.movie_resolver_template.format(**fields))
        if self.movie_template:
            return SourceHit(self.name, self.movie_template.format(**fields), self.headers)
        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        fields = _episode_fields(episode)
        if self.series_resolver_template:
            return self._resolve_url(self.series_resolver_template.format(**fields))
        if self.series_template:
            return SourceHit(self.name, self.series_template.format(**fields), self.headers)
        return None

    def _resolve_url(self, url: str) -> SourceHit | None:
        response = self.session.get(url, headers=self.headers, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            payload = response.json()
            hls_url = payload.get("hls_url") or payload.get("url") or payload.get("link_m3u8")
            headers = {str(k): str(v) for k, v in (payload.get("headers") or {}).items()}
            if hls_url:
                return SourceHit(self.name, str(hls_url), headers or self.headers)
            return None
        text = response.text.strip()
        if text:
            return SourceHit(self.name, text, self.headers)
        return None
