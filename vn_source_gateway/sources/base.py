from __future__ import annotations

from abc import ABC, abstractmethod

from vn_source_gateway.domain.models import EpisodeWanted, MovieWanted, SourceHit


class Source(ABC):
    name: str

    @abstractmethod
    def resolve_movie(self, movie: MovieWanted) -> SourceHit | None:
        raise NotImplementedError

    @abstractmethod
    def resolve_episode(self, episode: EpisodeWanted) -> SourceHit | None:
        raise NotImplementedError
