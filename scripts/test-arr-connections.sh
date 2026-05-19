#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${CONFIG_PATH:-${ROOT_DIR}/.local/config/config.json}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8765}"

python3 - "$CONFIG_PATH" "$BASE_URL" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

config_path, base_url = sys.argv[1], sys.argv[2].rstrip("/")

config = {}
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as handle:
        config = json.load(handle)


def require(name: str) -> str:
    env_name = name.upper()
    value = str(os.environ.get(env_name) or config.get(name) or "").strip()
    if not value:
        raise SystemExit(f"Missing {name}. Set {env_name} or save it in {config_path}")
    return value


def optional(name: str, default: str) -> str:
    return str(os.environ.get(name.upper()) or config.get(name) or default)


def request(url: str, method: str = "GET", data: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[int, str]:
    encoded = None
    if data is not None:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {url} failed: HTTP {exc.code}\n{body}") from exc


for app, url_key, key_key in [
    ("Radarr", "radarr_url", "radarr_api_key"),
    ("Sonarr", "sonarr_url", "sonarr_api_key"),
]:
    app_url = require(url_key).rstrip("/")
    api_key = require(key_key)
    status, body = request(f"{app_url}/api/v3/system/status", headers={"X-Api-Key": api_key})
    payload = json.loads(body)
    print(f"{app}: OK {payload.get('version', 'unknown')}")

status, body = request(f"{base_url}/torznab/api?t=caps&apikey={urllib.parse.quote(optional('torznab_api_key', 'vn-source'))}")
if "movie-search" not in body or "tv-search" not in body:
    raise SystemExit("Torznab caps did not include movie-search and tv-search")
print("VN Source Torznab: OK")

status, body = request(
    f"{base_url}/api/v2/auth/login",
    method="POST",
    data={
        "username": optional("qb_username", "admin"),
        "password": optional("qb_password", "adminadmin"),
    },
)
if "Ok" not in body:
    raise SystemExit("qBittorrent-compatible login did not return Ok")
print("VN Source download client API: OK")
PY
