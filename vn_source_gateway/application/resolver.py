from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from vn_source_gateway.adapters.source_providers import Source, build_sources
from vn_source_gateway.domain.models import EpisodeWanted, GatewayRelease, MovieWanted, SourceHit
from vn_source_gateway.infrastructure.config import Settings

log = logging.getLogger(__name__)


class SourceResolver:
    def __init__(self, sources: dict[str, Source], source_order: list[str], rules: list[dict[str, Any]] | None = None) -> None:
        self.sources = sources
        self.source_order = source_order
        self.rules = rules or []

    @classmethod
    def from_settings(cls, settings: Settings) -> "SourceResolver":
        return cls(build_sources(settings.hls_template_sources), settings.source_order, settings.resolver_rules)

    def resolve_movie(self, movie: MovieWanted, source_names: list[str] | None = None) -> SourceHit | None:
        movie, source_names = self._apply_movie_rules(movie, source_names)
        label = f"movie {movie.title}"
        return self._resolve(label, source_names, lambda source: source.resolve_movie(movie))

    def resolve_episode(self, episode: EpisodeWanted, source_names: list[str] | None = None) -> SourceHit | None:
        episode, source_names = self._apply_episode_rules(episode, source_names)
        label = f"episode {episode.series_title} S{episode.season_number:02d}E{episode.episode_number:02d}"
        return self._resolve(label, source_names, lambda source: source.resolve_episode(episode))

    def resolve_release(self, release: GatewayRelease) -> SourceHit | None:
        source_names = [release.source_name] if release.source_name else None
        if release.kind == "movie":
            return self.resolve_movie(_movie_from_release(release), source_names)
        return self.resolve_episode(_episode_from_release(release), source_names)

    def _resolve(self, label: str, source_names: list[str] | None, resolve_with: ResolverFn) -> SourceHit | None:
        for source_name in source_names or self.source_order:
            if not source_name:
                continue
            source = self.sources.get(source_name)
            if not source:
                log.warning("Unknown or unconfigured source: %s", source_name)
                continue
            try:
                hit = resolve_with(source)
            except Exception:
                log.exception("%s resolver failed for %s", source_name, label)
                continue
            if hit:
                log.info("Resolved %s with %s", label, source_name)
                return hit
        return None

    def _apply_movie_rules(self, movie: MovieWanted, source_names: list[str] | None) -> tuple[MovieWanted, list[str] | None]:
        for rule in self._matching_rules("movie", movie.title):
            title = str(rule.get("title") or rule.get("query") or rule.get("search_title") or "").strip()
            if title:
                movie = replace(movie, title=title)
            source_names = _rule_source_order(rule, source_names)
        return movie, source_names

    def _apply_episode_rules(
        self,
        episode: EpisodeWanted,
        source_names: list[str] | None,
    ) -> tuple[EpisodeWanted, list[str] | None]:
        for rule in self._matching_rules("episode", episode.series_title):
            title = str(rule.get("title") or rule.get("query") or rule.get("search_title") or "").strip()
            if title:
                episode = replace(episode, series_title=title)
            source_names = _rule_source_order(rule, source_names)
        return episode, source_names

    def _matching_rules(self, kind: str, title: str) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for rule in self.rules:
            rule_kind = str(rule.get("kind") or "").strip().lower()
            if rule_kind and rule_kind != kind:
                continue
            pattern = str(rule.get("match") or rule.get("regex") or "").strip()
            if not pattern:
                continue
            try:
                if re.search(pattern, title, flags=re.IGNORECASE):
                    matched.append(rule)
            except re.error as exc:
                log.warning("Invalid resolver rule pattern %s: %s", pattern, exc)
        return matched


type ResolverFn = Callable[[Source], SourceHit | None]


def _rule_source_order(rule: dict[str, Any], current: list[str] | None) -> list[str] | None:
    raw = rule.get("source_order")
    if current is not None or raw is None:
        return current
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, list):
        return [str(part).strip() for part in raw if str(part).strip()]
    return current


def _movie_from_release(release: GatewayRelease) -> MovieWanted:
    return MovieWanted(
        radarr_id=0,
        title=release.query or release.title,
        year=release.year,
        tmdb_id=release.tmdb_id,
        imdb_id=release.imdb_id,
    )


def _episode_from_release(release: GatewayRelease) -> EpisodeWanted:
    return EpisodeWanted(
        sonarr_episode_id=0,
        series_id=0,
        series_title=release.query or release.title,
        episode_title="",
        year=release.year,
        tvdb_id=release.tvdb_id,
        imdb_id=release.imdb_id,
        season_number=release.season_number or 1,
        episode_number=release.episode_number or 1,
    )
