"""Tests for sources/scoring.py — score_item, detect_season, season_for_abs_ep."""
from __future__ import annotations

import pytest
from vn_source_gateway.sources.scoring import detect_season, score_item, season_for_abs_ep
from vn_source_gateway.adapters.tmdb import TmdbSeriesInfo, TmdbSeason

from .conftest import make_item


# ── Helpers ───────────────────────────────────────────────────────────────────

def empty_tmdb(year: int = 0) -> TmdbSeriesInfo:
    return TmdbSeriesInfo(series_year=year)


# ── score_item ────────────────────────────────────────────────────────────────

class TestScoreItemMovies:
    def test_tmdb_id_match_gives_high_score(self):
        item = make_item(tmdb_id="12345", year=2022)
        score = score_item(item, "Test Movie", 12345, 2022, "movie", None, empty_tmdb(2022))
        assert score >= 3000

    def test_wrong_tmdb_id_is_rejected(self):
        item = make_item(tmdb_id="99999", year=2022)
        score = score_item(item, "Test Movie", 12345, 2022, "movie", None, empty_tmdb(2022))
        assert score <= -5000

    def test_type_mismatch_tv_rejects_movie_query(self):
        item = make_item(kind="series", year=2022, episode_total=12)
        score = score_item(item, "Test Movie", None, 2022, "movie", None, empty_tmdb(2022))
        assert score < 0

    def test_type_mismatch_movie_rejects_tv_query(self):
        item = make_item(kind="single", year=2022, episode_total=1)
        score = score_item(item, "Test Series", None, 2022, "tv", 1, empty_tmdb(2022))
        assert score < 0

    def test_year_mismatch_rejects_movie(self):
        item = make_item(year=2019)
        score = score_item(item, "Test Movie", None, 2022, "movie", None, empty_tmdb(2022))
        assert score < 0

    def test_exact_title_match_adds_bonus(self):
        item = make_item(name="avengers", origin_name="avengers", year=2012)
        score = score_item(item, "avengers", None, 2012, "movie", None, empty_tmdb(2012))
        assert score > 1000

    def test_empty_item_returns_negative(self):
        assert score_item({}, "Test", None, 2022, "movie", None, empty_tmdb()) < 0

    def test_identity_leakage_rejects_sequel(self):
        # "Avengers 2" result for "Avengers" query — should leak
        item = make_item(name="Avengers 2", origin_name="Avengers 2", kind="single", year=2015)
        score = score_item(item, "Avengers", None, 2015, "movie", None, empty_tmdb(2015))
        assert score < 0


class TestScoreItemTv:
    def test_tv_tmdb_id_match(self, tmdb_single_season):
        item = make_item(name="Test Series", origin_name="Test Series",
                         kind="series", year=2022, tmdb_id="555",
                         episode_current="12", episode_total=12)
        score = score_item(item, "Test Series", 555, 2022, "tv", 1, tmdb_single_season)
        assert score >= 3000

    def test_season_mismatch_rejects(self, tmdb_multi_season):
        # Item is season 1 (2020) but we want season 2 (2022)
        item = make_item(name="Long Series Phần 1", origin_name="Long Series Season 1",
                         kind="series", year=2020, tmdb_id="777",
                         episode_current="10", episode_total=10)
        score = score_item(item, "Long Series", 777, 2022, "tv", 2, tmdb_multi_season)
        # Season detected as 1, requested is 2 → reject
        assert score <= -5000

    def test_too_many_episodes_rejects(self, tmdb_single_season):
        # 20 episodes when TMDB says 12 → 20 > 12*1.3=15.6
        item = make_item(kind="series", year=2022, episode_total=20, episode_current="20")
        score = score_item(item, "Test Series", None, 2022, "tv", 1, tmdb_single_season)
        assert score < 0


# ── detect_season ─────────────────────────────────────────────────────────────

class TestDetectSeason:
    def test_phan_keyword(self, tmdb_multi_season):
        assert detect_season("Tên Phim Phần 2", "Series S2", 2022, tmdb_multi_season) == 2

    def test_season_keyword(self, tmdb_multi_season):
        assert detect_season("Series Season 3", "", 2022, tmdb_multi_season) == 3

    def test_ss_keyword(self, tmdb_multi_season):
        assert detect_season("Series SS2", "", 2022, tmdb_multi_season) == 2

    def test_trailing_number(self, tmdb_multi_season):
        # "Series 2" → trailing 2
        assert detect_season("Series 2", "", 2022, tmdb_multi_season) == 2

    def test_year_match_to_season(self, tmdb_multi_season):
        # year 2022 → season 2 (season_years={1:2020, 2:2022})
        result = detect_season("Long Series", "Long Series", 2022, tmdb_multi_season)
        assert result == 2

    def test_year_match_approximate(self, tmdb_multi_season):
        # year 2021 is within 1 of 2020 → season 1
        result = detect_season("Long Series", "Long Series", 2021, tmdb_multi_season)
        assert result == 1

    def test_no_season_info_returns_none(self):
        tmdb = TmdbSeriesInfo(series_year=2022)
        result = detect_season("Some Movie", "Some Movie", 0, tmdb)
        assert result is None

    def test_slug_contains_season(self, tmdb_multi_season):
        assert detect_season("Series", "Series", 2022, tmdb_multi_season, "series-season-2") == 2


# ── season_for_abs_ep ─────────────────────────────────────────────────────────

class TestSeasonForAbsEp:
    def test_first_season(self, tmdb_multi_season):
        # eps 1-10 → season 1
        assert season_for_abs_ep(1, tmdb_multi_season) == 1
        assert season_for_abs_ep(10, tmdb_multi_season) == 1

    def test_second_season(self, tmdb_multi_season):
        # eps 11-18 → season 2
        assert season_for_abs_ep(11, tmdb_multi_season) == 2
        assert season_for_abs_ep(18, tmdb_multi_season) == 2

    def test_beyond_total_returns_none(self, tmdb_multi_season):
        assert season_for_abs_ep(99, tmdb_multi_season) is None

    def test_single_season(self, tmdb_single_season):
        assert season_for_abs_ep(1, tmdb_single_season) == 1
        assert season_for_abs_ep(12, tmdb_single_season) == 1
        assert season_for_abs_ep(13, tmdb_single_season) is None

    def test_empty_seasons(self):
        tmdb = TmdbSeriesInfo()
        assert season_for_abs_ep(5, tmdb) is None
