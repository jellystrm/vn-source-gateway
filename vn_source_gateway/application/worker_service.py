from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import replace

from vn_source_gateway.adapters.media_managers import RadarrClient, SonarrClient
from vn_source_gateway.application.output_service import OutputService
from vn_source_gateway.domain.models import EpisodeWanted, GatewayJob, GatewayRelease, MovieWanted, SourceHit
from vn_source_gateway.infrastructure.config import Settings
from vn_source_gateway.infrastructure.downloader import HlsDownloader
from vn_source_gateway.infrastructure.jobs import JobStore
from vn_source_gateway.infrastructure.state import StateStore
from vn_source_gateway.sources import Source, build_sources

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
        self.sonarr = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        self.sources = build_sources(settings.hls_template_sources, tmdb_api_key=settings.tmdb_api_key)
        self.state = StateStore(settings.state_path)
        self.jobs = JobStore(settings.state_path)
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
        self.sources = build_sources(next_settings.hls_template_sources, tmdb_api_key=next_settings.tmdb_api_key)
        self.state = StateStore(next_settings.state_path)
        self.downloader = HlsDownloader(
            next_settings.download_root,
            next_settings.ffmpeg_path,
            next_settings.ffmpeg_extra_args,
        )

    def run_once(self) -> None:
        if not self.settings.worker_enabled:
            log.debug("Worker polling disabled (worker_enabled=false)")
            return
        if self.settings.movie_enabled and self.radarr.enabled:
            self._process_movies()
        if self.settings.series_enabled and self.sonarr.enabled:
            self._process_episodes()

    def _process_movies(self) -> None:
        movies = self.radarr.missing_movies(self.settings.max_items_per_poll)
        log.info("Radarr missing movies: %d", len(movies))
        output = OutputService(self.settings)
        for movie in movies:
            mode = self.settings.default_output_mode
            job_id = movie.key
            release = GatewayRelease(
                title=movie.title,
                kind="movie",
                output_mode=mode,  # type: ignore[arg-type]
                source_name=None,
                query=movie.title,
                year=movie.year,
                tmdb_id=movie.tmdb_id,
                imdb_id=movie.imdb_id,
            )
            now = int(time.time())
            existing = self.jobs.get(job_id)
            job = GatewayJob(
                job_id=job_id,
                release=release,
                status=existing.status if existing else "queued",
                progress=existing.progress if existing else 0.0,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                category="vn-source",
            )
            self.jobs.upsert(job)
            path = output.strm_path(job) if mode == "strm" else self.downloader.movie_path(movie)
            self._process_item(
                key=job_id,
                label=f"movie {movie.title}",
                path=path,
                job=job,
                output=output,
                resolver=lambda source, item=movie: source.resolve_movie(item),
                importer=lambda import_path: self.radarr.import_path(import_path, self.settings.import_mode),
            )

    def _process_episodes(self) -> None:
        episodes = self.sonarr.missing_episodes(self.settings.max_items_per_poll)
        log.info("Sonarr missing episodes: %d", len(episodes))
        output = OutputService(self.settings)
        for episode in episodes:
            mode = self.settings.default_output_mode
            job_id = episode.key
            release = GatewayRelease(
                title=episode.series_title,
                kind="episode",
                output_mode=mode,  # type: ignore[arg-type]
                source_name=None,
                query=episode.series_title,
                year=episode.year,
                tmdb_id=episode.tmdb_id,
                tvdb_id=episode.tvdb_id,
                imdb_id=episode.imdb_id,
                season_number=episode.season_number,
                episode_number=episode.episode_number,
            )
            now = int(time.time())
            existing = self.jobs.get(job_id)
            job = GatewayJob(
                job_id=job_id,
                release=release,
                status=existing.status if existing else "queued",
                progress=existing.progress if existing else 0.0,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                category="vn-source",
            )
            self.jobs.upsert(job)
            path = output.strm_path(job) if mode == "strm" else self.downloader.episode_path(episode)
            self._process_item(
                key=job_id,
                label=(
                    f"episode {episode.series_title} "
                    f"S{episode.season_number:02d}E{episode.episode_number:02d}"
                ),
                path=path,
                job=job,
                output=output,
                resolver=lambda source, item=episode: source.resolve_episode(item),
                importer=lambda import_path: self.sonarr.import_path(import_path, self.settings.import_mode),
            )

    def _process_item(
        self,
        key: str,
        label: str,
        path: str,
        job: GatewayJob,
        output: OutputService,
        resolver: Callable[[Source], SourceHit | None],
        importer: Callable[[str], None],
    ) -> None:
        if os.path.exists(path):
            log.info("Already exists, re-importing: %s", path)
            self.jobs.update(key, status="completed", progress=1.0, save_path=path, error=None)
            importer(path)
            return
        # File gone (Radarr refresh / manual delete) → clear cooldown so we re-fetch
        self.state.clear_attempt(key)
        if self.state.recently_attempted(key, self.settings.retry_after_seconds):
            log.info("Skipping recent attempt: %s", label)
            self.jobs.update(key, status="queued", error="Skipped: recently attempted")
            return

        self.jobs.update(key, status="running", progress=0.05, error=None)
        try:
            hit = self._resolve(label, resolver)
            if not hit:
                log.info("No HLS source found for %s", label)
                self.jobs.update(key, status="error", progress=0.0, error="No HLS source found")
                return

            self.jobs.update(key, progress=0.35, hls_url=hit.hls_url)
            mode = job.release.output_mode
            if mode == "strm":
                completed = output.write_strm(job, hit)
                out_path = completed.save_path or path
            else:
                output.download_hls(job, hit)
                out_path = path
            self.state.mark_attempt(key, out_path, hit.source_name)
            self.jobs.update(key, status="completed", progress=1.0, save_path=out_path, hls_url=hit.hls_url, error=None)
            importer(out_path)
        except Exception as exc:
            log.error("Processing failed for %s: %s", label, exc)
            self.jobs.update(key, status="error", progress=0.0, error=str(exc))
            # Do NOT re-raise — let the worker continue with remaining items

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


def _resume_interrupted_jobs(settings: Settings) -> None:
    """On startup, restart any grab-service jobs that were interrupted by a container restart.

    Jobs created via the qBittorrent-compatible download client endpoint are
    processed by per-job threads.  When the container restarts those threads
    are gone, leaving jobs stuck in 'queued' or 'running' state.  This
    function re-queues them and spawns fresh threads so they continue.
    """
    import threading
    from vn_source_gateway.application.grab_service import process_job

    store = JobStore(settings.state_path)
    resumed = 0
    for job in store.list_jobs():
        if job.status in {"queued", "running"} and not job.paused:
            # Reset to queued (clears any partial progress) and restart thread
            store.update(job.job_id, status="queued", progress=0.0, error=None)
            threading.Thread(
                target=process_job,
                args=(settings, job.job_id),
                name=f"vn-source-job-{job.job_id[:8]}",
                daemon=True,
            ).start()
            log.info("Resumed interrupted job %s (%s)", job.job_id[:8], job.release.title)
            resumed += 1
    if resumed:
        log.info("Startup: resumed %d interrupted job(s)", resumed)


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
        from vn_source_gateway.web import UiServer

        UiServer(settings.ui_host, settings.ui_port).start_background()
    _resume_interrupted_jobs(settings)
    worker.run_forever()
