from __future__ import annotations

import logging
import re
from typing import Any

import requests

from deceptarr.adapters.tmdb import TmdbClient, TmdbSeriesInfo
from deceptarr.domain.models import EpisodeWanted, MovieWanted, SourceHit
from .phimapi import _keywords, _live_action_keywords, _norm
from .scoring import detect_season, score_item
from .text import _safe_int
from .base import Source

log = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(text)).strip("-")


class NguonCSource(Source):
    """Resolves HLS streams from phim.nguonc.com.

    NguonC is not PhimAPI-compatible. It exposes search at
    ``/api/films/search`` and detail at ``/api/film/{slug}``, with HLS URLs in
    ``movie.episodes[].items[].m3u8``.
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
        tmdb_info = TmdbSeriesInfo(series_year=movie.year or 0)
        extra_kws: list[str] = []
        if movie.tmdb_id and self.tmdb.enabled:
            self._trace(f"TMDB metadata lookup enabled for movie/{movie.tmdb_id}")
            info = self.tmdb.get_movie_info(movie.tmdb_id)
            if info:
                tmdb_info = TmdbSeriesInfo(series_year=info.series_year or movie.year or 0)
                extra_kws = [t for t in info.alternative_titles if t]
                self._trace(
                    f"TMDB metadata ok: title={info.title!r}, year={info.series_year}, "
                    f"keywords={extra_kws[:5]}"
                )
            else:
                self._trace("TMDB metadata lookup returned no movie info")
        elif movie.tmdb_id:
            self._trace("TMDB API key is not configured; title search uses only the provided title")

        checked = 0
        rejected: list[tuple[str, int]] = []
        keywords = _keywords(movie.title, *extra_kws)
        if keywords:
            self._trace(f"search keywords: {keywords[:8]}")
        else:
            self._trace("no search keywords; skipping search phase")

        for kw in keywords:
            for raw in self._search(kw):
                item = self._normalize_item(raw)
                score = score_item(item, kw, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
                if score < 400:
                    self._trace(f"search candidate skipped: {item.get('name')!r} score={score} need>=400")
                    continue
                self._trace(f"search candidate accepted: {item.get('name')!r} slug={item.get('slug')!r} score={score}")
                detail = self._detail(str(item.get("slug") or ""))
                if not detail:
                    continue
                checked += 1
                movie_node = self._normalize_item(detail.get("movie") or {})
                detail_score = score_item(movie_node, movie.title or kw, movie.tmdb_id, movie.year, "movie", None, tmdb_info)
                name = movie_node.get("name") or item.get("name") or item.get("slug")
                if detail_score < 1000:
                    rejected.append((str(name), detail_score))
                    self._trace(f"detail rejected: {name!r} score={detail_score} need>=1000")
                    continue
                hit = self._first_hls(detail, movie.server_label)
                if hit:
                    self._trace(f"matched {name!r} score={detail_score}")
                    return hit
                self._trace(f"matched {name!r} score={detail_score}, but no m3u8 found")

        if rejected:
            best_name, best_score = max(rejected, key=lambda x: x[1])
            self._trace(f"{checked} detail page(s) checked; best '{best_name}' score {best_score} (need 1000)")
        elif not keywords:
            self._trace("no usable title; provide Title/Year or configure TMDB key")
        else:
            self._trace("no matching movie found")
        return None

    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        self._last_log = [
            f"source={self.name} base={self.base_url}",
            (
                f"episode input: series={episode.series_title!r}, year={episode.year}, "
                f"tmdb_id={episode.tmdb_id}, S{episode.season_number:02d}E{episode.episode_number:02d}"
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
        elif episode.tmdb_id:
            self._trace("TMDB API key is not configured; title search uses only the provided series title")

        extra_kws = [tmdb_info.title] if tmdb_info.title else []
        extra_kws += tmdb_info.alternative_titles or []
        extra_kws += _live_action_keywords(episode.series_title, episode.year)
        keywords = _keywords(episode.series_title, *extra_kws)
        if keywords:
            self._trace(f"search keywords: {keywords[:8]}")
        else:
            self._trace("no search keywords; skipping search phase")

        checked = 0
        seen_slugs: set[str] = set()

        def _try_slug(slug: str, query: str, via: str = "") -> SourceHit | None:
            nonlocal checked
            if not slug or slug in seen_slugs:
                return None
            seen_slugs.add(slug)
            detail = self._detail(slug)
            if not detail:
                return None
            checked += 1
            movie_node = self._normalize_item(detail.get("movie") or {})
            detail_score = score_item(
                movie_node,
                query,
                episode.tmdb_id,
                episode.year,
                "tv",
                episode.season_number,
                tmdb_info,
            )
            name = movie_node.get("name") or slug
            if detail_score < 400:
                self._trace(f"detail rejected: {name!r} slug={slug!r} score={detail_score} need>=400")
                return None
            detected = detect_season(
                str(movie_node.get("name") or ""),
                str(movie_node.get("origin_name") or ""),
                _safe_int(movie_node.get("year")),
                tmdb_info,
                slug,
            )
            hit = self._episode_hls(detail, episode.season_number, episode.episode_number, detected, episode.server_label)
            if hit:
                suffix = f" via {via}" if via else ""
                self._trace(
                    f"S{episode.season_number:02d}E{episode.episode_number:02d} "
                    f"from slug={slug!r} detected_season={detected} score={detail_score}{suffix}"
                )
                return hit
            self._trace(f"episode not found in slug={slug!r} detected_season={detected} score={detail_score}")
            return None

        for kw in keywords:
            for raw in self._search(kw):
                item = self._normalize_item(raw)
                score = score_item(
                    item,
                    kw,
                    episode.tmdb_id,
                    episode.year,
                    "tv",
                    episode.season_number,
                    tmdb_info,
                )
                if score < 400:
                    self._trace(f"search candidate skipped: {item.get('name')!r} score={score} need>=400")
                    continue
                slug = str(item.get("slug") or "")
                self._trace(f"search candidate accepted: {item.get('name')!r} slug={slug!r} score={score}")
                hit = _try_slug(slug, kw)
                if hit:
                    return hit

        for kw in keywords:
            slug = _slugify(kw)
            if not slug:
                continue
            self._trace(f"trying direct slug fallback: {slug!r} from keyword={kw!r}")
            hit = _try_slug(slug, kw, via="direct slug fallback")
            if hit:
                return hit

        if not keywords:
            self._trace("no usable series title; provide Title/Year or configure TMDB key")
        else:
            self._trace(
                f"{checked} series detail page(s) checked; "
                f"episode S{episode.season_number:02d}E{episode.episode_number:02d} not found"
            )
        return None

    def _search(self, keyword: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/api/films/search"
        try:
            r = self.session.get(url, params={"keyword": keyword}, timeout=20)
            r.raise_for_status()
            data = r.json() or {}
            items = data.get("items")
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
        if not slug:
            self._trace("detail skipped: empty slug")
            return None
        url = f"{self.base_url}/api/film/{slug}"
        try:
            r = self.session.get(url, timeout=20)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                self._trace(f"GET {url}: HTTP {r.status_code}, JSON is not an object")
                return None
            if data.get("status") != "success":
                self._trace(f"GET {url}: HTTP {r.status_code}, status={data.get('status')!r} message={data.get('message')!r}")
                return None
            movie = data.get("movie") or {}
            episodes = movie.get("episodes") or []
            self._trace(
                f"GET {url}: HTTP {r.status_code}, movie={movie.get('name')!r}, "
                f"episode_servers={len(episodes) if isinstance(episodes, list) else 'n/a'}"
            )
            return data
        except Exception as exc:
            self._trace(f"GET {url}: failed: {exc}")
            log.debug("%s detail failed for %r: %s", self.name, slug, exc)
            return None

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        year = self._year_from_item(item)
        total = _safe_int(item.get("total_episodes"))
        current = str(item.get("current_episode") or "")
        is_movie = total == 1 or current.lower() in {"full", "hoan tat (1/1)", "hoàn tất (1/1)"}
        return {
            **item,
            "origin_name": item.get("origin_name") or item.get("original_name") or "",
            "year": year,
            "type": "single" if is_movie else "series",
            "episode_current": current or ("Full" if is_movie else ""),
            "episode_total": total,
        }

    def _year_from_item(self, item: dict[str, Any]) -> int:
        direct = _safe_int(item.get("year"))
        if direct:
            return direct
        category = item.get("category")
        if not isinstance(category, dict):
            return 0
        for group in category.values():
            if not isinstance(group, dict):
                continue
            group_name = ((group.get("group") or {}).get("name") or "").lower()
            if "nam" not in _norm(group_name):
                continue
            for entry in group.get("list") or []:
                value = _safe_int((entry or {}).get("name"))
                if value:
                    return value
        return 0

    def _sorted_servers(self, detail: dict[str, Any], server_label: str) -> list[dict[str, Any]]:
        servers = ((detail.get("movie") or {}).get("episodes") or [])
        if not isinstance(servers, list):
            return []
        if not server_label:
            return servers
        kw = _norm(server_label)
        return sorted(servers, key=lambda s: 0 if kw in _norm(str(s.get("server_name") or "")) else 1)

    def _first_hls(self, detail: dict[str, Any], server_label: str = "") -> SourceHit | None:
        headers: dict[str, str] = {"Referer": f"{self.base_url}/"}
        for server in self._sorted_servers(detail, server_label):
            for item in server.get("items") or []:
                url = item.get("m3u8")
                if url:
                    return SourceHit(self.name, str(url), headers)
        return None

    def _episode_hls(
        self,
        detail: dict[str, Any],
        season: int,
        episode: int,
        detected_season: int | None,
        server_label: str = "",
    ) -> SourceHit | None:
        if detected_season is not None and detected_season != season:
            self._trace(f"detail season mismatch: detected={detected_season}, requested={season}")
            return None
        headers: dict[str, str] = {"Referer": f"{self.base_url}/"}
        for server in self._sorted_servers(detail, server_label):
            for item in server.get("items") or []:
                url = item.get("m3u8")
                if not url:
                    continue
                raw_name = str(item.get("name") or item.get("slug") or "")
                match = re.search(r"\d+", raw_name)
                number = int(match.group()) if match else 1
                if number == episode:
                    return SourceHit(self.name, str(url), headers)
        return None
