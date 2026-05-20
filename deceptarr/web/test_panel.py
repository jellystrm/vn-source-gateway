"""Test tab — source resolver + Torznab query tester."""
from __future__ import annotations

import html
from typing import Any

from .cards import _attr

_RESOLVER_JS = r"""
(function () {
  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function epsHtml(eps, found, total) {
    var h = '<div style="font-size:11px;color:var(--muted);margin-bottom:4px">Found '
      + found + '/' + total + ' episodes</div>';
    var links = eps.filter(function(e) { return e.url; }).map(function(e) {
      return '<a href="' + esc(e.url) + '" target="_blank" '
        + 'style="font-size:11px;color:var(--accent);margin-right:6px">E'
        + String(e.num).padStart(2,'0') + '</a>';
    }).join('');
    return h + (links || '<span style="color:#e06c75;font-size:11px">No episodes found</span>');
  }

  window.srToggle = function () {
    var tv = document.getElementById('sr-type').value === 'tv';
    document.getElementById('sr-tv-f').style.display = tv ? 'flex' : 'none';
  };

  window.srTest = function () {
    var tid = (document.getElementById('sr-tmdb').value || '').trim();
    if (!tid) { alert('Please enter a TMDb ID'); return; }
    var payload = {
      tmdb_id: parseInt(tid),
      media_type: document.getElementById('sr-type').value,
    };
    var title = (document.getElementById('sr-title').value || '').trim();
    var year = (document.getElementById('sr-year').value || '').trim();
    if (title) payload.title = title;
    if (year) payload.year = parseInt(year);
    if (payload.media_type === 'tv') {
      var sv = (document.getElementById('sr-season').value || '').trim();
      var ev = (document.getElementById('sr-ep').value || '').trim();
      var tv = (document.getElementById('sr-tvdb').value || '').trim();
      if (sv) payload.season = parseInt(sv);
      if (ev) payload.episode = parseInt(ev);
      if (tv) payload.tvdb_id = parseInt(tv);
    }
    var scanMsg = (payload.media_type === 'tv' && payload.season && !payload.episode)
      ? 'Scanning all episodes of S' + String(payload.season).padStart(2,'0') + '…'
      : 'Resolving…';
    var res = document.getElementById('sr-results');
    res.innerHTML = '<p style="color:var(--muted);font-size:13px">' + scanMsg + '</p>';
    fetch('/api/source-test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var rows = Object.keys(d).map(function (nm) {
          var r = d[nm], ok = r.status === 'ok';
          var lines = (r.log || []).map(function (line) {
            return '<div style="padding:1px 0">' + esc(line) + '</div>';
          }).join('');
          var detail = ok
            ? (r.episodes != null
                ? epsHtml(r.episodes, r.found, r.total)
                : (r.urls || [{url:r.url}]).map(function (u, idx) {
                    var label = (u.server || u.name) ? '<span style="color:var(--muted);font-size:10px;margin-right:6px">'
                      + esc([u.server, u.name].filter(Boolean).join(' / ')) + '</span>' : '';
                    return '<div style="padding:1px 0">' + label
                      + '<a href="' + esc(u.url) + '" target="_blank" style="font-size:11px;word-break:break-all;color:var(--accent)">'
                      + esc((idx + 1) + '. ' + u.url.slice(0, 120) + (u.url.length > 120 ? '…' : '')) + '</a></div>';
                  }).join(''))
            : '<span style="color:#e06c75;font-size:11px">' + esc(r.message || 'Not found') + '</span>';
          var logBlock = lines
            ? '<details style="margin-top:6px"><summary style="cursor:pointer;color:var(--muted);font-size:11px">trace log</summary>'
              + '<div style="margin-top:6px;background:var(--input-bg);border:1px solid var(--border);border-radius:5px;padding:8px 10px;'
              + 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.4;color:var(--muted);white-space:normal">'
              + lines + '</div></details>'
            : '';
          return '<tr>'
            + '<td style="font-size:12px;padding:5px 10px;font-weight:500">' + esc(nm) + '</td>'
            + '<td style="padding:5px 8px"><span class="sdot ' + (ok ? 'ok' : 'err') + '"></span></td>'
            + '<td style="padding:5px 10px">' + detail + logBlock + '</td></tr>';
        });
        res.innerHTML = rows.length
          ? '<table class="jd-table"><tbody>' + rows.join('') + '</tbody></table>'
          : '<p style="color:var(--muted);font-size:13px">No sources configured.</p>';
      })
      .catch(function (e) {
        res.innerHTML = '<p style="color:#e06c75;font-size:13px">Error: ' + esc(String(e)) + '</p>';
      });
  };

  document.getElementById('sr-type').addEventListener('change', window.srToggle);
  window.srToggle();
})();
"""

