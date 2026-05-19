from __future__ import annotations

import re
from typing import Any

from vn_source_gateway.adapters.tmdb import TmdbSeriesInfo
from .text import _identity_leakage, _safe_int, normalize_text


def score_item(
    item: dict[str, Any],
    query: str,
    tmdb_id: int | None,
    year: int | None,
    media_type: str,
    requested_season: int | None,
    tmdb_info: TmdbSeriesInfo,
) -> int:
    if not item:
        return -1000
    score = 0
    n_name = normalize_text(item.get("name") or "")
    n_origin = normalize_text(item.get("origin_name") or "")
    s_type = str(item.get("type") or "").lower()
    s_year = _safe_int(item.get("year"))

    # 1. TMDB ID match
    src_tmdb = item.get("tmdb") or {}
    item_tmdb_str = str(src_tmdb.get("id") or "")
    tmdb_matched = False
    if tmdb_id and item_tmdb_str and item_tmdb_str not in ("0", "null", "None", ""):
        if item_tmdb_str == str(tmdb_id):
            series_start = tmdb_info.series_year or year or 0
            if series_start > 0 and s_year > 0:
                all_y = [series_start] + list(tmdb_info.season_years.values())
                year_ok = abs(s_year - series_start) <= 10 or any(abs(s_year - y) <= 1 for y in all_y if y > 0)
                if not year_ok:
                    return -5000
            score += 3000
            tmdb_matched = True
        else:
            return -5000

    # 2. Type check
    if not tmdb_matched:
        MOVIE_TYPES = {"single", "movie"}
        TV_TYPES = {"series", "tvshows", "tv"}
        if media_type == "movie" and s_type in TV_TYPES:
            return -3000
        if media_type == "tv" and s_type in MOVIE_TYPES:
            return -3000
        if s_type not in MOVIE_TYPES | TV_TYPES:
            ep_current = str(item.get("episode_current") or "").strip().lower()
            ep_total = _safe_int(item.get("episode_total"))
            is_movie_like = ep_current in ("full", "1") or ep_total == 1
            is_tv_like = not is_movie_like and (ep_total > 1 or (ep_current and ep_current not in ("full", "1")))
            if media_type == "movie" and is_tv_like:
                return -3000
            if media_type == "tv" and is_movie_like:
                return -3000

    # 3. Year match
    series_start = tmdb_info.series_year or year or 0
    all_y = [series_start] + list(tmdb_info.season_years.values())
    if s_year > 0 and series_start > 0:
        if media_type == "movie":
            if abs(s_year - series_start) > 1:
                return -3000
            score += 600
        else:
            season_year = tmdb_info.season_years.get(requested_season or 0, 0)
            if season_year > 0:
                if abs(s_year - season_year) > 2:
                    return -4000
                score += 600
            else:
                if requested_season == 1 and abs(s_year - series_start) > 2:
                    if not any(abs(s_year - y) <= 1 for y in all_y if y > 0):
                        return -4000
                    score -= 1000
                if any(abs(s_year - y) <= 1 for y in all_y if y > 0):
                    score += 500
                elif s_year >= series_start:
                    score += 100
                else:
                    return -3000

    # 4. Episode/season sanity
    ep_total = _safe_int(item.get("episode_total"))
    if tmdb_info.total_episodes > 0 and ep_total > tmdb_info.total_episodes * 1.3:
        return -4500

    found_s = detect_season(item.get("name", ""), item.get("origin_name", ""), s_year, tmdb_info)
    if found_s and tmdb_info.total_seasons > 0 and found_s > tmdb_info.total_seasons:
        return -4600
    if found_s is not None:
        if requested_season is None:
            score += 500
        elif found_s == requested_season:
            score += 500
        else:
            return -5000

    # 5. Identity leakage (sequel/spinoff detection)
    # ignore_season only for TV — for movies "2" in title IS a meaningful sequel token
    ignore_s = (found_s or 0) if media_type == "tv" else 0
    if not tmdb_matched:
        if _identity_leakage(item.get("name", ""), query, ignore_year=s_year, ignore_season=ignore_s) and \
           _identity_leakage(item.get("origin_name", ""), query, ignore_year=s_year, ignore_season=ignore_s):
            return -4800

    # 6. Title similarity
    n_query = normalize_text(query)
    if n_query and (n_query == n_name or n_query == n_origin):
        score += 1000
    elif n_query and (n_query in n_name or n_query in n_origin):
        score += 500
    else:
        if not item_tmdb_str or item_tmdb_str == "0":
            return -2000

    return score


def detect_season(name: str, origin_name: str, year: int, tmdb_info: TmdbSeriesInfo, slug: str = "") -> int | None:
    full = f"{name} {origin_name} {slug}".lower().replace("-", " ")
    m = re.search(r"(ph[aầ]n|season|ss|p)\s*(\d+)", full, re.IGNORECASE)
    if m:
        return int(m.group(2))
    trail = re.search(r"\s(\d+)$", name.strip())
    if trail:
        val = int(trail.group(1))
        if 1 <= val <= 30:
            return val
    if year > 0 and tmdb_info.season_years:
        for s_num, s_year in tmdb_info.season_years.items():
            if s_year > 0 and s_year == year:
                return s_num
        for s_num, s_year in tmdb_info.season_years.items():
            if s_year > 0 and abs(year - s_year) <= 1:
                return s_num
        max_s = max(tmdb_info.season_years.keys())
        if year >= (tmdb_info.series_year + max_s - 1):
            return max_s
    return None


def season_for_abs_ep(ep_num: int, tmdb_info: TmdbSeriesInfo) -> int | None:
    total = 0
    for s in tmdb_info.seasons:
        total += s.episode_count
        if ep_num <= total:
            return s.season_number
    return None
