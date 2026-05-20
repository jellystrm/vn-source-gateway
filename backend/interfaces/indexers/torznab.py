from __future__ import annotations

import hashlib
import re
import threading
import time
import unicodedata
from email.utils import formatdate
from html import escape as xml_escape

from backend.adapters.tmdb import TmdbClient
from backend.adapters.tvmaze import TVMazeClient
from backend.application.grab_service import encode_release
from backend.domain.models import EpisodeWanted, GatewayRelease, MovieWanted, OutputMode
from backend.infrastructure.activity import ActivityLog
from backend.infrastructure.config import Settings

# ── Source availability cache ────────────────────────────────────────────────
# key → (monotonic_ts, {source_name: [matched_server_labels]} | None)
# None means the check timed out / errored → caller should fall back to all sources.
_src_cache: dict[str, tuple[float, dict[str, list[str]] | None]] = {}
_src_cache_lock = threading.Lock()
_SRC_CACHE_TTL = 300.0   # 5 minutes
_SRC_CHECK_TIMEOUT = 6.0  # per-source probe timeout (seconds)


def _norm_label(s: str) -> str:
    """Lowercase + strip diacritics for fuzzy server label matching."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _available_sources(
    settings: Settings,
    title: str,
    kind: str,
    tmdb_id: int | None,
    tvdb_id: int | None,
    season: int | None,
    episode: int | None,
) -> dict[str, list[str]] | None:
    """Probe all configured sources in parallel.

    Return values:
    - ``{source: [server_labels, ...]}`` — for each source that has the content,
       lists which configured ``server_labels`` are actually present on that source.
       An empty dict means all sources completed but none found the content.
    - ``None`` — at least one probe timed out with no results; caller should fall
       back to all sources × all labels so we don't silently hide content.

    The server-label list for a source may contain all configured labels when the
    source has content but its server names don't match any label (fallback: show
    all options rather than hiding content).

    Results are cached for 5 minutes at season-level granularity so all per-episode
    requests inside the same season share a single round of HTTP checks.
    """
    if not settings.source_order:
        return {}

    # Can't verify without a real title (test/caps queries, unresolved IDs)
    placeholder = re.match(r"^(TMDB|TVDB|VN Source)\s*\d*$", title.strip())
    if not title or placeholder:
        return None  # fall back: show all sources

    server_labels: list[str] = settings.server_labels if settings.server_labels else [""]

    id_part = str(tmdb_id or tvdb_id or re.sub(r"[^a-z0-9]", "", title.lower())[:40])
    cache_key = f"{kind}:{id_part}:{season or ''}"

    now = time.monotonic()
    with _src_cache_lock:
        cached = _src_cache.get(cache_key)
        if cached and now - cached[0] < _SRC_CACHE_TTL:
            return cached[1]

    from backend.sources import build_sources

    sources_map = build_sources(settings.hls_template_sources, tmdb_api_key=settings.tmdb_api_key)
    check_season  = season  or 1
    check_episode = episode or 1

    # Results per source:
    #   list[str] → matched server_labels (may be empty if content not found)
    #   None      → probe errored/timed out
    probe_results: dict[str, list[str] | None] = {}
    results_lock = threading.Lock()

    def probe(source_name: str) -> None:
        source_obj = sources_map.get(source_name)
        if not source_obj:
            with results_lock:
                probe_results[source_name] = []
            return
        try:
            if kind == "movie":
                wanted: MovieWanted | EpisodeWanted = MovieWanted(
                    radarr_id=0, title=title, year=None,
                    tmdb_id=tmdb_id, imdb_id=None,
                )
                hits = source_obj.resolve_movie_all(wanted)  # type: ignore[arg-type]
            else:
                wanted = EpisodeWanted(
                    sonarr_episode_id=0, series_id=0, series_title=title,
                    episode_title="", year=None,
                    tmdb_id=tmdb_id, tvdb_id=tvdb_id, imdb_id=None,
                    season_number=check_season, episode_number=check_episode,
                )
                hits = source_obj.resolve_episode_all(wanted)  # type: ignore[arg-type]

            if not hits:
                with results_lock:
                    probe_results[source_name] = []
                return

            # No server label distinction → content found is enough
            if server_labels == [""]:
                with results_lock:
                    probe_results[source_name] = [""]
                return

            # Match each configured label against the actual server names returned
            hit_server_names = [h.server_name or "" for h in hits if h.server_name]
            matched: list[str] = []
            for label in server_labels:
                kw = _norm_label(label)
                if any(kw and kw in _norm_label(sname) for sname in hit_server_names):
                    matched.append(label)

            # Fallback: source has the content but its server names don't match any
            # configured label → show all labels rather than silently hiding content.
            if not matched:
                matched = list(server_labels)

            with results_lock:
                probe_results[source_name] = matched
        except Exception:
            with results_lock:
                probe_results[source_name] = None  # error → treated like timeout

    threads = [
        threading.Thread(target=probe, args=(name,), daemon=True)
        for name in settings.source_order
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_SRC_CHECK_TIMEOUT)

    any_timeout = any(t.is_alive() for t in threads)

    # Build available dict preserving source_order
    available: dict[str, list[str]] = {
        name: probe_results[name]  # type: ignore[assignment]
        for name in settings.source_order
        if probe_results.get(name)  # non-None and non-empty
    }

    # If any source timed out and we found nothing, we can't trust the result —
    # return None so the caller falls back to showing all sources × all labels.
    final: dict[str, list[str]] | None
    if any_timeout and not available:
        final = None
    else:
        final = available

    with _src_cache_lock:
        _src_cache[cache_key] = (now, final)
        if len(_src_cache) > 500:   # prune stale entries
            cutoff = now - _SRC_CACHE_TTL
            for k in [k for k, v in _src_cache.items() if v[0] < cutoff]:
                _src_cache.pop(k, None)

    return final


def caps_response() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<caps>
  <server version="1.0" title="Deceptarr"/>
  <limits max="100" default="50"/>
  <searching>
    <search available="yes" supportedParams="q"/>
    <movie-search available="yes" supportedParams="q,imdbid,tmdbid"/>
    <tv-search available="yes" supportedParams="q,tvdbid,season,ep"/>
  </searching>
  <categories>
    <category id="2000" name="Movies">
      <subcat id="2040" name="Movies/HD"/>
    </category>
    <category id="5000" name="TV">
      <subcat id="5040" name="TV/HD"/>
    </category>
  </categories>
</caps>"""


