from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import replace

from backend.adapters.media_managers import RadarrClient, SonarrClient
from backend.adapters.tmdb import TmdbClient
from backend.application.grab_service import _enrich_with_tmdb
from backend.application.output_service import OutputService
from backend.domain.models import EpisodeWanted, GatewayJob, GatewayRelease, MovieWanted, SourceHit
from backend.infrastructure.config import Settings
from backend.infrastructure.downloader import HlsDownloader
from backend.infrastructure.jobs import JobStore
from backend.infrastructure.state import StateStore
from backend.sources import Source, build_sources

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.radarr = RadarrClient(settings.radarr_url, settings.radarr_api_key)
        self.sonarr = SonarrClient(settings.sonarr_url, settings.sonarr_api_key)
        self.sources = build_sources(tmdb_api_key=settings.tmdb_api_key)
        self.state = StateStore(settings.state_path)
        self.jobs = JobStore(settings.state_path)
        self.downloader = HlsDownloader(settings.download_root, settings.ffmpeg_path, settings.ffmpeg_extra_args)
        self._movie_last_run: float = 0.0
        self._series_last_run: float = 0.0

    def _tick_interval(self) -> int:
        """Sleep interval for the main loop — short enough to honour both schedules."""
        return max(10, min(
            self.settings.movie_poll_interval_seconds,
            self.settings.series_poll_interval_seconds,
        ) // 10)

    def run_forever(self) -> None:
        log.info("deceptarr started")
        while True:
            started = time.time()
            try:
                self.reload_settings()
                self.run_once()
            except Exception:
                log.exception("Worker cycle failed")
            elapsed = time.time() - started
            time.sleep(max(1, self._tick_interval() - elapsed))

    def reload_settings(self) -> None:
        next_settings = replace(Settings.load(), run_once=self.settings.run_once)
        if next_settings == self.settings:
            return
        log.info("Reloaded worker config")
        self.settings = next_settings
        self.radarr = RadarrClient(next_settings.radarr_url, next_settings.radarr_api_key)
        self.sonarr = SonarrClient(next_settings.sonarr_url, next_settings.sonarr_api_key)
        self.sources = build_sources(tmdb_api_key=next_settings.tmdb_api_key)
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
        now = time.time()
        force = self.settings.run_once  # one-shot mode: skip timing checks
        if self.settings.movie_enabled and self.radarr.enabled:
            if force or now - self._movie_last_run >= self.settings.movie_poll_interval_seconds:
                self._process_movies()
                self._movie_last_run = now
        if self.settings.series_enabled and self.sonarr.enabled:
            if force or now - self._series_last_run >= self.settings.series_poll_interval_seconds:
                self._process_episodes()
                self._series_last_run = now
        self._prune_stale_jobs()

    def _process_movies(self) -> None:
        movies = self.radarr.missing_movies(self.settings.movie_max_items_per_poll)
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
            release = _enrich_with_tmdb(self.settings, release)
            wanted = replace(movie, title=release.query or release.title, year=release.year, tmdb_id=release.tmdb_id)
            now = int(time.time())
            existing = self.jobs.get(job_id)
            job = GatewayJob(
                job_id=job_id,
                release=release,
                status=existing.status if existing else "queued",
                progress=existing.progress if existing else 0.0,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                category="deceptarr",
            )
            self.jobs.upsert(job)
            path = output.strm_path(job) if mode == "strm" else self.downloader.movie_path(wanted)
            self._process_item(
                key=job_id,
                label=f"movie {release.title}",
                path=path,
                job=job,
                output=output,
                resolver=lambda source, item=wanted: source.resolve_movie(item),
                importer=lambda import_path: self.radarr.import_path(import_path, self.settings.import_mode),
            )

    def _process_episodes(self) -> None:
        episodes = self.sonarr.missing_episodes(self.settings.series_max_items_per_poll)
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
            release = _enrich_with_tmdb(self.settings, release)

            # Remap TVDB season/episode → TMDB numbering.
            # Sonarr uses TVDB numbering; Vietnamese sources use TMDB.
            # TMDB /find/{tvdb_episode_id} returns the canonical TMDB numbers.
            tmdb_season, tmdb_episode = _remap_tvdb_to_tmdb(
                self.settings, episode, release.season_number, release.episode_number
            )
            if (tmdb_season, tmdb_episode) != (release.season_number, release.episode_number):
                release = replace(release, season_number=tmdb_season, episode_number=tmdb_episode)

            wanted = replace(
                episode,
                series_title=release.query or release.title,
                year=release.year,
                tmdb_id=release.tmdb_id,
                season_number=tmdb_season,
                episode_number=tmdb_episode,
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
                category="deceptarr",
            )
            self.jobs.upsert(job)
            path = output.strm_path(job) if mode == "strm" else self.downloader.episode_path(wanted)
            # For STRM mode, bypass filename-based DownloadedEpisodesScan (which
            # fails when TMDB-numbered files don't match Sonarr's TVDB numbering).
            # Use ManualImport with explicit episode ID so Sonarr marks the episode
            # as "downloaded" (green). Falls back to unmonitored if ManualImport fails.
            if mode == "strm" and episode.sonarr_episode_id:
                ep_importer = lambda _path, _sid=episode.series_id, _eid=episode.sonarr_episode_id: \
                    self.sonarr.import_episode_by_id(_path, _sid, _eid)
            else:
                ep_importer = lambda import_path: self.sonarr.import_path(
                    import_path, self.settings.import_mode
                )
            self._process_item(
                key=job_id,
                label=(
                    f"episode {release.title} "
                    f"S{episode.season_number:02d}E{episode.episode_number:02d}"
                ),
                path=path,
                job=job,
                output=output,
                resolver=lambda source, item=wanted: source.resolve_episode(item),
                importer=ep_importer,
            )

    def _prune_stale_jobs(self) -> None:
        """Mark queued/error worker jobs as deleted when they are no longer wanted.

        Handles the case where Radarr, Sonarr, or Jellyseerr removes a request
        after Deceptarr already queued a job for it.  Without pruning, those
        orphaned jobs pile up indefinitely.

        Safety rules:
        - Only prune *worker-created* jobs (job_id starts with movie: or episode:).
          Torznab / manual-grab jobs use SHA1 hashes and are left untouched.
        - Only prune jobs in ``queued`` or ``error`` state.
          Running jobs are left alone; completed jobs are kept for history.
        - If either arr cannot be reached, skip pruning that kind to avoid
          accidentally deleting jobs due to a transient network error.
        """
        _BIG = 2000  # large enough for any realistic library
        wanted_keys: set[str] = set()
        queried_movie = False
        queried_episode = False

        if self.settings.movie_enabled and self.radarr.enabled:
            try:
                for m in self.radarr.missing_movies(_BIG):
                    wanted_keys.add(m.key)
                queried_movie = True
            except Exception:
                log.debug("Radarr unavailable — skipping movie stale-job pruning")

        if self.settings.series_enabled and self.sonarr.enabled:
            try:
                for e in self.sonarr.missing_episodes(_BIG):
                    wanted_keys.add(e.key)
                queried_episode = True
            except Exception:
                log.debug("Sonarr unavailable — skipping episode stale-job pruning")

        if not queried_movie and not queried_episode:
            return

        pruned = 0
        for job in self.jobs.list_jobs():
            if job.status not in {"queued", "error"} or job.paused:
                continue
            is_movie_job = job.job_id.startswith("movie:")
            is_episode_job = job.job_id.startswith("episode:")
            if not is_movie_job and not is_episode_job:
                continue  # torznab / manual-grab job — leave untouched
            if is_movie_job and not queried_movie:
                continue  # Radarr unreachable — don't prune
            if is_episode_job and not queried_episode:
                continue  # Sonarr unreachable — don't prune
            if job.job_id not in wanted_keys:
                self.jobs.update(job.job_id, status="deleted")
                log.info("Pruned stale job (no longer wanted): %s  title=%s", job.job_id, job.release.title)
                pruned += 1

        if pruned:
            log.info("Pruned %d stale job(s) no longer in wanted lists", pruned)

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


def _remap_tvdb_to_tmdb(
    settings: Settings,
    episode: EpisodeWanted,
    current_season: int | None,
    current_episode: int | None,
) -> tuple[int, int]:
    """Remap TVDB season/episode numbers to TMDB numbering via TMDB /find API.

    Sonarr uses TVDB ordering; Vietnamese sources use TMDB ordering.
    When a TVDB episode-level ID is available and TMDB is configured, this
    calls TMDB /find/{tvdb_episode_id}?external_source=tvdb_id to get the
    canonical TMDB season/episode numbers.

    Returns the original (season, episode) unchanged if:
    - No TVDB episode ID is available from Sonarr
    - TMDB API key is not configured
    - TMDB has no match for the TVDB episode ID
    - The numbers already match (no-op remap)
    """
    original_season = current_season or episode.season_number
    original_episode = current_episode or episode.episode_number

    if not episode.tvdb_episode_id or not settings.tmdb_api_key:
        return original_season, original_episode

    mapped = TmdbClient(settings.tmdb_api_key).tvdb_episode_to_tmdb(episode.tvdb_episode_id)
    if mapped is None:
        return original_season, original_episode

    new_season, new_episode = mapped
    if (new_season, new_episode) != (original_season, original_episode):
        log.info(
            "TVDB→TMDB remap %r S%02dE%02d → S%02dE%02d (tvdb_ep=%s)",
            episode.series_title,
            original_season, original_episode,
            new_season, new_episode,
            episode.tvdb_episode_id,
        )
    return new_season, new_episode


def _resume_interrupted_jobs(settings: Settings) -> None:
    """On startup, restart any grab-service jobs that were interrupted by a container restart.

    Jobs created via the qBittorrent-compatible download client endpoint are
    processed by per-job threads.  When the container restarts those threads
    are gone, leaving jobs stuck in 'queued' or 'running' state.  This
    function re-queues them and spawns fresh threads so they continue.
    """
    import threading
    from backend.application.grab_service import process_job

    store = JobStore(settings.state_path)
    resumed = 0
    for job in store.list_jobs():
        if job.status in {"queued", "running"} and not job.paused:
            # Reset to queued (clears any partial progress) and restart thread
            store.update(job.job_id, status="queued", progress=0.0, error=None)
            threading.Thread(
                target=process_job,
                args=(settings, job.job_id),
                name=f"deceptarr-job-{job.job_id[:8]}",
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
    # Persist activity log next to state.json
    from backend.infrastructure.activity import ActivityLog
    activity_path = settings.state_path.replace("state.json", "activity.json")
    if activity_path == settings.state_path:          # fallback if path has no state.json
        activity_path = settings.state_path + ".activity.json"
    ActivityLog.init(activity_path)
    log.info("Activity log: %s", activity_path)

    worker = Worker(settings)
    if settings.run_once or "--once" in sys.argv:
        log.info("deceptarr running one cycle")
        worker.run_once()
        return
    if settings.ui_enabled:
        import threading
        import uvicorn
        from backend.api import create_app

        _ui_app = create_app()
        _ui_config = uvicorn.Config(
            _ui_app,
            host=settings.ui_host,
            port=settings.ui_port,
            log_level="warning",
            loop="asyncio",
        )
        _ui_server = uvicorn.Server(_ui_config)
        threading.Thread(target=_ui_server.run, name="deceptarr-ui", daemon=True).start()
        log.info("UI listening on http://%s:%s (FastAPI/uvicorn)", settings.ui_host, settings.ui_port)
    _resume_interrupted_jobs(settings)
    worker.run_forever()
