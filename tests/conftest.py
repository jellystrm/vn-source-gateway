from __future__ import annotations

import os

import pytest

# Ensure config never reads real files/env during tests
os.environ.setdefault("CONFIG_PATH", "/tmp/vn_test_config.yml")


from vn_source_gateway.adapters.tmdb import TmdbSeriesInfo, TmdbSeason


@pytest.fixture
def tmdb_single_season() -> TmdbSeriesInfo:
    """A simple single-season series with 12 episodes, started 2022."""
    return TmdbSeriesInfo(
        series_year=2022,
        season_years={1: 2022},
        seasons=[TmdbSeason(season_number=1, episode_count=12, year=2022)],
        total_episodes=12,
        total_seasons=1,
        title="Test Series",
        alternative_titles=["Test Series"],
    )


@pytest.fixture
def tmdb_multi_season() -> TmdbSeriesInfo:
    """A two-season series: S1 (2020, 10 eps) and S2 (2022, 8 eps)."""
    return TmdbSeriesInfo(
        series_year=2020,
        season_years={1: 2020, 2: 2022},
        seasons=[
            TmdbSeason(season_number=1, episode_count=10, year=2020),
            TmdbSeason(season_number=2, episode_count=8, year=2022),
        ],
        total_episodes=18,
        total_seasons=2,
        title="Long Series",
        alternative_titles=["Long Series"],
    )


def make_item(
    name: str = "Test Movie",
    origin_name: str = "Test Movie",
    kind: str = "single",
    year: int = 2022,
    tmdb_id: str | None = None,
    episode_current: str = "Full",
    episode_total: int = 1,
    slug: str = "test-movie",
) -> dict:
    return {
        "name": name,
        "origin_name": origin_name,
        "type": kind,
        "year": year,
        "tmdb": {"id": tmdb_id} if tmdb_id else {},
        "episode_current": episode_current,
        "episode_total": episode_total,
        "slug": slug,
    }
