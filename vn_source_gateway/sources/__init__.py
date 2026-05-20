from __future__ import annotations

from typing import Any

from .base import Source
from .phimapi import PhimApiSource
from .template import DirectHlsTemplateSource

__all__ = ["Source", "PhimApiSource", "DirectHlsTemplateSource", "build_sources", "BUILTIN_SOURCES"]

# Built-in PhimAPI-compatible sources — always available without user configuration.
# User-defined DirectHlsTemplateSource entries can supplement or override these.
BUILTIN_SOURCES: dict[str, str] = {
    "kkphim": "https://phimapi.com",
    "ophim": "https://ophim17.cc",
    "nguonc": "https://phim.nguonc.com",
}

# Default source priority order (used when source_order is empty in config)
DEFAULT_SOURCE_ORDER: list[str] = ["kkphim", "ophim", "nguonc"]


def build_sources(template_configs: list[dict[str, Any]], tmdb_api_key: str = "") -> dict[str, Source]:
    """Build the active source registry.

    Priority (highest to lowest when the same name appears):
    1. User-defined DirectHlsTemplateSource entries from ``hls_template_sources``
    2. Built-in PhimApiSource entries (kkphim / ophim / nguonc)
    """
    # Start with built-ins
    sources: dict[str, Source] = {
        name: PhimApiSource(name, base_url, tmdb_api_key=tmdb_api_key)
        for name, base_url in BUILTIN_SOURCES.items()
    }
    # User-defined templates override built-ins when the same name is used
    for config in template_configs:
        source = DirectHlsTemplateSource(config)
        sources[source.name] = source
    return sources