def search_response(settings: Settings, query: dict[str, list[str]]) -> str:
    from urllib.parse import urlencode
    releases = build_releases(settings, query)
    t = _first(query, "t", "search")
    if t != "caps":
        q = _first(query, "q", "").strip()
        tmdb_id = _first(query, "tmdbid", "")
        tvdb_id = _first(query, "tvdbid", "")
        kind = "TV" if (t == "tvsearch" or tvdb_id) else "Movie"
        # Use the title already resolved inside build_releases (first release has it)
        resolved_title = (releases[0].title if releases else None) or q
        fallback = (f"TMDB {tmdb_id}" if tmdb_id else "") or (f"TVDB {tvdb_id}" if tvdb_id else "") or ""
        display_title = resolved_title if resolved_title and resolved_title not in {"VN Source"} else fallback
        # Reconstruct the full query URL so the user can inspect results in a browser
        flat = {k: v[0] for k, v in query.items() if v}
        query_url = f"{settings.public_base_url}/torznab/api?{urlencode(flat)}"
        # Skip logging test/RSS queries (no real show identifier)
        if display_title:
            result_titles = [_release_display_title(r) for r in releases]
            result_grabs = [_release_grab_payload(r) for r in releases]
            ActivityLog.get().add(
                kind="search",
                title=f"{kind}: {display_title}",
                detail=f"{len(releases)} result(s) — sources: {', '.join(settings.source_order) or 'none'}",
                status="ok" if releases else "error",
                results=result_titles,
                url=query_url,
                grabs=result_grabs,
            )
    items = "\n".join(_release_item(settings, release) for release in releases)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <title>Deceptarr</title>
    <description>HLS to STRM or HLS download gateway</description>
    {items}
  </channel>
