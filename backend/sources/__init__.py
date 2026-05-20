from __future__ import annotations

import logging
from typing import Any

from .base import Source
from .nguonc import NguonCSource
from .phimapi import PhimApiSource
from .template import DirectHlsTemplateSource

__all__ = [
    "Source",
    "PhimApiSource",
    "NguonCSource",
    "DirectHlsTemplateSource",
    "build_sources",
    "BUILTIN_SOURCES",
]

log = logging.getLogger(__name__)

# Built-in sources — always available without user configuration.
# User-defined DirectHlsTemplateSource entries can supplement these.
#
# API documentation:
#   kkphim  https://kkphim.vip/tai-lieu-api        (PhimAPI-compatible)
#   ophim   https://ophim17.cc/api-document         (PhimAPI-compatible docs)
#   nguonc  https://phim.nguonc.com/api-document    (custom schema)
BUILTIN_SOURCES: dict[str, str] = {
    "kkphim": "https://phimapi.com",
    "ophim": "https://ophim1.com",
    "nguonc": "https://phim.nguonc.com",
}

# Default source priority order (used when source_order is empty in config)
DEFAULT_SOURCE_ORDER: list[str] = ["kkphim", "ophim", "nguonc"]


def build_sources(template_configs: list[dict[str, Any]], tmdb_api_key: str = "") -> dict[str, Source]:
    """Build the active source registry.

    Built-in source names are reserved. User-defined templates with names such
    as ``kkphim``, ``ophim``, or ``nguonc`` are ignored so stale config cannot
    silently replace the maintained resolver implementations.
    """
    # Start with built-ins
    sources: dict[str, Source] = {
        "kkphim": PhimApiSource("kkphim", BUILTIN_SOURCES["kkphim"], tmdb_api_key=tmdb_api_key),
        "ophim": PhimApiSource("ophim", BUILTIN_SOURCES["ophim"], tmdb_api_key=tmdb_api_key),
        "nguonc": NguonCSource("nguonc", BUILTIN_SOURCES["nguonc"], tmdb_api_key=tmdb_api_key),
    }
    for config in template_configs:
        source = DirectHlsTemplateSource(config)
        if source.name in BUILTIN_SOURCES:
            log.warning("Ignoring custom source %r because it conflicts with a built-in source", source.name)
            continue
        sources[source.name] = source
    return sources
