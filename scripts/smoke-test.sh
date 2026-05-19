#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${TMPDIR:-/tmp}/vn-source-gateway-smoke"
PORT="${PORT:-18765}"
BASE_URL="http://127.0.0.1:${PORT}"

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

cat > "${WORK_DIR}/config.json" <<JSON
{
  "ui_host": "127.0.0.1",
  "ui_port": ${PORT},
  "public_base_url": "${BASE_URL}",
  "torznab_api_key": "secret",
  "qb_username": "admin",
  "qb_password": "pass",
  "source_order": ["embed"],
  "default_output_mode": "strm",
  "expose_both_modes": true,
  "movie_strm_root": "${WORK_DIR}/movies",
  "series_strm_root": "${WORK_DIR}/shows",
  "download_root": "${WORK_DIR}/downloads",
  "state_path": "${WORK_DIR}/state.json",
  "poll_interval_seconds": 3600,
  "hls_template_sources": [
    {
      "name": "embed",
      "movie_url_template": "https://stream.example/{tmdb_id}/{title}.m3u8",
      "series_url_template": "https://stream.example/{tvdb_id}/s{season:02d}e{episode:02d}.m3u8"
    }
  ]
}
JSON

CONFIG_PATH="${WORK_DIR}/config.json" python3 -m vn_source_gateway > "${WORK_DIR}/server.log" 2>&1 &
PID="$!"
trap 'kill "${PID}" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 50); do
  if curl -fsS "${BASE_URL}/api/config" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

curl -fsS "${BASE_URL}/torznab/api?t=caps&apikey=secret" | grep -q "movie-search"
SEARCH_XML="$(curl -fsS "${BASE_URL}/torznab/api?t=movie&apikey=secret&q=Test%20Movie&tmdbid=123&year=2026")"
echo "${SEARCH_XML}" | grep -q "\\[STRM\\]"
echo "${SEARCH_XML}" | grep -q "\\[HLS-DL\\]"
GRAB_URL="$(echo "${SEARCH_XML}" | grep -m1 -o '<link>[^<]*</link>' | sed -e 's#<link>##' -e 's#</link>##')"

curl -fsS -X POST "${BASE_URL}/api/v2/auth/login" -d "username=admin&password=pass" | grep -q "Ok"
curl -fsS -X POST "${BASE_URL}/api/v2/torrents/add" -F "urls=${GRAB_URL}" -F "category=radarr" | grep -q "Ok"

for _ in $(seq 1 50); do
  if [ -f "${WORK_DIR}/movies/Test Movie (2026)/Test Movie (2026).strm" ]; then
    break
  fi
  sleep 0.1
done

test -f "${WORK_DIR}/movies/Test Movie (2026)/Test Movie (2026).strm"
grep -q "https://stream.example/123/Test Movie.m3u8" "${WORK_DIR}/movies/Test Movie (2026)/Test Movie (2026).strm"
curl -fsS "${BASE_URL}/api/v2/torrents/info" | grep -q '"state": "uploading"'
curl -fsS "${BASE_URL}/api/v2/app/preferences" | grep -q '"save_path"'
curl -fsS "${BASE_URL}/api/v2/sync/maindata" | grep -q '"torrents"'

echo "Smoke test passed: ${WORK_DIR}"
