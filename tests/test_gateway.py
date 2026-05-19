"""Tests for gateway.py — encode/decode release URL tokens."""
from __future__ import annotations

import pytest
from vn_source_gateway.application.grab_service import decode_release, decode_release_from_url, encode_release
from vn_source_gateway.domain.models import GatewayRelease


def _make_release(**kwargs) -> GatewayRelease:
    defaults = dict(
        title="Test Movie",
        kind="movie",
        output_mode="strm",
        source_name=None,
        query="Test Movie",
        year=2022,
        tmdb_id=12345,
    )
    defaults.update(kwargs)
    return GatewayRelease(**defaults)


class TestEncodeDecodeRelease:
    def test_roundtrip_movie(self):
        release = _make_release()
        token = encode_release(release)
        decoded = decode_release(token)
        assert decoded == release

    def test_roundtrip_episode(self):
        release = _make_release(
            title="Test Series",
            kind="episode",
            query="Test Series",
            year=2022,
            tmdb_id=None,
            tvdb_id=456789,
            season_number=2,
            episode_number=5,
        )
        token = encode_release(release)
        decoded = decode_release(token)
        assert decoded == release

    def test_token_is_url_safe(self):
        release = _make_release(title="Phim Việt Nam: Special/Edition")
        token = encode_release(release)
        # URL-safe base64 must not contain + or /
        assert "+" not in token
        assert "/" not in token

    def test_encode_is_deterministic(self):
        release = _make_release()
        assert encode_release(release) == encode_release(release)

    def test_roundtrip_with_none_fields(self):
        release = _make_release(tmdb_id=None, imdb_id=None)
        decoded = decode_release(encode_release(release))
        assert decoded.tmdb_id is None
        assert decoded.imdb_id is None

    def test_roundtrip_special_chars_in_title(self):
        release = _make_release(title='Title with "quotes" & <symbols>')
        decoded = decode_release(encode_release(release))
        assert decoded.title == release.title


class TestDecodeFromUrl:
    def test_grab_url(self):
        release = _make_release()
        token = encode_release(release)
        url = f"http://localhost:8765/grab/{token}"
        decoded = decode_release_from_url(url)
        assert decoded == release

    def test_grab_url_with_query_params(self):
        release = _make_release()
        token = encode_release(release)
        url = f"http://localhost:8765/grab/{token}?foo=bar"
        decoded = decode_release_from_url(url)
        assert decoded == release

    def test_grab_url_with_trailing_slash(self):
        release = _make_release()
        token = encode_release(release)
        url = f"http://localhost:8765/grab/{token}/"
        decoded = decode_release_from_url(url)
        assert decoded == release

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Unsupported grab URL"):
            decode_release_from_url("http://localhost:8765/no-grab-here")
