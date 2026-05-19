from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import requests

from .models import EpisodeWanted, MovieWanted, SourceHit
from .util import normalize_text

log = logging.getLogger(__name__)


class Source(ABC):
    name: str

    @abstractmethod
    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        raise NotImplementedError

    @abstractmethod
    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        raise NotImplementedError


class PhimApiSource(Source):
    def __init__(self, name: str, base_url: str) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        for detail in self._details_for_title(movie.title):
            remote_tmdb = self._tmdb_id(detail)
            if movie.tmdb_id and remote_tmdb and remote_tmdb != movie.tmdb_id:
                continue
            hls_url = self._first_hls(detail)
            if hls_url:
                return SourceHit(self.name, hls_url, {})
        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        for detail in self._details_for_title(episode.series_title):
            hls_url = self._episode_hls(detail, episode.episode_number)
            if hls_url:
                return SourceHit(self.name, hls_url, {})
        return None

    def _details_for_title(self, title: str) -> list[dict[str, Any]]:
        try:
            response = self.session.get(
                f"{self.base_url}/v1/api/tim-kiem",
                params={"keyword": title, "limit": 10},
                timeout=20,
            )
            response.raise_for_status()
            items = response.json().get("data", {}).get("items", [])
        except Exception as exc:
            log.debug("%s search failed for %s: %s", self.name, title, exc)
            return []

        details: list[dict[str, Any]] = []
        wanted_title = normalize_text(title)
        for item in items:
            slug = item.get("slug")
            item_title = normalize_text(str(item.get("name") or item.get("origin_name") or ""))
            if wanted_title and item_title and wanted_title not in item_title and item_title not in wanted_title:
                log.debug("%s loose title mismatch: %s vs %s", self.name, title, item.get("name"))
            if not slug:
                continue
            try:
                detail_response = self.session.get(f"{self.base_url}/phim/{slug}", timeout=20)
                detail_response.raise_for_status()
                details.append(detail_response.json())
            except Exception as exc:
                log.debug("%s detail failed for slug %s: %s", self.name, slug, exc)
        return details

    @staticmethod
    def _tmdb_id(detail: dict[str, Any]) -> int | None:
        raw = detail.get("movie", {}).get("tmdb", {}).get("id")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _server_data(detail: dict[str, Any]) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = []
        for server in detail.get("episodes") or []:
            data.extend(server.get("server_data") or [])
        return data

    def _first_hls(self, detail: dict[str, Any]) -> str | None:
        for item in self._server_data(detail):
            url = item.get("link_m3u8")
            if url:
                return str(url)
        return None

    def _episode_hls(self, detail: dict[str, Any], episode_number: int) -> str | None:
        candidates = self._server_data(detail)
        for item in candidates:
            name = str(item.get("name") or item.get("slug") or item.get("filename") or "")
            if _episode_number_matches(name, episode_number):
                url = item.get("link_m3u8")
                if url:
                    return str(url)
        if episode_number == 1 and len(candidates) == 1:
            return candidates[0].get("link_m3u8")
        return None


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
        "tmdb_id": "",
        "tvdb_id": episode.tvdb_id or "",
        "imdb_id": episode.imdb_id or "",
        "season": episode.season_number,
        "episode": episode.episode_number,
    }


def build_sources(template_configs: list[dict[str, Any]]) -> dict[str, Source]:
    sources: dict[str, Source] = {
        "kkphim": PhimApiSource("kkphim", "https://phimapi.com"),
        "ophim": PhimApiSource("ophim", "https://ophim1.com"),
    }
    for config in template_configs:
        source = DirectHlsTemplateSource(config)
        sources[source.name] = source
    return sources


def _episode_number_matches(value: str, episode_number: int) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    patterns = [
        rf"\btap\s*0*{episode_number}\b",
        rf"\bep(?:isode)?\s*0*{episode_number}\b",
        rf"\be\s*0*{episode_number}\b",
        rf"\b0*{episode_number}\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)
