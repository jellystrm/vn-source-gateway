"""Tests for sources/text.py — normalize, tokenize, identity leakage."""
from __future__ import annotations

import pytest
from vn_source_gateway.sources.text import (
    _identity_leakage,
    _is_supported_lang,
    _safe_int,
    _tokens,
    normalize_text,
)


class TestNormalizeText:
    def test_empty(self):
        assert normalize_text("") == ""

    def test_latin(self):
        assert normalize_text("Hello World") == "hello world"

    def test_vietnamese_accents_stripped(self):
        result = normalize_text("Phim Việt Nam")
        assert result == "phim viet nam"

    def test_d_with_stroke(self):
        # đ → d
        assert normalize_text("Đặc biệt") == "dac biet"

    def test_special_chars_become_spaces(self):
        result = normalize_text("The Dark Knight (2008)")
        assert result == "the dark knight 2008"

    def test_numbers_preserved(self):
        assert normalize_text("Avengers 2012") == "avengers 2012"

    def test_strips_leading_trailing(self):
        assert normalize_text("  hello  ") == "hello"


class TestTokens:
    def test_basic(self):
        assert _tokens("hello world") == {"hello", "world"}

    def test_vietnamese(self):
        result = _tokens("Phim Việt")
        assert "phim" in result
        assert "viet" in result

    def test_deduplicates(self):
        assert _tokens("the the the") == {"the"}


class TestIdentityLeakage:
    def test_same_title_no_leakage(self):
        assert _identity_leakage("Squid Game", "Squid Game") is False

    def test_sequel_detected(self):
        # "2" is an extra meaningful token
        assert _identity_leakage("Squid Game 2", "Squid Game") is True

    def test_meta_tokens_ignored(self):
        # "Vietsub" and "HD" are in _META_TOKENS
        assert _identity_leakage("Squid Game Vietsub HD", "Squid Game") is False

    def test_ignore_year(self):
        assert _identity_leakage("Squid Game 2021", "Squid Game", ignore_year=2021) is False

    def test_ignore_season(self):
        assert _identity_leakage("Squid Game 2", "Squid Game", ignore_season=2) is False

    def test_spinoff_detected(self):
        # Extra word "origins" not in query
        assert _identity_leakage("Dragon Ball Origins", "Dragon Ball") is True

    def test_subset_title_no_leakage(self):
        # Result title is a subset of query — no extra tokens
        assert _identity_leakage("Dragon Ball", "Dragon Ball Super") is False


class TestSafeInt:
    def test_none_returns_default(self):
        assert _safe_int(None) == 0
        assert _safe_int(None, default=5) == 5

    def test_int_passthrough(self):
        assert _safe_int(42) == 42

    def test_string_number(self):
        assert _safe_int("12") == 12

    def test_string_with_text(self):
        assert _safe_int("ep12") == 12
        assert _safe_int("12 episodes") == 12

    def test_non_numeric_string(self):
        assert _safe_int("Full") == 0

    def test_float_string(self):
        assert _safe_int("3.14") == 3


class TestIsSupportedLang:
    def test_plain_latin(self):
        assert _is_supported_lang("Avengers") is True

    def test_vietnamese(self):
        assert _is_supported_lang("Phim Việt Nam") is True

    def test_empty(self):
        assert _is_supported_lang("") is False

    def test_chinese_not_supported(self):
        assert _is_supported_lang("中文") is False

    def test_mixed_unsupported(self):
        assert _is_supported_lang("Hello 中文") is False
