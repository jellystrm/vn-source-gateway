from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

import requests

from deceptarr.adapters.tmdb import TmdbClient, TmdbSeriesInfo
from deceptarr.adapters.tvmaze import TVMazeClient
from deceptarr.domain.models import EpisodeWanted, MovieWanted, SourceHit
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


def _live_action_keywords(title: str, year: int | None) -> list[str]:
    """Return extra search variants for newer live-action adaptations."""
    if not title or not year or year < 2020:
        return []
    if "live action" in normalize_text(title):
        return []
    return [f"{title} Live Action"]


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

    def _trace(self, message: str) -> None:
        self._last_log.append(message)

    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        self._last_log = [
            f"source={self.name} base={self.base_url}",
            f"movie input: title={movie.title!r}, year={movie.year}, tmdb_id={movie.tmdb_id}",
        ]
        seen: set[str] = set()
        tmdb_info = TmdbSeriesInfo(series_year=movie.year or 0)

        # fetch TMDB title + alternative titles for broader keyword coverage
        _extra_kws: list[str] = []
        if movie.tmdb_id and self.tmdb.enabled:
            self._trace(f"TMDB metadata lookup enabled for movie/{movie.tmdb_id}")
            info = self.tmdb.get_movie_info(movie.tmdb_id)
            if info:
                tmdb_info = TmdbSeriesInfo(series_year=info.series_year or movie.year or 0)
                _extra_kws = [t for t in info.alternative_titles if t]
                self._trace(
                    f"TMDB metadata ok: title={info.title!r}, year={info.series_year}, "
                    f"keywords={_extra_kws[:5]}"
                )
            else:
                self._trace("TMDB metadata lookup returned no movie info")
        elif movie.tmdb_id:
            self._trace("TMDB API key is not configured; title search uses only the provided title")

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
                self._trace(f"detail failed for slug={slug!r}")
                return None
            movie_node = detail.get("movie") or {}
            s = score_item(movie_node, movie.title, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
            name = movie_node.get("name") or slug
            _entry_passed += 1
            if s < 1000:
                _rejected.append((name, s))
                self._trace(f"detail rejected: {name!r} score={s} need>=1000")
                log.debug("%s movie '%s' detail score=%d (need 1000)", self.name, name, s)
                return None
            hit = self._first_hls(detail, server_label)
            if hit:
                suffix = f" via {via}" if via else ""
                self._trace(f"matched {name!r} score={s}{suffix}")
            else:
                self._trace(f"matched {name!r} score={s}, but no HLS link_m3u8 found")
            return hit

        keywords = _keywords(movie.title, *_extra_kws)
        if keywords:
            self._trace(f"search keywords: {keywords[:8]}")
        else:
            self._trace("no search keywords; skipping search phase")
        for kw in keywords:
            results = self._search(kw)
            _search_total += len(results)
            for item in results:
                s = score_item(item, kw, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
                if s >= 400:
                    self._trace(f"search candidate accepted: {item.get('name')!r} slug={item.get('slug')!r} score={s}")
                    hit = _try_slug(item.get("slug"))
                    if hit:
                        return hit
                else:
                    self._trace(f"search candidate skipped: {item.get('name')!r} score={s} need>=400")

        if movie.tmdb_id:
            slug = self._slug_by_tmdb("movie", movie.tmdb_id)
            hit = _try_slug(slug, via="TMDB direct")
            if hit:
                return hit
            if slug:
                self._trace("TMDB direct lookup: detail score too low or no HLS")
            else:
                self._trace("TMDB direct lookup: not found")

        # build failure summary
        if _rejected:
            best_name, best_score = max(_rejected, key=lambda x: x[1])
            self._trace(
                f"{_search_total} results, {len(_rejected)} checked; "
                f"best '{best_name}' score {best_score} (need 1000)"
            )
        elif _search_total == 0:
            self._trace("no search results")
        elif _entry_passed == 0:
            self._trace(f"{_search_total} results found, all below entry threshold (400)")

        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        self._last_log = [
            f"source={self.name} base={self.base_url}",
            (
                f"episode input: series={episode.series_title!r}, year={episode.year}, "
                f"tmdb_id={episode.tmdb_id}, tvdb_id={episode.tvdb_id}, "
                f"S{episode.season_number:02d}E{episode.episode_number:02d}"
            ),
        ]
        tmdb_info = TmdbSeriesInfo(series_year=episode.year or 0)
        if episode.tmdb_id and self.tmdb.enabled:
            self._trace(f"TMDB metadata lookup enabled for tv/{episode.tmdb_id}")
            tmdb_info = self.tmdb.get_series_info(episode.tmdb_id)
            self._trace(
                f"TMDB metadata: title={tmdb_info.title!r}, seasons={tmdb_info.total_seasons}, "
                f"episodes={tmdb_info.total_episodes}"
            )
            log.debug("%s tmdb_info for %s: %s seasons, %s eps",
                      self.name, episode.series_title, tmdb_info.total_seasons, tmdb_info.total_episodes)
        elif episode.tmdb_id:
            self._trace("TMDB API key is not configured; title search uses only the provided series title")

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
                self._trace(f"S{episode.season_number:02d}E{episode.episode_number:02d} from slug={slug!r}{suffix}")
            else:
                _rejected.append((slug, 0))
                self._trace(f"episode not found in slug={slug!r}")
                log.debug("%s episode not found in slug '%s'", self.name, slug)
            return hit

        extra_kws: list[str] = []
        if tmdb_info.title:
            extra_kws.append(tmdb_info.title)
        extra_kws += (tmdb_info.alternative_titles or [])
        extra_kws += _live_action_keywords(episode.series_title, episode.year)

        keywords = _keywords(episode.series_title, *extra_kws)
        if keywords:
            self._trace(f"search keywords: {keywords[:8]}")
        else:
            self._trace("no search keywords; skipping search phase")
        for kw in keywords:
            results = self._search(kw)
            _search_total += len(results)
            for item in results:
                s = score_item(item, kw, episode.tmdb_id, episode.year, "tv", episode.season_number, tmdb_info)
                if s >= 400:
                    s_year = _safe_int(item.get("year"))
                    detected_s = detect_season(item.get("name", ""), item.get("origin_name", ""), s_year, tmdb_info)
                    self._trace(
                        f"search candidate accepted: {item.get('name')!r} slug={item.get('slug')!r} "
                        f"score={s} detected_season={detected_s}"
                    )
                    hit = _try_slug(item.get("slug"), detected_s)
                    if hit:
                        return hit
                else:
                    self._trace(f"search candidate skipped: {item.get('name')!r} score={s} need>=400")

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
                    self._trace("TMDB direct lookup: detail fetch failed")
            else:
                self._trace("TMDB direct lookup: not found")

        # failure summary
        if _search_total == 0:
            self._trace("no search results")
        elif _entry_passed == 0:
            self._trace(f"{_search_total} results, all below entry threshold (400)")
        else:
            self._trace(
                f"{_search_total} results, {_entry_passed} series checked; "
                f"episode S{episode.season_number:02d}E{episode.episode_number:02d} not found in any"
            )

        return None

    def _search(self, keyword: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/v1/api/tim-kiem"
        try:
            r = self.session.get(
                url,
                params={"keyword": keyword, "limit": 20},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json() or {}
            items = (data.get("data") or {}).get("items")
            if isinstance(items, list):
                self._trace(f"GET {url} keyword={keyword!r}: HTTP {r.status_code}, {len(items)} item(s)")
                return items
            self._trace(f"GET {url} keyword={keyword!r}: HTTP {r.status_code}, items is not a list")
            return []
        except Exception as exc:
            self._trace(f"GET {url} keyword={keyword!r}: failed: {exc}")
            log.debug("%s search failed for %r: %s", self.name, keyword, exc)
            return []

    def _detail(self, slug: str) -> dict[str, Any] | None:
        url = f"{self.base_url}/phim/{slug}"
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                self._trace(f"GET {url}: HTTP {r.status_code}, JSON is not an object")
                return None
            if data.get("status") is False:
                self._trace(f"GET {url}: HTTP {r.status_code}, status=false msg={data.get('msg')!r}")
                return None
            movie = data.get("movie") or {}
            episodes = data.get("episodes") or (data.get("data") or {}).get("episodes") or []
            self._trace(
                f"GET {url}: HTTP {r.status_code}, movie={movie.get('name')!r}, "
                f"episode_servers={len(episodes) if isinstance(episodes, list) else 'n/a'}"
            )
            return data
        except Exception as exc:
            self._trace(f"GET {url}: failed: {exc}")
            log.debug("%s detail failed for %r: %s", self.name, slug, exc)
            return None

    def _slug_by_tmdb(self, media_type: str, tmdb_id: int) -> str | None:
        url = f"{self.base_url}/tmdb/{media_type}/{tmdb_id}"
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("status") is True:
                slug = (data.get("movie") or {}).get("slug")
                if slug:
                    self._trace(f"GET {url}: HTTP {r.status_code}, slug={slug!r}")
                    log.debug("%s direct tmdb lookup: %s/%s → %s", self.name, media_type, tmdb_id, slug)
                    return str(slug)
            self._trace(f"GET {url}: HTTP {r.status_code}, no slug msg={data.get('msg')!r}")
        except Exception as exc:
            self._trace(f"GET {url}: failed: {exc}")
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
        self._trace(f"slug={slug!r}: {len(all_candidates)} episode row(s), {len(unique_urls)} unique URL(s)")
        if tmdb_info.total_episodes > 0 and len(unique_urls) > tmdb_info.total_episodes * 1.5:
            self._trace(
                f"slug={slug!r}: skipped, too many URLs ({len(unique_urls)} vs TMDB total {tmdb_info.total_episodes})"
            )
            log.debug("%s slug %s has too many episodes (%s vs tmdb %s)", self.name, slug, len(unique_urls), tmdb_info.total_episodes)
            return None

        movie_node = detail.get("movie") or {}
        s_year = _safe_int(movie_node.get("year"))
        current_s = detect_season(movie_node.get("name", ""), movie_node.get("origin_name", ""), s_year, tmdb_info, slug)
        if current_s is None:
            current_s = assigned_season

        # ── TVMaze: fetch series info once (cached) ───────────────────────────
        # Used for two purposes:
        # 1. abs-ep → season mapping (PhimAPI absolute → TVDB season)
        # 2. TVDB (season, ep) → abs-ep  (the reverse, for flat-list shows like
        #    One Piece where PhimAPI stores "Tập 13" but Sonarr sends S2000E05)
        _tvmaze_info = None
        _expected_abs: int | None = None   # TVDB S{season}E{episode} → absolute
        if tvdb_id is not None:
            try:
                _tvmaze_info = TVMazeClient().get_series_info(tvdb_id)
                if _tvmaze_info and _tvmaze_info.seasons:
                    prev_total = 0
                    for tvs in _tvmaze_info.seasons:
                        if tvs.season_number == season:
                            _expected_abs = prev_total + episode
                            break
                        prev_total = _tvmaze_info.cumulative.get(tvs.season_number, prev_total)
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

                # ── abs-ep → season mapping ───────────────────────────────────
                # When PhimAPI uses absolute numbering and the slug has no season
                # info in its title, infer which TVDB season this episode belongs to.
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

                # ── episode number match ──────────────────────────────────────
                # Try two candidates:
                # 1. num == episode          — PhimAPI restarts ep count each season
                # 2. num == _expected_abs    — PhimAPI uses absolute ep numbering
                #    e.g. One Piece TVDB S2000E05 = absolute ep 13
                #         PhimAPI stores "Tập 13" → num=13, _expected_abs=13 ✓
                if num != episode and (_expected_abs is None or num != _expected_abs):
                    continue

                key = (url, rs, ename)
                if key not in seen_keys:
                    seen_keys.add(key)
                    log.debug("%s found S%02dE%02d in slug %s: %s", self.name, season, episode, slug, url)
                    return SourceHit(self.name, url, {})

        return None
