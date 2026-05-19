"""Tests for PhimApiSource — mocked HTTP responses."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from vn_source_gateway.domain.models import EpisodeWanted, MovieWanted
from vn_source_gateway.sources.phimapi import PhimApiSource
from vn_source_gateway.adapters.tmdb import TmdbSeriesInfo, TmdbSeason


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _source(tmdb_api_key: str = "") -> PhimApiSource:
    return PhimApiSource("kkphim", "https://phimapi.com", tmdb_api_key=tmdb_api_key)


def _movie(title="Avengers", year=2012, tmdb_id=24428) -> MovieWanted:
    return MovieWanted(radarr_id=1, title=title, year=year, tmdb_id=tmdb_id, imdb_id=None)


def _episode(title="Breaking Bad", year=2008, tmdb_id=1396, season=1, ep=1, tvdb_id=81189) -> EpisodeWanted:
    return EpisodeWanted(
        sonarr_episode_id=1, series_id=1,
        series_title=title, episode_title="Pilot",
        year=year, tmdb_id=tmdb_id, tvdb_id=tvdb_id, imdb_id=None,
        season_number=season, episode_number=ep,
    )


def _search_response(items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": {"items": items}}
    resp.raise_for_status = MagicMock()
    return resp


def _detail_response(slug: str, episodes: list[dict], tmdb_id: str = "24428",
                     name: str = "Avengers", year: int = 2012) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "status": True,
        "movie": {"slug": slug, "name": name, "origin_name": name,
                  "year": year, "type": "single", "tmdb": {"id": tmdb_id}},
        "episodes": episodes,
    }
    resp.raise_for_status = MagicMock()
    return resp


def _tmdb_direct_response(slug: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": True, "movie": {"slug": slug}}
    resp.raise_for_status = MagicMock()
    return resp


def _hls_episodes(urls: list[str]) -> list[dict]:
    return [{"server_data": [
        {"name": str(i + 1), "link_m3u8": url}
        for i, url in enumerate(urls)
    ]}]


def _error_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("HTTP 500")
    return resp


# ── Movie resolution ──────────────────────────────────────────────────────────

class TestSearchRobustness:
    """Regression: API returning {"data":{"items":null}} must not crash."""

    def _null_items_resp(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": {"items": None}}
        return resp

    def _null_data_resp(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"data": None}
        return resp

    def test_search_returns_list_when_items_null(self):
        source = _source()
        with patch.object(source.session, "get", return_value=self._null_items_resp()):
            assert source._search("anything") == []

    def test_search_returns_list_when_data_null(self):
        source = _source()
        with patch.object(source.session, "get", return_value=self._null_data_resp()):
            assert source._search("anything") == []

    def test_resolve_movie_falls_through_to_tmdb_when_search_null(self):
        """The original crash: null items broke the for-loop before tmdb fallback."""
        source = _source()
        tmdb_resp = _tmdb_direct_response("avengers-direct")
        detail = _detail_response("avengers-direct",
                                  _hls_episodes(["https://cdn/x.m3u8"]))
        with patch.object(source.session, "get") as mock_get:
            mock_get.side_effect = [self._null_items_resp(), tmdb_resp, detail]
            hit = source.resolve_movie(_movie())
        assert hit is not None
        assert hit.hls_url == "https://cdn/x.m3u8"

    def test_detail_handles_non_dict_json(self):
        source = _source()
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = None
        with patch.object(source.session, "get", return_value=resp):
            assert source._detail("slug") is None


class TestResolveMovie:
    def test_resolves_via_search(self):
        source = _source()
        search_item = {
            "name": "Avengers", "origin_name": "Avengers",
            "type": "single", "year": 2012,
            "tmdb": {"id": "24428"}, "slug": "avengers-2012",
            "episode_current": "Full", "episode_total": 1,
        }
        detail = _detail_response(
            "avengers-2012",
            _hls_episodes(["https://cdn.example.com/avengers.m3u8"]),
        )
        with patch.object(source.session, "get") as mock_get:
            mock_get.side_effect = [_search_response([search_item]), detail]
            hit = source.resolve_movie(_movie())
        assert hit is not None
        assert hit.hls_url == "https://cdn.example.com/avengers.m3u8"
        assert hit.source_name == "kkphim"

    def test_falls_back_to_tmdb_direct(self):
        source = _source()
        tmdb_resp = _tmdb_direct_response("avengers-direct")
        detail = _detail_response(
            "avengers-direct",
            _hls_episodes(["https://cdn.example.com/avengers-direct.m3u8"]),
        )
        with patch.object(source.session, "get") as mock_get:
            # search returns empty, then tmdb direct
            mock_get.side_effect = [_search_response([]), tmdb_resp, detail]
            hit = source.resolve_movie(_movie())
        assert hit is not None
        assert "avengers-direct" in hit.hls_url

    def test_returns_none_when_no_results(self):
        source = _source()
        with patch.object(source.session, "get") as mock_get:
            mock_get.side_effect = [_search_response([]), _error_response()]
            hit = source.resolve_movie(_movie(tmdb_id=None))
        assert hit is None

    def test_handles_search_network_error_gracefully(self):
        source = _source()
        with patch.object(source.session, "get", side_effect=Exception("timeout")):
            hit = source.resolve_movie(_movie(tmdb_id=None))
        assert hit is None

    def test_score_below_threshold_skipped(self):
        source = _source()
        # A sequel should be scored below threshold and skipped
        bad_item = {
            "name": "Avengers 2", "origin_name": "Avengers Age of Ultron",
            "type": "single", "year": 2015,
            "tmdb": {}, "slug": "avengers-2-2015",
            "episode_current": "Full", "episode_total": 1,
        }
        with patch.object(source.session, "get") as mock_get:
            mock_get.side_effect = [_search_response([bad_item]), _error_response()]
            hit = source.resolve_movie(_movie(year=2012, tmdb_id=None))
        assert hit is None


# ── Episode resolution ────────────────────────────────────────────────────────

class TestResolveEpisode:
    def _tv_search_item(self, tmdb_id="1396", season_suffix="", year=2008):
        return {
            "name": f"Breaking Bad{season_suffix}",
            "origin_name": f"Breaking Bad{season_suffix}",
            "type": "series", "year": year,
            "tmdb": {"id": tmdb_id}, "slug": f"breaking-bad{season_suffix.lower().replace(' ', '-')}",
            "episode_current": "7", "episode_total": 7,
        }

    def test_resolves_episode_via_search(self, tmdb_single_season):
        source = _source()
        ep_url = "https://cdn.example.com/s01e01.m3u8"
        search_item = self._tv_search_item()
        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {
            "status": True,
            "movie": {"slug": "breaking-bad", "name": "Breaking Bad",
                      "origin_name": "Breaking Bad", "year": 2008, "type": "series",
                      "tmdb": {"id": "1396"}},
            "episodes": [{"server_data": [
                {"name": "1", "link_m3u8": ep_url},
                {"name": "2", "link_m3u8": "https://cdn.example.com/s01e02.m3u8"},
            ]}],
        }
        with patch.object(source.session, "get") as mock_get:
            with patch.object(source.tmdb, "get_series_info", return_value=tmdb_single_season):
                mock_get.side_effect = [_search_response([search_item]), detail_resp]
                hit = source.resolve_episode(_episode())
        assert hit is not None
        assert hit.hls_url == ep_url

    def test_tmdb_direct_fallback_for_episode(self, tmdb_single_season):
        source = _source()
        ep_url = "https://cdn.example.com/direct-s01e01.m3u8"
        tmdb_resp = _tmdb_direct_response("breaking-bad")
        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {
            "status": True,
            "movie": {"slug": "breaking-bad", "name": "Breaking Bad",
                      "origin_name": "Breaking Bad", "year": 2008, "type": "series",
                      "tmdb": {"id": "1396"}},
            "episodes": [{"server_data": [
                {"name": "1", "link_m3u8": ep_url},
            ]}],
        }
        with patch.object(source.session, "get") as mock_get:
            with patch.object(source.tmdb, "get_series_info", return_value=tmdb_single_season):
                # search empty → tmdb direct → detail
                mock_get.side_effect = [_search_response([]), tmdb_resp, detail_resp, detail_resp]
                hit = source.resolve_episode(_episode())
        assert hit is not None
        assert hit.hls_url == ep_url

    def test_wrong_episode_number_not_returned(self, tmdb_single_season):
        source = _source()
        search_item = self._tv_search_item()
        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {
            "status": True,
            "movie": {"slug": "breaking-bad", "name": "Breaking Bad",
                      "origin_name": "Breaking Bad", "year": 2008, "type": "series",
                      "tmdb": {"id": "1396"}},
            "episodes": [{"server_data": [
                {"name": "2", "link_m3u8": "https://cdn.example.com/s01e02.m3u8"},
            ]}],
        }
        with patch.object(source.session, "get") as mock_get:
            with patch.object(source.tmdb, "get_series_info", return_value=tmdb_single_season):
                # Only ep 2 available, we want ep 1
                mock_get.side_effect = [_search_response([search_item]), detail_resp, _error_response()]
                hit = source.resolve_episode(_episode(ep=1))
        assert hit is None

    def test_too_many_episodes_slug_skipped(self):
        """Slug with far more episodes than TMDB says → skip."""
        source = _source()
        tmdb_info = TmdbSeriesInfo(
            series_year=2008,
            season_years={1: 2008},
            seasons=[TmdbSeason(season_number=1, episode_count=7, year=2008)],
            total_episodes=7, total_seasons=1,
        )
        search_item = self._tv_search_item()
        # Detail has 20 episodes — way more than TMDB's 7
        too_many = [{"server_data": [
            {"name": str(i), "link_m3u8": f"https://cdn/ep{i}.m3u8"} for i in range(1, 21)
        ]}]
        detail_resp = MagicMock()
        detail_resp.status_code = 200
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {
            "status": True,
            "movie": {"slug": "breaking-bad", "name": "Breaking Bad",
                      "origin_name": "Breaking Bad", "year": 2008,
                      "type": "series", "tmdb": {"id": "1396"}},
            "episodes": too_many,
        }
        # Create source with a non-empty api_key so tmdb.enabled=True
        source_with_tmdb = PhimApiSource("kkphim", "https://phimapi.com", tmdb_api_key="fake-key")
        with patch.object(source_with_tmdb.session, "get") as mock_get:
            with patch.object(source_with_tmdb.tmdb, "get_series_info", return_value=tmdb_info):
                mock_get.side_effect = [_search_response([search_item]), detail_resp, _error_response()]
                hit = source_with_tmdb.resolve_episode(_episode())
        assert hit is None
