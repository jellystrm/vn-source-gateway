from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import replace

from .arr import RadarrClient, SonarrClient
from .config import Settings
from .downloader import HlsDownloader
from .models import EpisodeWanted, MovieWanted, SourceHit
from .sources import Source, build_sources
from .state import StateStore

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
        self.sonarr = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        self.sources = build_sources(settings.hls_template_sources, tmdb_api_key=settings.tmdb_api_key)
        self.state = StateStore(settings.state_path)
        self.downloader = HlsDownloader(settings.download_root, settings.ffmpeg_path, settings.ffmpeg_extra_args)

    def run_forever(self) -> None:
        log.info("vn-source-gateway started")
        while True:
            started = time.time()
            try:
                self.reload_settings()
                self.run_once()
            except Exception:
                log.exception("Worker cycle failed")
            elapsed = time.time() - started
            time.sleep(max(1, self.settings.poll_interval_seconds - elapsed))

    def reload_settings(self) -> None:
        next_settings = replace(Settings.load(), run_once=self.settings.run_once)
        if next_settings == self.settings:
            return
        log.info("Reloaded worker config")
        self.settings = next_settings
        self.radarr = RadarrClient(next_settings.radarr_url, next_settings.radarr_api_key)
        self.sonarr = SonarrClient(next_settings.sonarr_url, next_settings.sonarr_api_key)
        self.sources = build_sources(next_settings.hls_template_sources)
        self.state = StateStore(next_settings.state_path)
        self.downloader = HlsDownloader(
            next_settings.download_root,
            next_settings.ffmpeg_path,
            next_settings.ffmpeg_extra_args,
        )

    def run_once(self) -> None:
        if self.settings.movie_enabled and self.radarr.enabled:
            self._process_movies()
        if self.settings.series_enabled and self.sonarr.enabled:
            self._process_episodes()

    def _process_movies(self) -> None:
        movies = self.radarr.missing_movies(self.settings.max_items_per_poll)
        log.info("Radarr missing movies: %d", len(movies))
        for movie in movies:
            path = self.downloader.movie_path(movie)
            self._process_item(
                key=movie.key,
                label=f"movie {movie.title}",
                path=path,
                resolver=lambda source, item=movie: source.resolve_movie(item),
                importer=lambda import_path: self.radarr.import_path(import_path, self.settings.import_mode),
            )

    def _process_episodes(self) -> None:
        episodes = self.sonarr.missing_episodes(self.settings.max_items_per_poll)
        log.info("Sonarr missing episodes: %d", len(episodes))
        for episode in episodes:
            path = self.downloader.episode_path(episode)
            self._process_item(
                key=episode.key,
                label=(
                    f"episode {episode.series_title} "
                    f"S{episode.season_number:02d}E{episode.episode_number:02d}"
                ),
                path=path,
                resolver=lambda source, item=episode: source.resolve_episode(item),
                importer=lambda import_path: self.sonarr.import_path(import_path, self.settings.import_mode),
            )

    def _process_item(
        self,
        key: str,
        label: str,
        path: str,
        resolver: Callable[[Source], SourceHit | None],
        importer: Callable[[str], None],
    ) -> None:
        if os.path.exists(path):
            log.info("Already downloaded, asking import again: %s", path)
            importer(path)
            return
        if self.state.recently_attempted(key, self.settings.retry_after_seconds):
            log.info("Skipping recent attempt: %s", label)
            return

        hit = self._resolve(label, resolver)
        if not hit:
            log.info("No HLS source found for %s", label)
            return

        self.downloader.download(hit, path)
        self.state.mark_attempt(key, path, hit.source_name)
        importer(path)

    def _resolve(self, label: str, resolver: Callable[[Source], SourceHit | None]) -> SourceHit | None:
        for source_name in self.settings.source_order:
            source = self.sources.get(source_name)
            if not source:
                log.warning("Unknown source in SOURCE_ORDER: %s", source_name)
                continue
            try:
                hit = resolver(source)
            except Exception:
                log.exception("%s resolver failed for %s", source_name, label)
                continue
            if hit:
                log.info("Resolved %s with %s", label, source_name)
                return hit
        return None


def main() -> None:
    settings = Settings.load()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    worker = Worker(settings)
    if settings.run_once or "--once" in sys.argv:
        log.info("vn-source-gateway running one cycle")
        worker.run_once()
        return
    if settings.ui_enabled:
        from .web import UiServer

        UiServer(settings.ui_host, settings.ui_port).start_background()
    worker.run_forever()
