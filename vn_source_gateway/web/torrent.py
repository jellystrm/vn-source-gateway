"""Minimal bencode helpers for generating and parsing fake .torrent grab files.

The gateway serves a synthetic .torrent from GET /grab/{token}.  When a
download client (Radarr/Sonarr) receives that file it POSTs it to
POST /api/v2/torrents/add as a multipart ``torrents`` file upload.  We
recover the original grab URL from the ``announce`` field embedded in the
bencode so we can route it through the normal job pipeline.
"""
from __future__ import annotations

import hashlib


# ---------------------------------------------------------------------------
# Bencode encoder
# ---------------------------------------------------------------------------

def bencode(obj: object) -> bytes:
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
        return str(len(raw)).encode() + b":" + raw
    if isinstance(obj, str):
        enc = obj.encode("utf-8")
        return str(len(enc)).encode() + b":" + enc
    if isinstance(obj, list):
        return b"l" + b"".join(bencode(i) for i in obj) + b"e"
    if isinstance(obj, dict):
        # Keys must be sorted lexicographically (bytes order)
        def _key(k: object) -> bytes:
            return k.encode("utf-8") if isinstance(k, str) else bytes(k)  # type: ignore[arg-type]

        items = sorted(obj.items(), key=lambda kv: _key(kv[0]))
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in items) + b"e"
    raise TypeError(f"Cannot bencode {type(obj)!r}")


# ---------------------------------------------------------------------------
# Minimal bencode string decoder (enough to extract the announce URL)
# ---------------------------------------------------------------------------

def _bdecode_string(data: bytes, pos: int) -> tuple[bytes, int]:
    """Decode a bencode byte-string starting at *pos*.

    Returns ``(raw_bytes, next_pos)``.
    """
    colon = data.index(b":", pos)
    length = int(data[pos:colon])
    start = colon + 1
    return data[start : start + length], start + length


def extract_announce(torrent_bytes: bytes) -> str | None:
    """Return the ``announce`` URL embedded in a bencode torrent, or *None*."""
    # Fast path: the torrent dict starts at byte 0 with 'd'.  The ``announce``
    # key is always one of the first keys (sorted order: a < c < i).
    key = b"8:announce"
    idx = torrent_bytes.find(key)
    if idx == -1:
        return None
    try:
        raw, _ = _bdecode_string(torrent_bytes, idx + len(key))
        return raw.decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fake .torrent generator
# ---------------------------------------------------------------------------

def make_grab_torrent(grab_url: str, name: str) -> bytes:
    """Return bencode bytes for a minimal single-file .torrent.

    The ``announce`` and ``comment`` fields both carry *grab_url* so the
    gateway can recover it when the file is uploaded back via
    ``/api/v2/torrents/add``.

    The ``info`` dict contains a single fake 1-byte file so bittorrent
    clients that inspect the torrent see a valid structure, but the file is
    never actually downloaded — the gateway intercepts the add call first.
    """
    piece_length = 262144  # 256 KiB — standard minimum
    # SHA-1 of a single zero byte as the pieces hash
    pieces: bytes = hashlib.sha1(b"\x00").digest()

    # bencode dict keys must be plain ASCII; piece hashes are raw bytes
    info: dict = {
        "length": 1,
        "name": (name + ".strm").encode("utf-8"),
        "piece length": piece_length,
        "pieces": pieces,
    }
    torrent: dict = {
        "announce": grab_url.encode("utf-8"),
        "comment": grab_url.encode("utf-8"),
        "info": info,
    }
    return bencode(torrent)