_TORZNAB_JS = r"""
(function () {
  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function buildUrl() {
    var type = document.getElementById('tt-type').value;
    var key  = document.getElementById('tt-key').value;
    var p = new URLSearchParams({t: type, apikey: key});
    if (type === 'movie') {
      var q = document.getElementById('tt-q').value;
      var yr = document.getElementById('tt-year').value;
      var tm = document.getElementById('tt-tmdbid').value;
      var im = document.getElementById('tt-imdbid').value;
      if (q)  p.set('q', q);
      if (yr) p.set('year', yr);
      if (tm) p.set('tmdbid', tm);
      if (im) p.set('imdbid', im);
    } else {
      var tvq  = document.getElementById('tt-tvq').value;
      var tvdb = document.getElementById('tt-tvdbid').value;
      var tmtv = document.getElementById('tt-tmdbid-tv').value;
      var sea  = document.getElementById('tt-season').value;
      var ep   = document.getElementById('tt-ep').value;
      if (tvq)  p.set('q', tvq);
      if (tvdb) p.set('tvdbid', tvdb);
      if (tmtv) p.set('tmdbid', tmtv);
      if (sea)  p.set('season', sea);
      if (ep)   p.set('ep', ep);
    }
    var url = '/torznab/api?' + p.toString();
    document.getElementById('tt-url').textContent = url;
    return url;
  }

  window.ttToggle = function () {
    var movie = document.getElementById('tt-type').value === 'movie';
    document.getElementById('tt-movie-f').style.display = movie ? '' : 'none';
    document.getElementById('tt-tv-f').style.display    = movie ? 'none' : '';
    buildUrl();
  };

  window.ttSearch = function () {
    var url = buildUrl();
    var res = document.getElementById('tt-results');
    res.innerHTML = '<p style="color:var(--muted);font-size:13px;padding:8px 0">Searching…</p>';
    fetch(url)
      .then(function (r) { return r.text(); })
      .then(function (xml) {
        var doc = new DOMParser().parseFromString(xml, 'text/xml');
        var err = doc.querySelector('error');
        if (err) {
          res.innerHTML = '<p style="color:#e06c75;font-size:13px">Error: ' + esc(err.getAttribute('description') || xml) + '</p>';
          return;
        }
        var items = doc.querySelectorAll('item');
        if (!items.length) {
          res.innerHTML = '<p style="color:var(--muted);font-size:13px;padding:8px 0">No results returned.</p>';
          return;
        }
        var rows = Array.from(items).map(function (item) {
          var title = (item.querySelector('title') || {}).textContent || '';
          var enc   = item.querySelector('enclosure');
          var link  = enc ? (enc.getAttribute('url') || '') : '';
          var size  = enc ? (enc.getAttribute('length') || '') : '';
          var attrs = {};
          item.querySelectorAll('attr').forEach(function (a) {
            attrs[a.getAttribute('name')] = a.getAttribute('value');
          });
          var linkHtml = link
            ? '<a href="' + esc(link) + '" target="_blank" style="color:var(--accent);font-size:11px;word-break:break-all">'
              + esc(link.slice(0, 100) + (link.length > 100 ? '…' : '')) + '</a>'
            : '<span style="color:var(--muted)">—</span>';
          return '<tr>'
            + '<td style="font-size:12px;max-width:340px">' + esc(title) + '</td>'
            + '<td style="font-size:11px;color:var(--muted);white-space:nowrap">' + esc(attrs.tmdbid || '—') + '</td>'
            + '<td style="font-size:11px;color:var(--muted);white-space:nowrap">'
            + (size ? Math.round(parseInt(size) / 1048576) + ' MB' : '—') + '</td>'
            + '<td>' + linkHtml + '</td>'
            + '</tr>';
        });
        res.innerHTML = '<table class="jd-table"><thead><tr>'
          + '<th>Title</th><th>TMDb ID</th><th>Size</th><th>Grab URL</th>'
          + '</tr></thead><tbody>' + rows.join('') + '</tbody></table>';
      })
      .catch(function (e) {
        res.innerHTML = '<p style="color:#e06c75;font-size:13px">Fetch error: ' + esc(String(e)) + '</p>';
      });
  };

  document.querySelectorAll('#tt-movie-f input, #tt-tv-f input, #tt-key').forEach(function (el) {
    el.addEventListener('input', buildUrl);
  });
  document.getElementById('tt-type').addEventListener('change', window.ttToggle);
  buildUrl();
})();
"""


