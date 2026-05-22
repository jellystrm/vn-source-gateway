from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from backend.infrastructure.config import Settings

log = logging.getLogger(__name__)
router = APIRouter()


def _season_ep_count(tmdb_id: int | None, season: int, settings: Any) -> int | None:
    if not tmdb_id or not settings.tmdb_api_key:
        return None
    from backend.adapters.tmdb import TmdbClient
    try:
        info = TmdbClient(settings.tmdb_api_key).get_series_info(tmdb_id)
        for s in (info.seasons or []):
            if s.season_number == season:
                return s.episode_count
    except Exception:
        pass
    return None


def _season_plan(tmdb_id: int | None, season: int | None, episode: int | None, settings: Any) -> tuple[list[tuple[int, list[int]]], list[str]]:
    notes: list[str] = []
    info = None
    if tmdb_id and settings.tmdb_api_key:
        from backend.adapters.tmdb import TmdbClient
        try:
            info = TmdbClient(settings.tmdb_api_key).get_series_info(tmdb_id)
        except Exception:
            info = None

    if season is None:
        season_numbers = [s.season_number for s in (getattr(info, "seasons", None) or []) if s.season_number > 0]
        if not season_numbers:
            season_numbers = [1]
            notes.append("No season selected and TMDB season list unavailable; scanning season 1 only")
        else:
            notes.append(f"No season selected; scanning {len(season_numbers)} season(s)")
    else:
        season_numbers = [season]

    plan: list[tuple[int, list[int]]] = []
    total = 0
    max_episodes = 200
    for season_num in season_numbers:
        if episode is not None:
            eps = [episode]
        else:
            count = None
            if info:
                for s in info.seasons:
                    if s.season_number == season_num:
                        count = s.episode_count
                        break
            count = count or _season_ep_count(tmdb_id, season_num, settings) or 13
            eps = list(range(1, count + 1))

        remaining = max_episodes - total
        if remaining <= 0:
            break
        if len(eps) > remaining:
            eps = eps[:remaining]
            notes.append(f"Scan capped at {max_episodes} episode(s)")
        total += len(eps)
        plan.append((season_num, eps))
    return plan, notes


def _resolve_ep_fresh(
    tmdb_api_key: str, source_name: str,
    title: str, year: int | None, tmdb_id: int | None,
    tvdb_id: int | None, season: int, ep_num: int,
) -> tuple[list, list[str]]:
    from backend.sources import build_sources
    from backend.domain.models import EpisodeWanted
    src = build_sources(tmdb_api_key=tmdb_api_key).get(source_name)
    if not src:
        return [], []
    wanted = EpisodeWanted(
        sonarr_episode_id=0, series_id=0, series_title=title, episode_title="",
        year=year, tmdb_id=tmdb_id, tvdb_id=tvdb_id, tvdb_episode_id=None,
        imdb_id=None, season_number=season, episode_number=ep_num,
    )
    hits = src.resolve_episode_all(wanted)
    return hits, list(getattr(src, "_last_log", []))