</rss>"""


def build_releases(settings: Settings, query: dict[str, list[str]]) -> list[GatewayRelease]:
    t = _first(query, "t", "search")
    q = _first(query, "q", "").strip()
    imdb_id = _first(query, "imdbid", "").strip() or None
    tmdb_id = _int_or_none(_first(query, "tmdbid", ""))
    tvdb_id = _int_or_none(_first(query, "tvdbid", ""))
    season = _int_or_none(_first(query, "season", ""))
    episode = _int_or_none(_first(query, "ep", ""))
    year = _int_or_none(_first(query, "year", ""))

    # Determine kind:
    # 1. Explicit search type (t=movie / t=tvsearch) takes highest priority.
    # 2. TV-specific params (tvdbid, season, ep) → TV.
    # 3. For t=search (generic), use the cat= parameter that Radarr/Sonarr always send:
    #    cat contains 5xxx → TV; cat contains 2xxx → movie.
    # 4. tmdbid without other TV signals → movie (Radarr sends tmdbid for movies).
    cats = {c.strip() for c in _first(query, "cat", "").split(",") if c.strip()}
    is_tv_by_cat = bool(cats & {"5000", "5040"}) and not bool(cats & {"2000", "2040"})
    is_tv = (
        t == "tvsearch"
        or season is not None
        or episode is not None
        or tvdb_id is not None
        or (t not in {"movie"} and is_tv_by_cat)
    )
    kind = "episode" if is_tv else "movie"
    title = q or _resolve_title(settings, tmdb_id, tvdb_id, is_tv) or "VN Source"
    year = year or _resolve_year(settings, tmdb_id, tvdb_id, is_tv)
    modes: list[OutputMode] = ["strm", "download"] if settings.expose_both_modes else [_output_mode(settings.default_output_mode)]

    # Server labels: empty list means no server distinction (single label "")
    server_labels: list[str] = settings.server_labels if settings.server_labels else [""]

    # ── Source + server-label pairs: verify which sources have this content
    #    and which server labels (ViệtSub / Lồng Tiếng / …) each source offers.
    #
    # _available_sources() probes all configured sources in parallel (≤6 s) using
    # resolve_movie_all() / resolve_episode_all(), then matches each SourceHit's
    # server_name against the configured server_labels.
    #
    # Returns:
    #   dict {source: [labels]}  — sources that have the content and their matched labels
    #   None                     — timeout / placeholder → fall back to all combinations
    if not settings.source_order:
        return []  # no sources configured

    # src_server_pairs: ordered list of (source_name | None, server_label) to generate
    src_server_pairs: list[tuple[str | None, str]]

    if settings.torznab_group_sources:
        # Legacy grouped mode: single auto-select entry per server_label.
        src_server_pairs = [(None, lbl) for lbl in server_labels]
    else:
        verified = _available_sources(
            settings, title, kind, tmdb_id, tvdb_id, season, episode
        )
        if verified is None:
            # Couldn't verify (timeout / placeholder title) → show all combinations
            src_server_pairs = [
                (src, lbl)
                for src in settings.source_order
                for lbl in server_labels
            ]
        elif not verified:
            # All sources completed and none have this content → empty feed
            return []
        else:
            # Only generate releases for (source, server_label) pairs that actually exist
            src_server_pairs = [
                (src, lbl)
                for src, lbls in verified.items()
                for lbl in lbls
            ]

    # ── Season expansion: when season given but no specific episode,
    #    expand to per-episode results so Sonarr tracks each episode individually.
    episode_numbers: list[int | None] = [episode]
    expanded = False
    if kind == "episode" and season is not None and episode is None:
        ep_list = _fetch_season_episode_numbers(settings, tmdb_id, tvdb_id, season)
        if ep_list:
            episode_numbers = ep_list  # type: ignore[assignment]
            expanded = True

    releases: list[GatewayRelease] = []

    # ── Season pack items (at the top): one per (source × server_label × mode)
    if kind == "episode" and season is not None and episode is None:
        for source_name, server_label in src_server_pairs:
            for mode in modes:
                releases.append(
                    GatewayRelease(
                        title=title,
                        kind=kind,  # type: ignore[arg-type]
                        output_mode=mode,
                        source_name=source_name,
                        query=q or title,
                        year=year,
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        tvdb_id=tvdb_id,
                        season_number=season,
                        episode_number=None,  # season pack marker
                        server_label=server_label,
                    )
                )

    # ── Per-episode items (sorted by episode first)
    for ep_num in episode_numbers:
        # Skip None placeholder ONLY when a season was specified — that case is
        # already covered by the season-pack block above.
        # When season is also None (pure title/test search), allow ep_num=None
        # so at least one result is returned (needed for Sonarr indexer test).
        if kind == "episode" and ep_num is None and season is not None:
            continue  # season pack handled above; skip the placeholder
        for source_name, server_label in src_server_pairs:
            for mode in modes:
                releases.append(
                    GatewayRelease(
                        title=title,
                        kind=kind,  # type: ignore[arg-type]
                        output_mode=mode,
                        source_name=source_name,
                        query=q or title,
                        year=year,
                        tmdb_id=tmdb_id,
                        imdb_id=imdb_id,
                        tvdb_id=tvdb_id,
                        season_number=season,
                        episode_number=ep_num,
                        server_label=server_label,
                    )
                )
    return releases


def _release_display_title(release: GatewayRelease) -> str:
    """Human-readable title string matching what torznab returns in <title>."""
    mode_label = "STRM" if release.output_mode == "strm" else "HLS-DL"
    source_part = f" {release.source_name}" if release.source_name else ""
    server_part = f" [{release.server_label}]" if release.server_label else ""
    year = f" {release.year}" if release.year else ""
    ep = ""
    if release.kind == "episode" and release.season_number is not None:
        if release.episode_number is not None:
            ep = f" S{release.season_number:02d}E{release.episode_number:02d}"
        else:
            ep = f" S{release.season_number:02d}"
    return f"{release.title}{year}{ep} 1080p VN{source_part}{server_part} [{mode_label}]"


def _release_grab_payload(release: GatewayRelease) -> dict:
    return {
        "title": _release_display_title(release),
        "token": encode_release(release),
        "media_kind": release.kind,
        "media_title": release.title,
        "year": release.year,
        "season": release.season_number,
        "episode": release.episode_number,
        "source": release.source_name or "",
        "server": release.server_label,
        "output_mode": release.output_mode,
    }


def _release_item(settings: Settings, release: GatewayRelease) -> str:
    token = encode_release(release)
    mode_label = "STRM" if release.output_mode == "strm" else "HLS-DL"
    source_part = f" {release.source_name}" if release.source_name else ""
    server_part = f" [{release.server_label}]" if release.server_label else ""
    year = f" {release.year}" if release.year else ""

    # Episode / season pack label
    ep = ""
    is_season_pack = False
    if release.kind == "episode" and release.season_number is not None:
        if release.episode_number is not None:
            ep = f" S{release.season_number:02d}E{release.episode_number:02d}"
        else:
            ep = f" S{release.season_number:02d}"  # season pack
            is_season_pack = True

    title = f"{release.title}{year}{ep} 1080p VN{source_part}{server_part} [{mode_label}]"
    link = f"{settings.public_base_url}/grab/{token}"
    if release.kind == "episode":
        categories = ["5000", "5040"]
    else:
        categories = ["2000", "2040"]
    # Season pack size is estimated as 20 episodes × 1 GB; individual = 1 GB
    size = 1024 * 1024 * 1024 * (20 if is_season_pack else 1)
    attrs = [
        *[f'<torznab:attr name="category" value="{c}"/>' for c in categories],
        f'<torznab:attr name="size" value="{size}"/>',
        '<torznab:attr name="seeders" value="999"/>',
        '<torznab:attr name="peers" value="999"/>',
        '<torznab:attr name="leechers" value="0"/>',
        '<torznab:attr name="downloadvolumefactor" value="0"/>',
        '<torznab:attr name="uploadvolumefactor" value="1"/>',
    ]
    if release.imdb_id:
        attrs.append(f'<torznab:attr name="imdb" value="{xml_escape(release.imdb_id)}"/>')
    if release.tmdb_id:
        attrs.append(f'<torznab:attr name="tmdbid" value="{release.tmdb_id}"/>')
    if release.tvdb_id:
        attrs.append(f'<torznab:attr name="tvdbid" value="{release.tvdb_id}"/>')
    return f"""<item>
      <title>{xml_escape(title)}</title>
      <guid isPermaLink="false">vnsource-{hashlib.sha1(token.encode()).hexdigest()}</guid>
      <link>{xml_escape(link)}</link>
      <comments>{xml_escape(link)}</comments>
      <pubDate>{formatdate(usegmt=True)}</pubDate>
      <size>{size}</size>
      <enclosure url="{xml_escape(link)}" length="{size}" type="application/x-bittorrent"/>
      {''.join(attrs)}
    </item>"""


def _first(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    return values[0] if values else default


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _output_mode(value: str) -> OutputMode:
    return "download" if value.lower() in {"download", "hls-dl", "hls_dl"} else "strm"


def _resolve_title(settings: Settings, tmdb_id: int | None, tvdb_id: int | None, is_tv: bool) -> str:
    """Fetch real title from TMDB so Radarr/Sonarr can parse the release."""
    if not settings.tmdb_api_key:
        return f"TMDB {tmdb_id}" if tmdb_id else (f"TVDB {tvdb_id}" if tvdb_id else "")
    tmdb = TmdbClient(settings.tmdb_api_key)
    if not tmdb.enabled:
        return f"TMDB {tmdb_id}" if tmdb_id else (f"TVDB {tvdb_id}" if tvdb_id else "")
    try:
        if is_tv:
            _tmdb_id = tmdb_id or (tmdb.tmdb_id_for_tvdb(tvdb_id) if tvdb_id else None)
            if _tmdb_id:
                info = tmdb.get_series_info(_tmdb_id)
                if info.title:
                    return info.title
        else:
            if tmdb_id:
                result = tmdb.get_movie_title(tmdb_id)
                if result:
                    return result[0]
    except Exception:
        pass
    return f"TMDB {tmdb_id}" if tmdb_id else (f"TVDB {tvdb_id}" if tvdb_id else "")


def _fetch_season_episode_numbers(
    settings: Settings,
    tmdb_id: int | None,
    tvdb_id: int | None,
    season: int,
) -> list[int]:
    """Return ordered episode numbers for a season.

    Strategy:
    - When ``tvdb_id`` is provided, use TVMaze (free, mirrors TVDB numbering)
      because Sonarr sends TVDB season/episode numbers and TMDB seasons can
      differ (e.g. TVDB Season 1 = 24 eps vs TMDB Season 1 + Season 2 = 12 ea).
    - Fall back to TMDB when only ``tmdb_id`` is available (Radarr path, or
      Sonarr configured to use TMDB series IDs).
    - Empty list → caller keeps season-pack behaviour (no per-episode expansion).
    """
    # ── TVDB-aligned path: prefer TVMaze ──────────────────────────────────────
    if tvdb_id:
        try:
            eps = TVMazeClient().get_season_episodes(tvdb_id, season)
            if eps:
                return eps
        except Exception:
            pass
        # TVMaze miss → fall through to TMDB if we can resolve the TMDB ID

    # ── TMDB path ─────────────────────────────────────────────────────────────
    if not settings.tmdb_api_key:
        return []
    tmdb = TmdbClient(settings.tmdb_api_key)
    if not tmdb.enabled:
        return []
    _tmdb_id = tmdb_id or (tmdb.tmdb_id_for_tvdb(tvdb_id) if tvdb_id else None)
    if not _tmdb_id:
        return []
    return tmdb.get_season_episodes(_tmdb_id, season)


def _resolve_year(settings: Settings, tmdb_id: int | None, tvdb_id: int | None, is_tv: bool) -> int | None:
    """Fetch release year from TMDB for the torznab title."""
    if not settings.tmdb_api_key:
        return None
    tmdb = TmdbClient(settings.tmdb_api_key)
    if not tmdb.enabled:
        return None
    try:
        if not is_tv and tmdb_id:
            result = tmdb.get_movie_title(tmdb_id)
            if result:
                return result[1] or None
        if is_tv:
            _tmdb_id = tmdb_id or (tmdb.tmdb_id_for_tvdb(tvdb_id) if tvdb_id else None)
            if _tmdb_id:
                info = tmdb.get_series_info(_tmdb_id)
                return info.series_year or None
    except Exception:
        pass
    return None