def test_panel(config: dict[str, Any]) -> str:
    api_key = _attr(config.get("torznab_api_key", ""))
    return f"""
<div class="card" style="margin-bottom:16px">
  <div class="card-header">
    <div>
      <div class="card-title">Source Resolver</div>
      <div class="card-desc">Test HLS URL resolution per-source — enter a TMDb ID and check which sources can serve it.</div>
    </div>
  </div>
  <div class="card-body">
    <div class="row" style="margin-bottom:14px">
      <div class="field">
        <label class="field-label">TMDb ID</label>
        <input id="sr-tmdb" type="number" placeholder="27205 (Inception) / 1396 (Breaking Bad)">
      </div>
      <div class="field">
        <label class="field-label">Title Override</label>
        <input id="sr-title" placeholder="Optional when TMDB key is empty">
      </div>
      <div class="field">
        <label class="field-label">Year</label>
        <input id="sr-year" type="number" placeholder="2010">
      </div>
      <div class="field">
        <label class="field-label">Media Type</label>
        <select id="sr-type">
          <option value="movie">Movie</option>
          <option value="tv">TV Series</option>
        </select>
      </div>
      <div id="sr-tv-f" style="display:none;flex-direction:row;gap:8px;flex-wrap:wrap">
        <div class="field">
          <label class="field-label">Season</label>
          <input id="sr-season" type="number" min="1" placeholder="1" style="width:80px">
        </div>
        <div class="field">
          <label class="field-label">Episode</label>
          <input id="sr-ep" type="number" min="1" placeholder="all" style="width:80px">
        </div>
        <div class="field">
          <label class="field-label">TVDb ID</label>
          <input id="sr-tvdb" type="number" placeholder="optional" style="width:110px">
        </div>
      </div>
    </div>
    <div class="actions" style="margin-bottom:20px">
      <button type="button" class="btn btn-primary" onclick="srTest()">&#9654; Resolve</button>
    </div>
    <div id="sr-results"></div>
  </div>
</div>

<div class="card">
  <div class="card-header">
    <div>
      <div class="card-title">Torznab Query Tester</div>
      <div class="card-desc">Simulate the exact HTTP request Radarr/Sonarr sends — same parameters, same endpoint. Inspect titles and grab URLs before Radarr/Sonarr sees them.</div>
    </div>
  </div>
  <div class="card-body">
    <div class="row" style="margin-bottom:14px">
      <div class="field">
        <label class="field-label">API Key</label>
        <input id="tt-key" value="{api_key}">
      </div>
      <div class="field">
        <label class="field-label">Type (t=)</label>
        <select id="tt-type" onchange="ttToggle()">
          <option value="movie">movie — Radarr</option>
          <option value="tvsearch">tvsearch — Sonarr</option>
        </select>
      </div>
    </div>
    <div id="tt-movie-f" class="row" style="margin-bottom:14px">
      <div class="field"><label class="field-label">Title (q=)</label>
        <input id="tt-q" placeholder="e.g. Inception"></div>
      <div class="field"><label class="field-label">Year</label>
        <input id="tt-year" type="number" placeholder="2010"></div>
      <div class="field"><label class="field-label">TMDb ID (tmdbid=)</label>
        <input id="tt-tmdbid" type="number" placeholder="27205"></div>
      <div class="field"><label class="field-label">IMDb ID (imdbid=)</label>
        <input id="tt-imdbid" placeholder="tt1375666"></div>
    </div>
    <div id="tt-tv-f" class="row" style="display:none;margin-bottom:14px">
      <div class="field"><label class="field-label">Series Title (q=)</label>
        <input id="tt-tvq" placeholder="e.g. Breaking Bad"></div>
      <div class="field"><label class="field-label">TVDb ID (tvdbid=)</label>
        <input id="tt-tvdbid" type="number" placeholder="81189"></div>
      <div class="field"><label class="field-label">TMDb ID (tmdbid=)</label>
        <input id="tt-tmdbid-tv" type="number" placeholder="1396"></div>
      <div class="field"><label class="field-label">Season (season=)</label>
        <input id="tt-season" type="number" value="1" min="1" style="width:80px"></div>
      <div class="field"><label class="field-label">Episode (ep=)</label>
        <input id="tt-ep" type="number" value="1" min="1" style="width:80px"></div>
    </div>
    <div style="margin-bottom:14px">
      <div class="field-label" style="margin-bottom:6px">Request URL</div>
      <code id="tt-url" style="display:block;background:var(--input-bg);border:1px solid var(--border);
        border-radius:5px;padding:8px 12px;font-size:12px;word-break:break-all;
        color:var(--accent);min-height:36px"></code>
    </div>
    <div class="actions" style="margin-bottom:20px">
      <button type="button" class="btn btn-primary" onclick="ttSearch()">&#9654; Send</button>
    </div>
    <div id="tt-results"></div>
  </div>
</div>
<script>{_RESOLVER_JS}</script>
<script>{_TORZNAB_JS}</script>"""