@router.post("/api/source-test")
async def source_test(request: Request) -> Response:
    try:
        params = await request.json()
    except Exception:
        return Response(status_code=400, content="Invalid JSON")

    settings = Settings.load()
    # Optional: restrict to a single source (used by "Test resolve" per-source button)
    only_source: str | None = str(params["source_name"]) if params.get("source_name") else None
    tmdb_id_raw = params.get("tmdb_id")
    tmdb_id = int(tmdb_id_raw) if tmdb_id_raw else None
    media_type = str(params.get("media_type", "movie"))
    season_raw = params.get("season")
    episode_raw = params.get("episode")
    tvdb_id_raw = params.get("tvdb_id")
    season: int | None = int(season_raw) if season_raw not in (None, "") else None
    episode: int | None = int(episode_raw) if episode_raw not in (None, "") else None
    tvdb_id: int | None = int(tvdb_id_raw) if tvdb_id_raw else None
    title = str(params.get("title") or "").strip()
    year_raw = params.get("year")
    year = int(year_raw) if year_raw else None

    scan_mode = (media_type == "tv" and (season is None or episode is None))
    eff_season = season if season is not None else 1
    eff_episode = episode if episode is not None else 1
    test_log: list[str] = [
        f"input: media_type={media_type}, tmdb_id={tmdb_id}, title={title!r}, "
        f"year={year}, season={season}, episode={episode}, tvdb_id={tvdb_id}",
    ]

    from backend.sources import build_sources
    from backend.adapters.tmdb import TmdbClient
    from backend.domain.models import MovieWanted, EpisodeWanted

    if settings.tmdb_api_key:
        tmdb = TmdbClient(settings.tmdb_api_key)
        # Auto-resolve TMDB ID from TVDB ID when only tvdb_id is provided
        # (mirrors real Sonarr behaviour — Sonarr only sends tvdbid, not tmdbid)
        if not tmdb_id and tvdb_id and media_type == "tv":
            resolved = tmdb.tmdb_id_for_tvdb(tvdb_id)
            if resolved:
                tmdb_id = resolved
                test_log.append(f"tvdb_id={tvdb_id} → tmdb_id={tmdb_id} (resolved via TMDB /find)")
            else:
                test_log.append(f"tvdb_id={tvdb_id} → could not resolve tmdb_id via TMDB")

        if tmdb_id:
            if media_type == "movie":
                info = tmdb.get_movie_info(tmdb_id)
                if info:
                    title = title or info.title or ""
                    year = year or info.series_year or None
                    test_log.append(f"TMDB movie metadata: title={info.title!r}, year={info.series_year}")
                else:
                    test_log.append("TMDB movie metadata lookup returned nothing")
            else:
                info = tmdb.get_series_info(tmdb_id)
                title = title or info.title or ""
                year = year or info.series_year or None
                test_log.append(
                    f"TMDB series metadata: title={info.title!r}, year={info.series_year}, "
                    f"seasons={info.total_seasons}, episodes={info.total_episodes}"
                )
    elif tmdb_id or tvdb_id:
        test_log.append("TMDB API key not configured; add Title/Year manually")

    sources = build_sources(tmdb_api_key=settings.tmdb_api_key)
    if only_source:
        sources = {k: v for k, v in sources.items() if k == only_source}
    results: dict[str, dict] = {}

    if scan_mode:
        plan, plan_notes = _season_plan(tmdb_id, season, episode, settings)
        test_log.extend(plan_notes)
        test_log.append(
            "Scanning "
            + ", ".join(f"S{s:02d}: {len(eps)} episode(s)" for s, eps in plan)
        )
        for source_name in sources:
            ep_map: dict[tuple[int, int], list] = {}
            ep_log_map: dict[tuple[int, int], list[str]] = {}
            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = {
                    pool.submit(
                        _resolve_ep_fresh,
                        settings.tmdb_api_key, source_name, title, year, tmdb_id, tvdb_id,
                        season_num, ep_num,
                    ): (season_num, ep_num)
                    for season_num, ep_nums in plan
                    for ep_num in ep_nums
                }
                for f in as_completed(futs):
                    key = futs[f]
                    try:
                        hits, ep_log = f.result()
                        ep_map[key] = hits
                        ep_log_map[key] = ep_log
                    except Exception:
                        ep_map[key] = []
            episodes_out = [
                {"season": s, "num": ep, "url": ep_map[(s, ep)][0].hls_url if ep_map[(s, ep)] else None}
                for s, ep in sorted(ep_map)
            ]
            found = sum(1 for e in episodes_out if e["url"])

            # Include the log from the first resolved episode (hit or miss)
            # so the sandbox shows resolve trace, not just the plan summary.
            first_hit_key = next((k for k in sorted(ep_map) if ep_map[k]), None)
            first_miss_key = next((k for k in sorted(ep_map) if not ep_map[k]), None)
            sample_key = first_hit_key or first_miss_key
            sample_ep_log = ep_log_map.get(sample_key, []) if sample_key else []
            if sample_key:
                s, e = sample_key
                sample_ep_log = [f"── Sample: S{s:02d}E{e:02d} ──"] + sample_ep_log

            results[source_name] = {
                "status": "ok" if found > 0 else "error",
                "message": None if found > 0 else "Not found",
                "episodes": episodes_out,
                "found": found,
                "total": sum(len(eps) for _, eps in plan),
                "log": test_log + sample_ep_log,
            }
    else:
        for source_name, source in sources.items():
            try:
                if media_type == "movie":
                    wanted: MovieWanted | EpisodeWanted = MovieWanted(
                        radarr_id=0, title=title, year=year, tmdb_id=tmdb_id, imdb_id=None
                    )
                    hits = source.resolve_movie_all(wanted)  # type: ignore[arg-type]
                else:
                    wanted = EpisodeWanted(
                        sonarr_episode_id=0, series_id=0, series_title=title, episode_title="",
                        year=year, tmdb_id=tmdb_id, tvdb_id=tvdb_id, tvdb_episode_id=None,
                        imdb_id=None, season_number=eff_season, episode_number=eff_episode,
                    )
                    hits = source.resolve_episode_all(wanted)  # type: ignore[arg-type]
                source_log = test_log + list(getattr(source, "_last_log", []))
                if hits:
                    urls = [{"url": h.hls_url, "server": h.server_name, "name": h.item_name} for h in hits]
                    results[source_name] = {"status": "ok", "url": hits[0].hls_url, "urls": urls, "log": source_log}
                else:
                    results[source_name] = {"status": "error", "message": "Not found", "log": source_log}
            except Exception as exc:
                source_log = test_log + list(getattr(source, "_last_log", [])) + [f"exception: {exc}"]
                results[source_name] = {"status": "error", "message": str(exc)[:200], "log": source_log}

    return JSONResponse(results)
