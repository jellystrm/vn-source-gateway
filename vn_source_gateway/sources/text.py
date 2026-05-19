from __future__ import annotations

import re
import unicodedata
from typing import Any

_META_TOKENS = {
    "vietsub", "long", "tieng", "thuyet", "minh", "phu", "de", "cam",
    "hd", "bluray", "full", "raw", "re", "ux", "remux", "fhd", "4k", "uhd",
    "tap", "phim", "le", "bo", "episode", "ep", "ss", "season", "phan",
    "the", "a", "an", "is", "of", "and", "or", "vostfr", "sub", "dual",
    "multi", "web", "dl",
}

_VI_PATTERN = re.compile(
    r'^[a-zA-Z0-9\s.,!?:;\-\(\)'
    r'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩ'
    r'òóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐ]+$'
)


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower().replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", t)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", ascii_str)).strip()


def _tokens(text: str) -> set[str]:
    return set(normalize_text(text).split())


def _identity_leakage(result_title: str, query_title: str, ignore_year: int = 0, ignore_season: int = 0) -> bool:
    """True if result has significant extra tokens not in query (sequel/spinoff detection)."""
    diff = _tokens(result_title) - _tokens(query_title) - _META_TOKENS
    if ignore_year and str(ignore_year) in diff:
        diff.discard(str(ignore_year))
    if ignore_season and str(ignore_season) in diff:
        diff.discard(str(ignore_season))
    return len(diff) > 0


def _is_supported_lang(text: str) -> bool:
    return bool(text and _VI_PATTERN.match(text))


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        m = re.search(r"\d+", str(value))
        return int(m.group()) if m else default
    except (ValueError, TypeError):
        return default
