"""Tests for state.py — StateStore persistence and retry logic."""
from __future__ import annotations

import json
import os
import time

import pytest
from vn_source_gateway.infrastructure.state import StateStore


@pytest.fixture
def state_path(tmp_path) -> str:
    return str(tmp_path / "state.json")


class TestStateStore:
    def test_fresh_store_no_attempts(self, state_path):
        store = StateStore(state_path)
        assert store.recently_attempted("movie:123", 3600) is False

    def test_mark_and_recently_attempted(self, state_path):
        store = StateStore(state_path)
        store.mark_attempt("movie:123", "/downloads/film.mkv", "kkphim")
        assert store.recently_attempted("movie:123", 3600) is True

    def test_retry_after_expires(self, state_path):
        store = StateStore(state_path)
        store.mark_attempt("movie:123", "/downloads/film.mkv", "kkphim")
        # retry_after=0 means always retry
        assert store.recently_attempted("movie:123", 0) is False

    def test_different_keys_independent(self, state_path):
        store = StateStore(state_path)
        store.mark_attempt("movie:111", "/path/a.mkv", "kkphim")
        assert store.recently_attempted("movie:222", 3600) is False
        assert store.recently_attempted("movie:111", 3600) is True

    def test_persists_to_disk(self, state_path):
        store = StateStore(state_path)
        store.mark_attempt("episode:tv:s01e01", "/path/ep.mkv", "ophim")
        assert os.path.exists(state_path)
        # Reload from disk
        store2 = StateStore(state_path)
        assert store2.recently_attempted("episode:tv:s01e01", 3600) is True

    def test_persisted_data_structure(self, state_path):
        store = StateStore(state_path)
        store.mark_attempt("movie:999", "/downloads/x.mkv", "kkphim")
        with open(state_path) as f:
            data = json.load(f)
        attempt = data["attempts"]["movie:999"]
        assert attempt["path"] == "/downloads/x.mkv"
        assert attempt["source"] == "kkphim"
        assert "attempted_at" in attempt

    def test_load_nonexistent_path_is_ok(self, tmp_path):
        store = StateStore(str(tmp_path / "nonexistent" / "state.json"))
        # Should not raise, just start empty
        assert store.recently_attempted("any", 3600) is False

    def test_save_creates_parent_dirs(self, tmp_path):
        nested_path = str(tmp_path / "deep" / "nested" / "state.json")
        store = StateStore(nested_path)
        store.mark_attempt("key", "/path", "source")
        assert os.path.exists(nested_path)
