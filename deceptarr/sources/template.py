from __future__ import annotations

from typing import Any

import requests

from deceptarr.domain.models import EpisodeWanted, MovieWanted, SourceHit
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
    s = episode.season_number
    e = episode.episode_number
    return {
        "title": episode.series_title,
        "year": episode.year or "",
        "tmdb_id": episode.tmdb_id or "",
        "tvdb_id": episode.tvdb_id or "",
        "imdb_id": episode.imdb_id or "",
        "season": s,
        "episode": e,
        # Zero-padded variants — use {season_padded}/{episode_padded} in templates
        "season_padded": f"{s:02d}",
        "episode_padded": f"{e:02d}",
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
        self._last_log: list[str] = []

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        self._last_log = [f"source={self.name} type=template", f"movie input: title={movie.title!r}, tmdb_id={movie.tmdb_id}"]
        fields = _movie_fields(movie)
        if self.movie_resolver_template:
            url = self.movie_resolver_template.format(**fields)
            self._last_log.append(f"resolver URL: {url}")
            return self._resolve_url(url)
        if self.movie_template:
            url = self.movie_template.format(**fields)
            self._last_log.append(f"direct URL template produced: {url}")
            return SourceHit(self.name, url, self.headers)
        self._last_log.append("no movie template or resolver configured")
        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        self._last_log = [
            f"source={self.name} type=template",
            f"episode input: title={episode.series_title!r}, tmdb_id={episode.tmdb_id}, S{episode.season_number:02d}E{episode.episode_number:02d}",
        ]
        fields = _episode_fields(episode)
        if self.series_resolver_template:
            url = self.series_resolver_template.format(**fields)
            self._last_log.append(f"resolver URL: {url}")
            return self._resolve_url(url)
        if self.series_template:
            url = self.series_template.format(**fields)
            self._last_log.append(f"direct URL template produced: {url}")
            return SourceHit(self.name, url, self.headers)
        self._last_log.append("no series template or resolver configured")
        return None

    def _resolve_url(self, url: str) -> SourceHit | None:
        try:
            response = self.session.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
        except Exception as exc:
            self._last_log.append(f"GET {url}: failed: {exc}")
            raise
        self._last_log.append(f"GET {url}: HTTP {response.status_code}, content-type={response.headers.get('Content-Type', '')!r}")
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            payload = response.json()
            hls_url = payload.get("hls_url") or payload.get("url") or payload.get("link_m3u8")
            headers = {str(k): str(v) for k, v in (payload.get("headers") or {}).items()}
            if hls_url:
                self._last_log.append(f"JSON resolver returned HLS URL: {hls_url}")
                return SourceHit(self.name, str(hls_url), headers or self.headers)
            self._last_log.append("JSON resolver did not include hls_url/url/link_m3u8")
            return None
        text = response.text.strip()
        if text:
            self._last_log.append(f"text resolver returned {len(text)} characters")
            return SourceHit(self.name, text, self.headers)
        self._last_log.append("resolver response body was empty")
        return None
