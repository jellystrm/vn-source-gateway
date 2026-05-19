from __future__ import annotations

import logging
import re
from typing import Any

import requests

from ..models import EpisodeWanted, MovieWanted, SourceHit
from ..tmdb import TmdbClient, TmdbSeriesInfo
from .base import Source
from .scoring import detect_season, score_item, season_for_abs_ep
from .text import _is_supported_lang, _safe_int, normalize_text

log = logging.getLogger(__name__)


def _keywords(title: str) -> list[str]:
    seen: dict[str, None] = {}
    for t in [title]:
        if t and _is_supported_lang(t):
            seen[t] = None
    return list(seen)


class PhimApiSource(Source):
    """
    Resolves HLS streams from phimapi-compatible APIs (KKPhim, OPhim).

    Lookup strategy:
      1. Search by title keywords with scoring (threshold 400 to enter, 1000 to accept).
      2. For TV or when search yields nothing: try direct /tmdb/{type}/{tmdb_id} endpoint.
    """

    def __init__(self, name: str, base_url: str, *, tmdb_api_key: str = "") -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.tmdb = TmdbClient(tmdb_api_key)
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        seen: set[str] = set()
        tmdb_info = TmdbSeriesInfo(series_year=movie.year or 0)

        def _try_slug(slug: str) -> SourceHit | None:
            if not slug or slug in seen:
                return None
            seen.add(slug)
            detail = self._detail(slug)
            if not detail:
                return None
            movie_node = detail.get("movie") or {}
            if score_item(movie_node, movie.title, movie.tmdb_id, movie.year, "movie", None, tmdb_info) < 1000:
                return None
            return self._first_hls(detail)

        for kw in _keywords(movie.title):
            for item in self._search(kw):
                if score_item(item, kw, movie.tmdb_id, movie.year, "movie", None, tmdb_info) >= 400:
                    hit = _try_slug(item.get("slug"))
                    if hit:
                        return hit

        if movie.tmdb_id:
            slug = self._slug_by_tmdb("movie", movie.tmdb_id)
            hit = _try_slug(slug)
            if hit:
                return hit

        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        tmdb_info = TmdbSeriesInfo(series_year=episode.year or 0)
        if episode.tmdb_id and self.tmdb.enabled:
            tmdb_info = self.tmdb.get_series_info(episode.tmdb_id)
            log.debug("%s tmdb_info for %s: %s seasons, %s eps",
                      self.name, episode.series_title, tmdb_info.total_seasons, tmdb_info.total_episodes)

        seen: set[str] = set()

        def _try_slug(slug: str, assigned_season: int | None = None) -> SourceHit | None:
            if not slug or slug in seen:
                return None
            seen.add(slug)
            return self._episode_hls_from_slug(slug, episode.season_number, episode.episode_number, tmdb_info, assigned_season)

        for kw in _keywords(episode.series_title):
            for item in self._search(kw):
                if score_item(item, kw, episode.tmdb_id, episode.year, "tv", episode.season_number, tmdb_info) >= 400:
                    s_year = _safe_int(item.get("year"))
                    detected_s = detect_season(item.get("name", ""), item.get("origin_name", ""), s_year, tmdb_info)
                    hit = _try_slug(item.get("slug"), detected_s)
                    if hit:
                        return hit

        if episode.tmdb_id:
            slug = self._slug_by_tmdb("tv", episode.tmdb_id)
            if slug:
                detail = self._detail(slug)
                if detail:
                    movie_node = detail.get("movie") or {}
                    s_year = _safe_int(movie_node.get("year"))
                    detected_s = detect_season(movie_node.get("name", ""), movie_node.get("origin_name", ""), s_year, tmdb_info, slug)
                    hit = _try_slug(slug, detected_s or episode.season_number)
                    if hit:
                        return hit

        return None

    def _search(self, keyword: str) -> list[dict[str, Any]]:
        try:
            r = self.session.get(
                f"{self.base_url}/v1/api/tim-kiem",
                params={"keyword": keyword, "limit": 20},
                timeout=20,
            )
            r.raise_for_status()
            return r.json().get("data", {}).get("items", [])
        except Exception as exc:
            log.debug("%s search failed for %r: %s", self.name, keyword, exc)
            return []

    def _detail(self, slug: str) -> dict[str, Any] | None:
        try:
            r = self.session.get(f"{self.base_url}/phim/{slug}", timeout=20)
            r.raise_for_status()
            data = r.json()
            return data if data.get("status") is not False else None
        except Exception as exc:
            log.debug("%s detail failed for %r: %s", self.name, slug, exc)
            return None

    def _slug_by_tmdb(self, media_type: str, tmdb_id: int) -> str | None:
        try:
            r = self.session.get(f"{self.base_url}/tmdb/{media_type}/{tmdb_id}", timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("status") is True:
                slug = (data.get("movie") or {}).get("slug")
                if slug:
                    log.debug("%s direct tmdb lookup: %s/%s → %s", self.name, media_type, tmdb_id, slug)
                    return str(slug)
        except Exception as exc:
            log.debug("%s tmdb direct lookup failed for %s/%s: %s", self.name, media_type, tmdb_id, exc)
        return None

    def _server_data(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        episodes = detail.get("episodes") or (detail.get("data") or {}).get("episodes") or []
        out: list[dict[str, Any]] = []
        for server in episodes:
            out.extend(server.get("server_data") or [])
        return out

    def _first_hls(self, detail: dict[str, Any]) -> SourceHit | None:
        for item in self._server_data(detail):
            url = item.get("link_m3u8")
            if url:
                return SourceHit(self.name, str(url), {})
        return None

    def _episode_hls_from_slug(
        self,
        slug: str,
        season: int,
        episode: int,
        tmdb_info: TmdbSeriesInfo,
        assigned_season: int | None,
    ) -> SourceHit | None:
        detail = self._detail(slug)
        if not detail:
            return None

        all_candidates = self._server_data(detail)
        unique_urls = {ep.get("link_m3u8") or ep.get("link_embed") for ep in all_candidates if ep.get("link_m3u8") or ep.get("link_embed")}
        if tmdb_info.total_episodes > 0 and len(unique_urls) > tmdb_info.total_episodes * 1.5:
            log.debug("%s slug %s has too many episodes (%s vs tmdb %s)", self.name, slug, len(unique_urls), tmdb_info.total_episodes)
            return None

        movie_node = detail.get("movie") or {}
        s_year = _safe_int(movie_node.get("year"))
        current_s = detect_season(movie_node.get("name", ""), movie_node.get("origin_name", ""), s_year, tmdb_info, slug)
        if current_s is None:
            current_s = assigned_season

        seen_keys: set[tuple[str, int | None, str]] = set()
        for server in detail.get("episodes") or []:
            for ep_data in server.get("server_data") or []:
                url = ep_data.get("link_m3u8")
                if not url:
                    continue
                ename = str(ep_data.get("name") or "")
                rs = current_s

                if not rs:
                    es_m = re.search(r"(ph[aầ]n|season|ss|p|s)\s*(\d+)", ename, re.IGNORECASE)
                    if es_m:
                        rs = int(es_m.group(2))

                clean = normalize_text(ename)
                if s_year > 0:
                    clean = clean.replace(str(s_year), "")
                if rs:
                    clean = re.sub(rf"\b(mua|p|s){rs}\b", "", clean)
                ep_m = re.search(r"(?:tap|episode|ep|e|t)\s*(\d+)", clean, re.IGNORECASE)
                if not ep_m:
                    ep_m = re.search(r"(\d+)", clean)
                num = int(ep_m.group(1)) if ep_m else 1

                if tmdb_info.seasons:
                    mapped_s = season_for_abs_ep(num, tmdb_info)
                    if mapped_s:
                        if current_s is None:
                            rs = mapped_s
                        else:
                            s_info = next((s for s in tmdb_info.seasons if s.season_number == current_s), None)
                            if s_info and num > s_info.episode_count:
                                rs = mapped_s

                if rs is not None and rs != season:
                    continue
                if num != episode:
                    continue

                key = (url, rs, ename)
                if key not in seen_keys:
                    seen_keys.add(key)
                    log.debug("%s found S%02dE%02d in slug %s: %s", self.name, season, episode, slug, url)
                    return SourceHit(self.name, url, {})

        return None
