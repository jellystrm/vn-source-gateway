from __future__ import annotations

from typing import Any

from .base import Source
from .phimapi import PhimApiSource
from .template import DirectHlsTemplateSource

__all__ = ["Source", "PhimApiSource", "DirectHlsTemplateSource", "build_sources"]


def build_sources(template_configs: list[dict[str, Any]], tmdb_api_key: str = "") -> dict[str, Source]:
    sources: dict[str, Source] = {
        "kkphim": PhimApiSource("kkphim", "https://phimapi.com", tmdb_api_key=tmdb_api_key),
        "ophim": PhimApiSource("ophim", "https://ophim1.com", tmdb_api_key=tmdb_api_key),
    }
    for config in template_configs:
        source = DirectHlsTemplateSource(config)
        sources[source.name] = source
    return sources
