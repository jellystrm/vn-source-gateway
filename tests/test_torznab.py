"""Tests for torznab.py — caps and search XML for Radarr/Sonarr."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from vn_source_gateway.config import Settings
from vn_source_gateway.torznab import build_releases, caps_response, search_response


@pytest.fixture
def settings() -> Settings:
    return Settings.load()


class TestCaps:
    def test_caps_is_valid_xml(self):
        root = ET.fromstring(caps_response())
        assert root.tag == "caps"

    def test_caps_advertises_movie_and_tv(self):
        root = ET.fromstring(caps_response())
        ids = {c.get("id") for c in root.iter("category")}
        assert "2000" in ids
        assert "5000" in ids


class TestSearchResponse:
    def test_valid_xml(self, settings):
        xml = search_response(settings, {"t": ["search"], "q": ["avengers"]})
        root = ET.fromstring(xml)
        assert root.tag == "rss"

    def test_movie_search_has_items(self, settings):
        xml = search_response(settings, {"t": ["movie"], "tmdbid": ["24428"]})
        root = ET.fromstring(xml)
        items = root.findall(".//item")
        assert len(items) > 0

    def test_item_has_enclosure_with_bittorrent_type(self, settings):
        """Radarr discards items without an enclosure of type application/x-bittorrent."""
        xml = search_response(settings, {"t": ["movie"], "tmdbid": ["24428"]})
        root = ET.fromstring(xml)
        for item in root.findall(".//item"):
            enc = item.find("enclosure")
            assert enc is not None, "every item must have an <enclosure>"
            assert enc.get("type") == "application/x-bittorrent"
            assert enc.get("url")
            assert int(enc.get("length")) > 0

    def test_item_has_correct_movie_category(self, settings):
        xml = search_response(settings, {"t": ["movie"], "tmdbid": ["24428"]})
        root = ET.fromstring(xml)
        ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
        for item in root.findall(".//item"):
            cats = {a.get("value") for a in item.findall("torznab:attr", ns)
                    if a.get("name") == "category"}
            assert "2000" in cats

    def test_tv_search_has_tv_category(self, settings):
        xml = search_response(settings, {"t": ["tvsearch"], "tvdbid": ["81189"],
                                         "season": ["1"], "ep": ["1"]})
        root = ET.fromstring(xml)
        ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
        items = root.findall(".//item")
        assert len(items) > 0
        for item in items:
            cats = {a.get("value") for a in item.findall("torznab:attr", ns)
                    if a.get("name") == "category"}
            assert "5000" in cats

    def test_tmdbid_attr_present_for_movie(self, settings):
        xml = search_response(settings, {"t": ["movie"], "tmdbid": ["24428"]})
        root = ET.fromstring(xml)
        ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
        item = root.find(".//item")
        tmdb_attrs = [a.get("value") for a in item.findall("torznab:attr", ns)
                      if a.get("name") == "tmdbid"]
        assert "24428" in tmdb_attrs


class TestBuildReleases:
    def test_one_release_per_source_and_mode(self, settings):
        # default source_order = [kkphim, ophim], expose_both_modes default
        releases = build_releases(settings, {"t": ["movie"], "tmdbid": ["24428"]})
        # 2 sources × N modes
        assert len(releases) >= 2
        assert all(r.kind == "movie" for r in releases)

    def test_tv_query_produces_episode_kind(self, settings):
        releases = build_releases(settings, {"t": ["tvsearch"], "tvdbid": ["81189"],
                                             "season": ["2"], "ep": ["5"]})
        assert all(r.kind == "episode" for r in releases)
        assert all(r.season_number == 2 and r.episode_number == 5 for r in releases)

    def test_empty_source_order_yields_nothing(self):
        from dataclasses import replace
        s = replace(Settings.load(), source_order=[])
        assert build_releases(s, {"t": ["movie"], "tmdbid": ["1"]}) == []
