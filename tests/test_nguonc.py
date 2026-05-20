from __future__ import annotations

from unittest.mock import MagicMock, patch

from deceptarr.domain.models import EpisodeWanted, MovieWanted
from deceptarr.sources import build_sources
from deceptarr.sources.nguonc import NguonCSource


def _source() -> NguonCSource:
    return NguonCSource("nguonc", "https://phim.nguonc.com")


def _movie() -> MovieWanted:
    return MovieWanted(radarr_id=1, title="Inception", year=2010, tmdb_id=27205, imdb_id=None)


def _episode(season: int = 1, ep: int = 1) -> EpisodeWanted:
    return EpisodeWanted(
        sonarr_episode_id=1,
        series_id=1,
        series_title="Breaking Bad",
        episode_title="Pilot",
        year=2008,
        tmdb_id=1396,
        tvdb_id=None,
        imdb_id=None,
        season_number=season,
        episode_number=ep,
    )


def _live_action_episode(season: int = 1, ep: int = 1) -> EpisodeWanted:
    return EpisodeWanted(
        sonarr_episode_id=1,
        series_id=1,
        series_title="One Piece",
        episode_title="Romance Dawn",
        year=2023,
        tmdb_id=111110,
        tvdb_id=None,
        imdb_id=None,
        season_number=season,
        episode_number=ep,
    )


def _response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data
    return resp


def _search_response(items: list[dict]) -> MagicMock:
    return _response({"status": "success", "items": items})


def _detail_response(slug: str, *, name: str, original_name: str, episodes: list[dict], total: int = 1) -> MagicMock:
    return _response(
        {
            "status": "success",
            "movie": {
                "name": name,
                "slug": slug,
                "original_name": original_name,
                "total_episodes": total,
                "current_episode": "FULL" if total == 1 else f"Hoan tat ({total}/{total})",
                "category": {
                    "3": {
                        "group": {"name": "Nam"},
                        "list": [{"name": "2010" if total == 1 else "2008"}],
                    }
                },
                "episodes": episodes,
            },
        }
    )


def test_build_sources_uses_dedicated_nguonc_source():
    sources = build_sources([])
    assert isinstance(sources["nguonc"], NguonCSource)


def test_resolves_movie_from_nguonc_schema():
    source = _source()
    search_item = {
        "name": "Ke Danh Cap Giac Mo",
        "original_name": "Inception",
        "slug": "ke-danh-cap-giac-mo",
        "total_episodes": 1,
        "current_episode": "FULL",
    }
    detail = _detail_response(
        "ke-danh-cap-giac-mo",
        name="Ke Danh Cap Giac Mo",
        original_name="Inception",
        episodes=[{"server_name": "Vietsub #1", "items": [{"name": "Full", "m3u8": "https://cdn/inception.m3u8"}]}],
    )
    with patch.object(source.session, "get") as mock_get:
        mock_get.side_effect = [_search_response([search_item]), detail]
        hit = source.resolve_movie(_movie())
    assert hit is not None
    assert hit.hls_url == "https://cdn/inception.m3u8"
    assert any("/api/films/search" in line for line in source._last_log)
    assert any("/api/film/ke-danh-cap-giac-mo" in line for line in source._last_log)


def test_resolves_episode_and_skips_wrong_season(tmdb_single_season):
    source = _source()
    wrong_season = {
        "name": "Tap Lam Nguoi Xau (Phan 4)",
        "original_name": "Breaking Bad (Season 4)",
        "slug": "tap-lam-nguoi-xau-phan-4",
        "total_episodes": 13,
        "current_episode": "Hoan tat (13/13)",
    }
    right_season = {
        "name": "Tap Lam Nguoi Xau (Phan 1)",
        "original_name": "Breaking Bad (Season 1)",
        "slug": "tap-lam-nguoi-xau-phan-1",
        "total_episodes": 7,
        "current_episode": "Hoan tat (7/7)",
    }
    detail = _detail_response(
        "tap-lam-nguoi-xau-phan-1",
        name="Tap Lam Nguoi Xau (Phan 1)",
        original_name="Breaking Bad (Season 1)",
        total=7,
        episodes=[{"server_name": "Vietsub #1", "items": [{"name": "1", "m3u8": "https://cdn/bb-s01e01.m3u8"}]}],
    )
    with patch.object(source.tmdb, "get_series_info", return_value=tmdb_single_season):
        with patch.object(source.session, "get") as mock_get:
            mock_get.side_effect = [_search_response([wrong_season, right_season]), detail]
            hit = source.resolve_episode(_episode())
    assert hit is not None
    assert hit.hls_url == "https://cdn/bb-s01e01.m3u8"
    assert any("score=-5000" in line for line in source._last_log)


def test_uses_live_action_keyword_variant_for_new_tv_series():
    source = _source()
    search_item = {
        "name": "One Piece Live Action (Phan 1)",
        "original_name": "One Piece (Season 1)",
        "slug": "one-piece-live-action-phan-1",
        "total_episodes": 8,
        "current_episode": "Hoan tat (8/8)",
    }
    detail = _detail_response(
        "one-piece-live-action-phan-1",
        name="One Piece Live Action (Phan 1)",
        original_name="One Piece (Season 1)",
        total=8,
        episodes=[{"server_name": "Vietsub #1", "items": [{"name": "1", "m3u8": "https://cdn/op-live-s01e01.m3u8"}]}],
    )
    with patch.object(source.session, "get") as mock_get:
        mock_get.side_effect = [_search_response([]), _search_response([search_item]), detail]
        hit = source.resolve_episode(_live_action_episode())
    assert hit is not None
    assert hit.hls_url == "https://cdn/op-live-s01e01.m3u8"
    assert any("One Piece Live Action" in line for line in source._last_log)
