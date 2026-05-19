from __future__ import annotations

import hashlib
from email.utils import formatdate
from html import escape as xml_escape

from vn_source_gateway.application.grab_service import encode_release
from vn_source_gateway.domain.models import GatewayRelease, OutputMode
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

    is_tv = t == "tvsearch" or season is not None or episode is not None or tvdb_id is not None
    kind = "episode" if is_tv else "movie"
    title = q or (f"TVDB {tvdb_id}" if is_tv and tvdb_id else "") or (f"TMDB {tmdb_id}" if tmdb_id else "") or "VN Source"
    modes: list[OutputMode] = ["strm", "download"] if settings.expose_both_modes else [_output_mode(settings.default_output_mode)]

    releases: list[GatewayRelease] = []
    for source_name in settings.source_order:
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
                    episode_number=episode,
                )
            )
    return releases


def _release_item(settings: Settings, release: GatewayRelease) -> str:
    token = encode_release(release)
    mode_label = "STRM" if release.output_mode == "strm" else "HLS-DL"
    source_label = release.source_name or "source"
    year = f" {release.year}" if release.year else ""
    ep = ""
    if release.kind == "episode" and release.season_number is not None and release.episode_number is not None:
        ep = f" S{release.season_number:02d}E{release.episode_number:02d}"
    title = f"{release.title}{year}{ep} 1080p VN {source_label} [{mode_label}]"
    link = f"{settings.public_base_url}/grab/{token}"
    category = "5000" if release.kind == "episode" else "2000"
    subcategory = "5040" if release.kind == "episode" else "2040"
    size = 1024 * 1024 * 1024
    attrs = [
        f'<torznab:attr name="category" value="{category}"/>',
        f'<torznab:attr name="category" value="{subcategory}"/>',
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
