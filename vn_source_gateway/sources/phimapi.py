from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import requests

from vn_source_gateway.adapters.tmdb import TmdbClient, TmdbSeriesInfo
from vn_source_gateway.adapters.tvmaze import TVMazeClient
from vn_source_gateway.domain.models import EpisodeWanted, MovieWanted, SourceHit
from .base import Source
from .scoring import detect_season, score_item, season_for_abs_ep
from .text import _is_supported_lang, _safe_int, normalize_text

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Lowercase + strip diacritics for fuzzy server name matching."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _keywords(*titles: str) -> list[str]:
    """Return deduplicated, language-filtered keyword list for searching."""
    seen: dict[str, None] = {}
    for t in titles:
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
        self._last_log: list[str] = []

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        self._last_log = []
        seen: set[str] = set()
        tmdb_info = TmdbSeriesInfo(series_year=movie.year or 0)

        # fetch TMDB title + alternative titles for broader keyword coverage
        _extra_kws: list[str] = []
        if movie.tmdb_id and self.tmdb.enabled:
            info = self.tmdb.get_movie_info(movie.tmdb_id)
            if info:
                tmdb_info = TmdbSeriesInfo(series_year=info.series_year or movie.year or 0)
                _extra_kws = [t for t in info.alternative_titles if t]

        _rejected: list[tuple[str, int]] = []   # (name, detail_score)
        _search_total = 0
        _entry_passed = 0
        server_label = movie.server_label

        def _try_slug(slug: str, via: str = "") -> SourceHit | None:
            nonlocal _entry_passed
            if not slug or slug in seen:
                return None
            seen.add(slug)
            detail = self._detail(slug)
            if not detail:
                return None
            movie_node = detail.get("movie") or {}
            s = score_item(movie_node, movie.title, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
            name = movie_node.get("name") or slug
            _entry_passed += 1
            if s < 1000:
                _rejected.append((name, s))
                log.debug("%s movie '%s' detail score=%d (need 1000)", self.name, name, s)
                return None
            hit = self._first_hls(detail, server_label)
            if hit:
                suffix = f" via {via}" if via else ""
                self._last_log = [f"matched '{name}' (score {s}){suffix}"]
            return hit

        for kw in _keywords(movie.title, *_extra_kws):
            results = self._search(kw)
            _search_total += len(results)
            for item in results:
                s = score_item(item, kw, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
                if s >= 400:
                    hit = _try_slug(item.get("slug"))
                    if hit:
                        return hit

        if movie.tmdb_id:
            slug = self._slug_by_tmdb("movie", movie.tmdb_id)
            hit = _try_slug(slug, via="TMDB direct")
            if hit:
                return hit
            if slug:
                self._last_log.append("TMDB direct lookup: detail score too low")
            else:
                self._last_log.append("TMDB direct lookup: not found")

        # build failure summary
        if _rejected:
            best_name, best_score = max(_rejected, key=lambda x: x[1])
            self._last_log = [
                f"{_search_total} results, {len(_rejected)} checked; "
                f"best '{best_name}' score {best_score} (need 1000)"
            ]
        elif _search_total == 0:
            self._last_log = ["no search results"]
        elif _entry_passed == 0:
            self._last_log = [f"{_search_total} results found, all below entry threshold (400)"]

        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        self._last_log = []
        tmdb_info = TmdbSeriesInfo(series_year=episode.year or 0)
        if episode.tmdb_id and self.tmdb.enabled:
            tmdb_info = self.tmdb.get_series_info(episode.tmdb_id)
            log.debug("%s tmdb_info for %s: %s seasons, %s eps",
                      self.name, episode.series_title, tmdb_info.total_seasons, tmdb_info.total_episodes)

        seen: set[str] = set()
        _rejected: list[tuple[str, int]] = []
        _search_total = 0
        _entry_passed = 0
        server_label = episode.server_label

        def _try_slug(slug: str, assigned_season: int | None = None, via: str = "") -> SourceHit | None:
            nonlocal _entry_passed
            if not slug or slug in seen:
                return None
            seen.add(slug)
            _entry_passed += 1
            hit = self._episode_hls_from_slug(slug, episode.season_number, episode.episode_number, tmdb_info, assigned_season, server_label, episode.tvdb_id)
            if hit:
                suffix = f" via {via}" if via else ""
                self._last_log = [f"S{episode.season_number:02d}E{episode.episode_number:02d} from '{slug}'{suffix}"]
            else:
                _rejected.append((slug, 0))
                log.debug("%s episode not found in slug '%s'", self.name, slug)
            return hit

        extra_kws: list[str] = []
        if tmdb_info.title:
            extra_kws.append(tmdb_info.title)
        extra_kws += (tmdb_info.alternative_titles or [])

        for kw in _keywords(episode.series_title, *extra_kws):
            results = self._search(kw)
            _search_total += len(results)
            for item in results:
                s = score_item(item, kw, episode.tmdb_id, episode.year, "tv", episode.season_number, tmdb_info)
                if s >= 400:
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
                    hit = _try_slug(slug, detected_s or episode.season_number, via="TMDB direct")
                    if hit:
                        return hit
                else:
                    self._last_log.append("TMDB direct lookup: detail fetch failed")
            else:
                self._last_log.append("TMDB direct lookup: not found")

        # failure summary
        if not self._last_log:
            if _search_total == 0:
                self._last_log = ["no search results"]
            elif _entry_passed == 0:
                self._last_log = [f"{_search_total} results, all below entry threshold (400)"]
            else:
                self._last_log = [
                    f"{_search_total} results, {_entry_passed} series checked; "
                    f"episode S{episode.season_number:02d}E{episode.episode_number:02d} not found in any"
                ]

        return None

    def _search(self, keyword: str) -> list[dict[str, Any]]:
        try:
            r = self.session.get(
                f"{self.base_url}/v1/api/tim-kiem",
                params={"keyword": keyword, "limit": 20},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json() or {}
            items = (data.get("data") or {}).get("items")
            return items if isinstance(items, list) else []
        except Exception as exc:
            log.debug("%s search failed for %r: %s", self.name, keyword, exc)
            return []

    def _detail(self, slug: str) -> dict[str, Any] | None:
        try:
            r = self.session.get(f"{self.base_url}/phim/{slug}", timeout=20)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return None
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

    def _sorted_servers(self, detail: dict[str, Any], server_label: str) -> list[dict[str, Any]]:
        """Return server list from detail, preferred server first when label given."""
        servers: list[dict[str, Any]] = (
            detail.get("episodes")
            or (detail.get("data") or {}).get("episodes")
            or []
        )
        if not server_label:
            return servers
        kw = _norm(server_label)
        def _rank(s: dict[str, Any]) -> int:
            name = _norm(s.get("server_name") or "")
            return 0 if kw in name else 1
        return sorted(servers, key=_rank)

    def _server_data(self, detail: dict[str, Any]) -> list[dict[str, Any]]:
        episodes = detail.get("episodes") or (detail.get("data") or {}).get("episodes") or []
        out: list[dict[str, Any]] = []
        for server in episodes:
            out.extend(server.get("server_data") or [])
        return out

    def _first_hls(self, detail: dict[str, Any], server_label: str = "") -> SourceHit | None:
        headers: dict[str, str] = {"Referer": f"{self.base_url}/"}
        for server in self._sorted_servers(detail, server_label):
            for item in server.get("server_data") or []:
                url = item.get("link_m3u8")
                if url:
                    return SourceHit(self.name, str(url), headers)
        return None

    def _episode_hls_from_slug(
        self,
        slug: str,
        season: int,
        episode: int,
        tmdb_info: TmdbSeriesInfo,
        assigned_season: int | None,
        server_label: str = "",
        tvdb_id: int | None = None,
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

        # Fetch TVMaze series info once (cached) for TVDB-aligned abs-ep mapping.
        _tvmaze_info = None
        if tvdb_id is not None:
            try:
                _tvmaze_info = TVMazeClient().get_series_info(tvdb_id)
            except Exception:
                pass

        seen_keys: set[tuple[str, int | None, str]] = set()
        for server in self._sorted_servers(detail, server_label):
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

                # Absolute-episode → season mapping.
                # Prefer TVMaze (TVDB-aligned) when tvdb_id is available;
                # fall back to TMDB seasons otherwise.
                # _tvmaze_info is fetched once per slug call (see below).
                if _tvmaze_info is not None and _tvmaze_info.seasons:
                    _tvmaze_mapped: int | None = None
                    total = 0
                    for tvs in _tvmaze_info.seasons:
                        total += tvs.episode_count
                        if num <= total:
                            _tvmaze_mapped = tvs.season_number
                            break
                    if _tvmaze_mapped is not None:
                        if current_s is None:
                            rs = _tvmaze_mapped
                        else:
                            tvs_cur = next((s for s in _tvmaze_info.seasons if s.season_number == current_s), None)
                            if tvs_cur and num > tvs_cur.episode_count:
                                rs = _tvmaze_mapped
                elif tmdb_info.seasons:
                    mapped_s = season_for_abs_ep(num, tmdb_info)
                    if mapped_s:
                        if current_s is None:
                            rs = mapped_s
                        else:
                            s_info_t = next((s for s in tmdb_info.seasons if s.season_number == current_s), None)
                            if s_info_t and num > s_info_t.episode_count:
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
