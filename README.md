# vn-source-gateway

HLS source gateway for Radarr/Sonarr/Jellyseerr workflows.

It can run in two ways:

```text
Direct gateway mode:
Radarr/Sonarr -> Torznab indexer -> qBittorrent-compatible endpoint -> STRM or HLS download

Polling fallback mode:
Radarr/Sonarr wanted list -> worker poll -> HLS download -> Radarr/Sonarr import
```

The qBittorrent-compatible endpoint is only an API compatibility layer so Radarr/Sonarr can send grabs without patching their core. Internally this service either creates `.strm` files containing HLS URLs, or downloads HLS with `ffmpeg` to `.mkv`/`.mp4`.

Use this only with sources you are legally allowed to access and archive. Sources are configured via direct HLS templates or resolver endpoints you control; this service does not bypass DRM, login walls, token systems, or anti-bot protections.

## Quick Start

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

Open:

```text
http://localhost:8765
```

## Add To Radarr/Sonarr

Add the indexer:

```text
Settings -> Indexers -> Add -> Torznab -> Custom

Name: VN Source
URL: http://vn-source-gateway:8765/torznab/api
API Key: value from service UI, default vn-source
Categories: 2000,2040,5000,5040
```

Add the download client:

```text
Settings -> Download Clients -> Add -> qBittorrent

Name: VN Source
Host: vn-source-gateway
Port: 8765
Username: value from service UI, default admin
Password: value from service UI, default adminadmin
Category: vn-source
```

The service implements the qBittorrent Web API endpoints Radarr/Sonarr commonly use for testing, adding, tracking, pausing/resuming, and deleting jobs:

```text
/api/v2/auth/login
/api/v2/app/version
/api/v2/app/webapiVersion
/api/v2/app/preferences
/api/v2/app/buildInfo
/api/v2/torrents/add
/api/v2/torrents/info
/api/v2/torrents/properties
/api/v2/torrents/files
/api/v2/torrents/delete
/api/v2/torrents/pause
/api/v2/torrents/resume
/api/v2/torrents/categories
/api/v2/sync/maindata
/api/v2/transfer/info
```

Manual search will show releases like:

```text
Movie 2026 1080p VN my-source [STRM]
Movie 2026 1080p VN my-source [HLS-DL]
```

`[STRM]` writes a `.strm` file. `[HLS-DL]` downloads the HLS stream with `ffmpeg`.

## Important Paths

For STRM mode:

```text
MOVIE_STRM_ROOT=/movies
SERIES_STRM_ROOT=/shows
```

These should be Jellyfin library paths.

For HLS download mode:

```text
DOWNLOAD_ROOT=/downloads/vn
```

This path should be visible to Radarr/Sonarr if you want them to import completed downloads.

## Supported Sources

Template/resolver based:

```text
vidsrc
embed
any custom name
```

Example direct HLS template:

```json
[
  {
    "name": "embed",
    "movie_url_template": "https://resolver.example/movie/{tmdb_id}.m3u8",
    "series_url_template": "https://resolver.example/tv/{tvdb_id}/s{season:02d}e{episode:02d}.m3u8",
    "headers": {
      "Referer": "https://resolver.example/"
    }
  }
]
```

Example resolver endpoint:

```json
[
  {
    "name": "vidsrc",
    "movie_resolver_url_template": "http://my-resolver:7000/movie/{tmdb_id}",
    "series_resolver_url_template": "http://my-resolver:7000/tv/{tvdb_id}/{season}/{episode}"
  }
]
```

Resolver endpoints can return plain text containing a `.m3u8` URL, or JSON:

```json
{
  "hls_url": "https://example/master.m3u8",
  "headers": {
    "Referer": "https://example/"
  }
}
```

Available template fields:

```text
title, year, tmdb_id, tvdb_id, imdb_id, season, episode
```

## Local Smoke Test

```bash
cd vn-source-gateway
python3 -m vn_source_gateway --once
```

Full gateway smoke test:

```bash
./scripts/smoke-test.sh
```

Start the UI locally:

```bash
./run
```

## Environment

| Variable | Default | Notes |
|---|---:|---|
| `CONFIG_PATH` | `/config/config.json` | UI-managed config file |
| `UI_ENABLED` | `true` | Enables the built-in config UI |
| `UI_HOST` | `0.0.0.0` | UI listen host |
| `UI_PORT` | `8765` | UI listen port |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8765` | Base URL embedded in Torznab release links |
| `TORZNAB_API_KEY` | `vn-source` | Indexer API key |
| `QB_USERNAME` | `admin` | qBittorrent-compatible username |
| `QB_PASSWORD` | `adminadmin` | qBittorrent-compatible password |
| `DEFAULT_OUTPUT_MODE` | `strm` | `strm` or `download` |
| `EXPOSE_BOTH_MODES` | `true` | Return both `[STRM]` and `[HLS-DL]` releases |
| `MOVIE_STRM_ROOT` | `/movies` | Movie STRM library path |
| `SERIES_STRM_ROOT` | `/shows` | Series STRM library path |
| `DOWNLOAD_ROOT` | `/downloads/vn` | HLS download staging path |
| `DOWNLOAD_CONTAINER` | `mkv` | `mkv` or `mp4` |
| `TMDB_API_KEY` | empty | Required for TV resolution via Torznab (TVDB → TMDB lookup). Get free at themoviedb.org |
| `SOURCE_ORDER` | `kkphim,ophim` | Comma-separated source names; built-ins are `kkphim` and `ophim` |
| `HLS_TEMPLATE_SOURCES_JSON` | empty | Adds custom HLS resolver endpoints you control |
| `JELLYFIN_URL` | empty | Optional Jellyfin URL |
| `JELLYFIN_API_KEY` | empty | Optional Jellyfin API key |
| `JELLYFIN_SCAN_AFTER_STRM` | `false` | Call Jellyfin scan after STRM creation |
| `FFMPEG_PATH` | `ffmpeg` | ffmpeg binary |
| `FFMPEG_EXTRA_ARGS` | empty | Comma-separated ffmpeg args |
| `STATE_PATH` | `/state/state.json` | Job and polling state |
| `LOG_LEVEL` | `INFO` | Python logging level |
