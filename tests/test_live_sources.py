"""
Live integration tests against real phimapi sources.

Skipped by default — opt-in with:
    pytest tests/test_live_sources.py -m live -v -s

Or set LIVE_SOURCES=1:
    LIVE_SOURCES=1 pytest tests/test_live_sources.py -v -s

Each test prints trace logs so you can see exactly why a source fails.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from deceptarr.sources import build_sources
from deceptarr.domain.models import EpisodeWanted, MovieWanted

_LIVE = os.getenv("LIVE_SOURCES") == "1"
pytestmark = pytest.mark.skipif(not _LIVE, reason="set LIVE_SOURCES=1 to run live tests")


# ── helpers ────────────────────────────────────────────────────────────────────

def _sources():
    return build_sources([], tmdb_api_key="")


def _ep(title: str, tmdb_id: int, tvdb_id: int | None,
        season: int, ep: int, year: int) -> EpisodeWanted:
    return EpisodeWanted(
        sonarr_episode_id=0, series_id=0, series_title=title,
        episode_title="", year=year, tmdb_id=tmdb_id,
        tvdb_id=tvdb_id, imdb_id=None,
        season_number=season, episode_number=ep,
    )


def _movie(title: str, tmdb_id: int, year: int) -> MovieWanted:
    return MovieWanted(radarr_id=0, title=title, year=year,
                       tmdb_id=tmdb_id, imdb_id=None)


def _check_ep(source_name: str, wanted: EpisodeWanted) -> None:
    src = _sources()[source_name]
    hit = src.resolve_episode(wanted)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[{source_name}] S{wanted.season_number:02d}E{wanted.episode_number:02d} "
          f"— {wanted.series_title}", file=sys.stderr)
    for line in getattr(src, "_last_log", []):
        print(f"  {line}", file=sys.stderr)
    if hit:
        print(f"  → HIT: {hit.hls_url}", file=sys.stderr)
    else:
        print(f"  → NOT FOUND", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    assert hit is not None, (
        f"{source_name}: S{wanted.season_number:02d}E{wanted.episode_number:02d} not found. "
        "Check stderr for trace log."
    )


def _check_movie(source_name: str, wanted: MovieWanted) -> None:
    src = _sources()[source_name]
    hit = src.resolve_movie(wanted)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[{source_name}] movie — {wanted.title} ({wanted.year})", file=sys.stderr)
    for line in getattr(src, "_last_log", []):
        print(f"  {line}", file=sys.stderr)
    if hit:
        print(f"  → HIT: {hit.hls_url}", file=sys.stderr)
    else:
        print(f"  → NOT FOUND", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    assert hit is not None, (
        f"{source_name}: movie '{wanted.title}' ({wanted.year}) not found."
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. MOVIES
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveMovies:
    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_inception(self, src):
        _check_movie(src, _movie("Inception", 27205, 2010))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_avengers_endgame(self, src):
        _check_movie(src, _movie("Avengers: Endgame", 299534, 2019))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_interstellar(self, src):
        _check_movie(src, _movie("Interstellar", 157336, 2014))


# ══════════════════════════════════════════════════════════════════════════════
# 2. STANDARD SERIES
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveSeries:
    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_breaking_bad_s1e1(self, src):
        _check_ep(src, _ep("Breaking Bad", 1396, 81189, season=1, ep=1, year=2008))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_squid_game_s1e1(self, src):
        _check_ep(src, _ep("Squid Game", 93405, 364081, season=1, ep=1, year=2021))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_squid_game_s2e1(self, src):
        _check_ep(src, _ep("Squid Game", 93405, 364081, season=2, ep=1, year=2021))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_game_of_thrones_s3e5(self, src):
        _check_ep(src, _ep("Game of Thrones", 1399, 121361, season=3, ep=5, year=2011))


# ══════════════════════════════════════════════════════════════════════════════
# 3. ANIME (absolute episode numbering — One Piece)
# ══════════════════════════════════════════════════════════════════════════════

class TestLiveAnime:
    """
    One Piece on phimapi sites often stores episodes with absolute numbering.
    S1E1 = abs 1, S2E5 = abs 66, etc.
    TVMaze mapping is needed for season > 1.
    tvdb_id=81797 for One Piece.
    """

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_one_piece_s1e1(self, src):
        _check_ep(src, _ep("One Piece", 37854, 81797, season=1, ep=1, year=1999))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_one_piece_s1e10(self, src):
        _check_ep(src, _ep("One Piece", 37854, 81797, season=1, ep=10, year=1999))

    @pytest.mark.live
    @pytest.mark.parametrize("src", ["kkphim", "ophim", "nguonc"])
    def test_naruto_s1e1(self, src):
        _check_ep(src, _ep("Naruto", 46260, 78857, season=1, ep=1, year=2002))
