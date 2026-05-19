from __future__ import annotations

import logging
import os
from dataclasses import replace

import requests

from .config import Settings
from .downloader import HlsDownloader
from .models import EpisodeWanted, GatewayJob, MovieWanted, SourceHit
from .util import safe_filename

log = logging.getLogger(__name__)


class OutputService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.downloader = HlsDownloader(
            settings.download_root,
            settings.ffmpeg_path,
            settings.ffmpeg_extra_args,
            settings.download_container,
        )

    def write_strm(self, job: GatewayJob, hit: SourceHit) -> GatewayJob:
        path = self.strm_path(job)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(hit.hls_url.strip() + "\n")
        if self.settings.jellyfin_scan_after_strm:
            self.scan_jellyfin()
        return replace(job, status="completed", progress=1.0, save_path=path, hls_url=hit.hls_url)

    def download_hls(self, job: GatewayJob, hit: SourceHit) -> GatewayJob:
        movie = self._movie_wanted(job)
        if movie:
            path = self.downloader.movie_path(movie)
        else:
            episode = self._episode_wanted(job)
            path = self.downloader.episode_path(episode)
        self.downloader.download(hit, path)
        return replace(job, status="completed", progress=1.0, save_path=path, hls_url=hit.hls_url)

    def strm_path(self, job: GatewayJob) -> str:
        release = job.release
        if release.kind == "movie":
            year = f" ({release.year})" if release.year else ""
            folder = safe_filename(f"{release.title}{year}")
            stem = safe_filename(f"{release.title}{year}")
            return os.path.join(self.settings.movie_strm_root, folder, f"{stem}.strm")

        series = safe_filename(release.title)
        season = release.season_number or 1
        episode = release.episode_number or 1
        stem = safe_filename(f"{release.title} - S{season:02d}E{episode:02d}")
        return os.path.join(self.settings.series_strm_root, series, f"Season {season:02d}", f"{stem}.strm")

    def scan_jellyfin(self) -> None:
        if not self.settings.jellyfin_url or not self.settings.jellyfin_api_key:
            return
        try:
            response = requests.post(
                f"{self.settings.jellyfin_url}/Library/Refresh",
                headers={"X-Emby-Token": self.settings.jellyfin_api_key},
                timeout=10,
            )
            response.raise_for_status()
        except Exception as exc:
            log.warning("Jellyfin scan failed: %s", exc)

    def _movie_wanted(self, job: GatewayJob) -> MovieWanted | None:
        release = job.release
        if release.kind != "movie":
            return None
        return MovieWanted(
            radarr_id=0,
            title=release.title,
            year=release.year,
            tmdb_id=release.tmdb_id,
            imdb_id=release.imdb_id,
        )

    def _episode_wanted(self, job: GatewayJob) -> EpisodeWanted:
        release = job.release
        return EpisodeWanted(
            sonarr_episode_id=0,
            series_id=0,
            series_title=release.title,
            episode_title="",
            year=release.year,
            tvdb_id=release.tvdb_id,
            imdb_id=release.imdb_id,
            season_number=release.season_number or 1,
            episode_number=release.episode_number or 1,
        )
