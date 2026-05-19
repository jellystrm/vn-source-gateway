from __future__ import annotations

import hashlib
from email.utils import formatdate
from html import escape as xml_escape

from vn_source_gateway.adapters.tmdb import TmdbClient
from vn_source_gateway.adapters.tvmaze import TVMazeClient
from vn_source_gateway.application.grab_service import encode_release
from vn_source_gateway.domain.models import GatewayRelease, OutputMode
from vn_source_gateway.infrastructure.activity import ActivityLog
from vn_source_gateway.infrastructure.config import Settings


def caps_response() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<caps>
  <server version="1.0" title="VN Source Gateway"/>
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
    releases = build_releases(settings, query)
    t = _first(query, "t", "search")
    if t != "caps":
        q = _first(query, "q", "").strip()
        tmdb_id = _first(query, "tmdbid", "")
        tvdb_id = _first(query, "tvdbid", "")
        kind = "TV" if (t == "tvsearch" or tvdb_id) else "Movie"
        label = q or (f"TMDB {tmdb_id}" if tmdb_id else "") or (f"TVDB {tvdb_id}" if tvdb_id else "") or "(no query)"
        result_titles = [_release_display_title(r) for r in releases]
        ActivityLog.get().add(
            kind="search",
            title=f"{kind}: {label}",
            detail=f"{len(releases)} result(s) — sources: {', '.join(settings.source_order) or 'none'}",
            status="ok" if releases else "error",
            results=result_titles,
        )
    items = "\n".join(_release_item(settings, release) for release in releases)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <title>VN Source Gateway</title>
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

    # Source list: None = auto-select from source_order at grab time (grouped mode)
    if settings.torznab_group_sources or not settings.source_order:
        source_list: list[str | None] = [None]
    else:
        source_list = list(settings.source_order)

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

    # ── Season pack items (at the top): one per (server_label × source × mode)
    if kind == "episode" and season is not None and episode is None:
        for server_label in server_labels:
            for source_name in source_list:
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
        for server_label in server_labels:
            for source_name in source_list:
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
    if tvdb_id is not None:
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
