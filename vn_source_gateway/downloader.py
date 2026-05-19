from __future__ import annotations

import logging
import os
import subprocess

from .models import EpisodeWanted, MovieWanted, SourceHit
from .util import safe_filename

log = logging.getLogger(__name__)


class HlsDownloader:
    def __init__(
        self,
        download_root: str,
        ffmpeg_path: str,
        ffmpeg_extra_args: list[str],
        container: str = "mkv",
    ) -> None:
        self.download_root = download_root
        self.ffmpeg_path = ffmpeg_path
        self.ffmpeg_extra_args = ffmpeg_extra_args
        self.container = container.lstrip(".") or "mkv"

    def movie_path(self, movie: MovieWanted) -> str:
        year = f" ({movie.year})" if movie.year else ""
        folder = safe_filename(f"{movie.title}{year}")
        stem = safe_filename(f"{movie.title}{year} [tmdb-{movie.tmdb_id or movie.radarr_id}]")
        return os.path.join(self.download_root, "radarr", folder, f"{stem}.{self.container}")

    def episode_path(self, episode: EpisodeWanted) -> str:
        series = safe_filename(episode.series_title)
        season = f"Season {episode.season_number:02d}"
        stem = safe_filename(
            f"{episode.series_title} - S{episode.season_number:02d}E{episode.episode_number:02d}"
            + (f" - {episode.episode_title}" if episode.episode_title else "")
        )
        return os.path.join(self.download_root, "sonarr", series, season, f"{stem}.{self.container}")

    def download(self, hit: SourceHit, output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tmp_path = f"{output_path}.part"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
        ]
        if hit.headers:
            command.extend(["-headers", _ffmpeg_headers(hit.headers)])
        command.extend(
            [
                "-i",
                hit.hls_url,
                *self.ffmpeg_extra_args,
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                tmp_path,
            ]
        )

        log.info("Downloading via %s to %s", hit.source_name, output_path)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise RuntimeError(f"ffmpeg failed with exit code {completed.returncode}")
        os.replace(tmp_path, output_path)


def _ffmpeg_headers(headers: dict[str, str]) -> str:
    return "".join(f"{key}: {value}\r\n" for key, value in headers.items())
