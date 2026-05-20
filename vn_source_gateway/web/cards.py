from __future__ import annotations

import html
import json
import time
from typing import Any

from vn_source_gateway.infrastructure.activity import ActivityLog


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'


def _poll_fields(prefix: str, config: dict[str, Any]) -> str:
    """Collapsible poll-interval + max-items fields, toggled by a 'poll enabled' checkbox.

    ``prefix`` is "movie" or "series" so the toggle JS ID is unique per card.
    """
    enabled_field = "movie_enabled" if prefix == "movie" else "series_enabled"
    is_enabled = bool(config.get(enabled_field, False))
    disabled = "" if is_enabled else " disabled"
    opacity = "" if is_enabled else " style='opacity:.45;pointer-events:none'"
    return f"""
        <div class="checks" style="margin-bottom:10px">
          <label class="check-item">
            <input type="checkbox" name="{enabled_field}" id="chk-{prefix}-enabled"
              {_checked(is_enabled)}
              onchange="(function(c){{
                var wrap=document.getElementById('poll-fields-{prefix}');
                wrap.style.opacity=c.checked?'1':'0.45';
                wrap.style.pointerEvents=c.checked?'':'none';
                wrap.querySelectorAll('input,select').forEach(function(i){{i.disabled=!c.checked}});
              }})(this)">
            Poll {prefix}s
          </label>
        </div>
        <div id="poll-fields-{prefix}"{opacity}>
          <div class="row">
            <div class="field"><label class="field-label">Poll Interval (seconds)</label>
              <input name="poll_interval_seconds" type="number" min="10"{disabled}
                value="{_attr(config["poll_interval_seconds"])}"></div>
            <div class="field"><label class="field-label">Max Items Per Poll</label>
              <input name="max_items_per_poll" type="number" min="1"{disabled}
                value="{_attr(config["max_items_per_poll"])}"></div>
          </div>
        </div>"""


def radarr_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="radarr">
      <div class="card-header">
        <div><div class="card-title">Radarr</div>
        <div class="card-desc">Movie manager — connection and polling</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Radarr URL</label>
            <input name="radarr_url" value="{_attr(config["radarr_url"])}" placeholder="http://radarr:7878"></div>
          <div class="field"><label class="field-label">Radarr API Key</label>
            <input name="radarr_api_key" type="password" value="{_attr(config["radarr_api_key"])}"></div>
        </div>
        <hr class="sep">
        {_poll_fields("movie", config)}
      </div>
    </div>"""


def sonarr_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="sonarr">
      <div class="card-header">
        <div><div class="card-title">Sonarr</div>
        <div class="card-desc">Series manager — connection and polling</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Sonarr URL</label>
            <input name="sonarr_url" value="{_attr(config["sonarr_url"])}" placeholder="http://sonarr:8989"></div>
          <div class="field"><label class="field-label">Sonarr API Key</label>
            <input name="sonarr_api_key" type="password" value="{_attr(config["sonarr_api_key"])}"></div>
        </div>
        <hr class="sep">
        {_poll_fields("series", config)}
      </div>
    </div>"""


def worker_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="worker">
      <div class="card-header">
        <div><div class="card-title">Worker</div>
        <div class="card-desc">State storage, retry policy, and UI settings</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Retry After (seconds)</label>
            <input name="retry_after_seconds" type="number" min="0" value="{_attr(config["retry_after_seconds"])}"></div>
          <div class="field"><label class="field-label">Job Detail Retention (hours)</label>
            <input name="job_detail_retention_hours" type="number" min="1" value="{_attr(config["job_detail_retention_hours"])}"></div>
          <div class="field"><label class="field-label">State Path</label>
            <input name="state_path" value="{_attr(config["state_path"])}"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="worker_enabled" {_checked(config["worker_enabled"])}> Worker Enabled</label>
          <label class="check-item"><input type="checkbox" name="ui_enabled" {_checked(config["ui_enabled"])}> UI Enabled</label>
        </div>
      </div>
    </div>"""


def media_managers_card(config: dict[str, Any]) -> str:
    return f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="radarr">
      {radarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Radarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Radarr</button>
      </div>
    </form>
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="sonarr">
      {sonarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Sonarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Sonarr</button>
      </div>
    </form>
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="worker">
      {worker_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Worker</button>
      </div>
    </form>"""


def sources_card(config: dict[str, Any], templates: str, source_order: str) -> str:
    """Sources page: JS-managed source list with priority, per-source mode/container, and test panel."""
    import json as _json
    sources_data = config.get("hls_template_sources", [])
    # Serialize for JS injection — escape </script> to avoid breaking the tag
    sources_json = _json.dumps(sources_data, ensure_ascii=False).replace("</", "<\\/")

    # --- JavaScript source manager ---
    src_js = (
        "(function(){"
        "var S=" + sources_json + ";"
        r"""
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function render(){
  var c=document.getElementById('src-list');
  if(!S.length){c.innerHTML='<p style="color:var(--muted);font-size:13px;padding:8px 0">No sources yet. Click &quot;+ Add Source&quot;.</p>';}
  else{c.innerHTML=S.map(function(s,i){return row(s,i);}).join('');}
  sync();
}
function sel(val,opts){
  return opts.map(function(o){return '<option value="'+esc(o[0])+'"'+(val===o[0]?' selected':'')+'>'+esc(o[1])+'</option>';}).join('');
}
function row(s,i){
  var n=S.length;
  return '<div style="display:flex;align-items:flex-start;gap:8px;padding:10px 0;border-bottom:1px solid var(--border)">'
    +'<div style="min-width:20px;text-align:center;font-size:11px;color:var(--muted);padding-top:28px">'+(i+1)+'</div>'
    +'<div style="display:flex;flex-direction:column;gap:2px;padding-top:24px">'
    +'<button type="button" onclick="sUp('+i+')" '+(i===0?'disabled':'')+' style="padding:0 4px;font-size:12px;line-height:1.4;cursor:pointer">↑</button>'
    +'<button type="button" onclick="sDn('+i+')" '+(i===n-1?'disabled':'')+' style="padding:0 4px;font-size:12px;line-height:1.4;cursor:pointer">↓</button>'
    +'</div>'
    +'<div style="flex:1;min-width:0">'
    +'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px">'
    +'<div class="field" style="flex:1;min-width:140px"><label class="field-label">Name</label>'
    +'<input value="'+esc(s.name||'')+'" oninput="sSet('+i+',\'name\',this.value)" placeholder="my-source"></div>'
    +'<div class="field"><label class="field-label">Output</label><select onchange="sSet('+i+',\'output_mode\',this.value)">'
    +sel(s.output_mode||'strm',[['strm','STRM (.strm)'],['download','Download (ffmpeg)']])
    +'</select></div>'
    +'<div class="field"><label class="field-label">Container</label><select onchange="sSet('+i+',\'container\',this.value)">'
    +sel(s.container||'mkv',[['mkv','MKV'],['mp4','MP4']])
    +'</select></div>'
    +'</div>'
    +'<details style="margin-top:2px"><summary style="font-size:11px;color:var(--muted);cursor:pointer;user-select:none">URL templates</summary>'
    +'<div style="display:grid;gap:6px;margin-top:6px">'
    +'<div class="field"><label class="field-label">Movie URL template</label>'
    +'<input value="'+esc(s.movie_url_template||'')+'" oninput="sSet('+i+',\'movie_url_template\',this.value)" placeholder="https://…/{tmdb_id}"></div>'
    +'<div class="field"><label class="field-label">Series URL template</label>'
    +'<input value="'+esc(s.series_url_template||'')+'" oninput="sSet('+i+',\'series_url_template\',this.value)" placeholder="https://…/{tmdb_id}/{season}/{episode}"></div>'
    +'<div class="field"><label class="field-label">Movie resolver URL</label>'
    +'<input value="'+esc(s.movie_resolver_url_template||'')+'" oninput="sSet('+i+',\'movie_resolver_url_template\',this.value)" placeholder="Returns JSON {hls_url:…}"></div>'
    +'<div class="field"><label class="field-label">Series resolver URL</label>'
    +'<input value="'+esc(s.series_resolver_url_template||'')+'" oninput="sSet('+i+',\'series_resolver_url_template\',this.value)" placeholder="Returns JSON {hls_url:…}"></div>'
    +'</div></details>'
    +'</div>'
    +'<button type="button" class="btn btn-danger btn-small" onclick="sRm('+i+')" style="align-self:center;margin-left:4px">×</button>'
    +'</div>';
}
function sync(){var e=document.getElementById('hls-sources-json');if(e)e.value=JSON.stringify(S);}
window.sUp=function(i){if(i===0)return;var t=S[i-1];S[i-1]=S[i];S[i]=t;render();};
window.sDn=function(i){if(i>=S.length-1)return;var t=S[i+1];S[i+1]=S[i];S[i]=t;render();};
window.sRm=function(i){if(!confirm('Remove "'+esc(S[i].name||'?')+'"?'))return;S.splice(i,1);render();};
window.sSet=function(i,k,v){S[i][k]=v;sync();};
window.srcAddNew=function(){
  S.push({name:'new-source',output_mode:'strm',container:'mkv',
          movie_url_template:'',series_url_template:'',
          movie_resolver_url_template:'',series_resolver_url_template:''});
  render();
};
// media-type toggle for test panel
var mt=document.getElementById('src-test-type');
if(mt){
  function tvToggle(){var tv=mt.value==='tv';
    ['src-test-season-f','src-test-ep-f'].forEach(function(id){
      var el=document.getElementById(id);if(el)el.style.display=tv?'':'none';});
  }
  mt.addEventListener('change',tvToggle);tvToggle();
}
// Test sources
window.sourcesTest=function(){
  var tid=(document.getElementById('src-test-tmdb')||{}).value||'';
  if(!tid){alert('Please enter a TMDB ID');return;}
  var p={tmdb_id:parseInt(tid),media_type:document.getElementById('src-test-type').value};
  if(p.media_type==='tv'){
    p.season=parseInt((document.getElementById('src-test-season')||{}).value)||1;
    p.episode=parseInt((document.getElementById('src-test-ep')||{}).value)||1;
  }
  var res=document.getElementById('src-test-results');
  res.innerHTML='<p style="color:var(--muted);font-size:13px">Testing…</p>';
  fetch('/api/source-test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})
    .then(function(r){return r.json();})
    .then(function(d){
      var rows=Object.keys(d).map(function(nm){
        var r=d[nm],ok=r.status==='ok';
        var det=ok?'<a href="'+esc(r.url)+'" target="_blank" style="font-size:11px;word-break:break-all">'+esc(r.url.slice(0,120)+(r.url.length>120?'…':''))+'</a>'
                  :'<span style="color:var(--err);font-size:11px">'+esc(r.message||'Not found')+'</span>';
        return '<tr><td style="padding:4px 10px;font-weight:500">'+esc(nm)+'</td>'
              +'<td style="padding:4px 8px"><span class="sdot '+(ok?'ok':'err')+'"></span></td>'
              +'<td style="padding:4px 10px">'+det+'</td></tr>';
      });
      res.innerHTML=rows.length
        ?'<table style="width:100%"><tbody>'+rows.join('')+'</tbody></table>'
        :'<p style="color:var(--muted);font-size:13px">No sources configured.</p>';
    })
    .catch(function(e){res.innerHTML='<p style="color:var(--err);font-size:13px">Error: '+esc(String(e))+'</p>';});
};
render();
"""
        + "})();"
    )

    return f"""
<form method="post" action="/save">
  <input type="hidden" name="_section" value="sources">
  <div class="card" id="sources">
    <div class="card-header">
      <div><div class="card-title">Sources</div>
      <div class="card-desc">Priority-ordered HLS sources — first match wins at grab time</div></div>
    </div>
    <div class="card-body">
      <div id="src-list"></div>
      <div class="actions" style="margin:10px 0 0">
        <button type="button" class="btn btn-ghost" onclick="srcAddNew()">+ Add Source</button>
      </div>
      <input type="hidden" name="hls_template_sources" id="hls-sources-json" value="{_attr(templates)}">
    </div>
  </div>
  <div class="card" id="source-test-card" style="margin-top:14px">
    <div class="card-header">
      <div><div class="card-title">Test Sources</div>
      <div class="card-desc">Resolve a TMDB ID against each configured source to verify URLs</div></div>
    </div>
    <div class="card-body">
      <div class="row">
        <div class="field" style="flex:1;min-width:160px"><label class="field-label">TMDB ID</label>
          <input id="src-test-tmdb" type="number" placeholder="e.g. 27205">
          <span style="font-size:11px;color:var(--muted)">Movie: 27205 (Inception) · TV: 1396 (Breaking Bad), 37854 (One Piece)</span>
        </div>
        <div class="field"><label class="field-label">Media Type</label>
          <select id="src-test-type">
            <option value="movie">Movie</option>
            <option value="tv">TV Series</option>
          </select>
        </div>
        <div class="field" id="src-test-season-f" style="display:none"><label class="field-label">Season</label>
          <input id="src-test-season" type="number" min="1" value="1" style="width:70px">
        </div>
        <div class="field" id="src-test-ep-f" style="display:none"><label class="field-label">Episode</label>
          <input id="src-test-ep" type="number" min="1" value="1" style="width:70px">
        </div>
      </div>
      <div class="actions" style="margin-bottom:10px">
        <button type="button" class="btn btn-ghost" onclick="sourcesTest()">&#9654; Test</button>
      </div>
      <div id="src-test-results"></div>
    </div>
  </div>
  <div class="actions">
    <button type="submit" class="btn btn-primary">&#10003; Save Sources</button>
  </div>
</form>
<script>{src_js}</script>"""


def tasks_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="tasks">
      <div class="card-header">
        <div><div class="card-title">Tasks</div><div class="card-desc">TMDB API key for title and episode lookups</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">TMDB API Key</label>
            <input name="tmdb_api_key" type="password" value="{_attr(config["tmdb_api_key"])}" placeholder="Required for title/year lookup and season expansion">
            <span style="font-size:11px;color:var(--muted)">Get a free key at <a href="https://www.themoviedb.org/settings/api" target="_blank">themoviedb.org</a></span>
          </div>
        </div>
      </div>
    </div>"""


def output_card(config: dict[str, Any], ffmpeg_args: str) -> str:
    return f"""
    <div class="card" id="output">
      <div class="card-header">
        <div><div class="card-title">Output</div><div class="card-desc">Release exposure, ffmpeg, container, and import settings</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">Default Output Mode</label>
            <select name="default_output_mode">
              {_option("strm", config["default_output_mode"])}
              {_option("download", config["default_output_mode"])}
            </select></div>
          <div class="field"><label class="field-label">Download Container</label>
            <select name="download_container">
              {_option("mkv", config["download_container"])}
              {_option("mp4", config["download_container"])}
            </select></div>
          <div class="field"><label class="field-label">Import Mode</label>
            <select name="import_mode">
              {_option("Move", config["import_mode"])}
              {_option("Copy", config["import_mode"])}
              {_option("Auto", config["import_mode"])}
            </select></div>
          <div class="field"><label class="field-label">FFmpeg Path</label>
            <input name="ffmpeg_path" value="{_attr(config["ffmpeg_path"])}"></div>
          <div class="field"><label class="field-label">FFmpeg Extra Args</label>
            <input name="ffmpeg_extra_args" value="{_attr(ffmpeg_args)}" placeholder="-user_agent,Something"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="expose_both_modes" {_checked(config["expose_both_modes"])}> Show both STRM and HLS-DL releases</label>
        </div>
      </div>
    </div>"""


def indexer_card(config: dict[str, Any]) -> str:
    torznab_url = config["public_base_url"] + "/torznab/api"
    server_labels_val = ", ".join(config.get("server_labels") or [])
    return f"""
    <div class="card" id="indexer">
      <div class="card-header">
        <div><div class="card-title">Indexer</div><div class="card-desc">Torznab API endpoint for Radarr/Sonarr</div></div>
      </div>
      <div class="card-body">
        <div class="row cols-3">
          <div class="field"><label class="field-label">Torznab URL</label>
            <input readonly value="{_attr(torznab_url)}"></div>
          <div class="field"><label class="field-label">API Key</label>
            <input name="torznab_api_key" value="{_attr(config["torznab_api_key"])}"></div>
          <div class="field"><label class="field-label">Public Base URL</label>
            <input name="public_base_url" value="{_attr(config["public_base_url"])}"></div>
        </div>
        <hr class="sep">
        <div class="row">
          <div class="field">
            <label class="field-label">Server Labels (comma-separated)</label>
            <input name="server_labels" value="{_attr(server_labels_val)}" placeholder="ViệtSub, Lồng Tiếng, Thuyết Minh">
            <span style="font-size:11px;color:var(--muted)">Labels generate separate release entries so Radarr/Sonarr can select ViệtSub vs Lồng Tiếng. Leave empty for a single undifferentiated release.</span>
          </div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="torznab_group_sources" {_checked(config.get("torznab_group_sources", False))}> Group sources — one result per episode (auto-selects best source at grab time)</label>
        </div>
      </div>
    </div>"""


def downloader_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="downloader">
      <div class="card-header">
        <div><div class="card-title">Download Client</div><div class="card-desc">qBittorrent-compatible API endpoint</div></div>
      </div>
      <div class="card-body">
        <div class="row cols-3">
          <div class="field"><label class="field-label">Host</label>
            <input name="ui_host" value="{_attr(config["ui_host"])}"></div>
          <div class="field"><label class="field-label">Port</label>
            <input name="ui_port" type="number" min="1" max="65535" value="{_attr(config["ui_port"])}"></div>
          <div class="field"><label class="field-label">Compatibility</label>
            <input readonly value="qBittorrent Web API"></div>
          <div class="field"><label class="field-label">Username</label>
            <input name="qb_username" value="{_attr(config["qb_username"])}"></div>
          <div class="field"><label class="field-label">Password</label>
            <input name="qb_password" type="password" value="{_attr(config["qb_password"])}"></div>
          <div class="field"><label class="field-label">Log Level</label>
            <select name="log_level">
              {_option("DEBUG", config["log_level"])}
              {_option("INFO", config["log_level"])}
              {_option("WARNING", config["log_level"])}
              {_option("ERROR", config["log_level"])}
            </select></div>
        </div>
      </div>
    </div>"""


def jellyfin_card(config: dict[str, Any]) -> str:
    return f"""
    <div class="card" id="jellyfin">
      <div class="card-header">
        <div><div class="card-title">Jellyfin</div><div class="card-desc">Optional library scan integration</div></div>
      </div>
      <div class="card-body">
        <div class="row">
          <div class="field"><label class="field-label">URL</label>
            <input name="jellyfin_url" value="{_attr(config["jellyfin_url"])}" placeholder="http://jellyfin:8096"></div>
          <div class="field"><label class="field-label">API Key</label>
            <input name="jellyfin_api_key" type="password" value="{_attr(config["jellyfin_api_key"])}"></div>
        </div>
        <hr class="sep">
        <div class="checks">
          <label class="check-item"><input type="checkbox" name="jellyfin_scan_after_strm" {_checked(config["jellyfin_scan_after_strm"])}> Scan library after STRM created</label>
        </div>
      </div>
    </div>"""


def activity_log_card() -> str:
    events = ActivityLog.get().recent(30)
    if not events:
        body = "<p style='color:var(--muted);font-size:13px'>No activity yet.</p>"
    else:
        KIND_ICON = {"search": "&#128269;", "grab": "&#128229;", "job": "&#9881;"}
        KIND_LABEL = {"search": "Search", "grab": "Grab", "job": "Job"}
        rows = []
        now = int(time.time())
        for ev in events:
            age = now - ev.ts
            if age < 60:
                age_str = f"{age}s ago"
            elif age < 3600:
                age_str = f"{age // 60}m ago"
            else:
                age_str = f"{age // 3600}h ago"
            icon = KIND_ICON.get(ev.kind, "•")
            label = KIND_LABEL.get(ev.kind, ev.kind)
            status_cls = {"ok": "running", "error": "error"}.get(ev.status, "")
            rows.append(
                f"<tr>"
                f"<td style='color:var(--muted);white-space:nowrap'>{age_str}</td>"
                f"<td><span class='badge {status_cls}'>{icon} {label}</span></td>"
                f"<td>{html.escape(ev.title)}</td>"
                f"<td style='color:var(--muted)'>{html.escape(ev.detail)}</td>"
                f"</tr>"
            )
        body = (
            "<table><thead><tr><th>When</th><th>Type</th><th>Title</th><th>Detail</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
        )
    return f"""
  <div class="card" id="activity-log">
    <div class="card-header">
      <div><div class="card-title">Activity Log</div>
      <div class="card-desc">Indexer searches, grabs, and job results — live pipeline view</div></div>
    </div>
    <div class="card-body">{body}</div>
  </div>"""


def download_tasks_card(tasks_html: str) -> str:
    return f"""
  <div class="card" id="download-tasks">
    <div class="card-header">
      <div><div class="card-title">Download Tasks</div><div class="card-desc">Queued, running, paused, completed, and failed gateway tasks</div></div>
    </div>
    <div class="card-body">{tasks_html}</div>
  </div>"""


def settings_card(config: dict[str, Any], ffmpeg_args: str, active_tab: str) -> str:
    tabs = [
        ("radarr", "Radarr"),
        ("sonarr", "Sonarr"),
        ("worker", "Worker"),
        ("tasks", "Tasks"),
        ("output", "Output"),
        ("indexer", "Indexer"),
        ("downloader", "Download Client"),
        ("jellyfin", "Jellyfin"),
    ]
    valid_tabs = {key for key, _ in tabs}
    active_tab = active_tab if active_tab in valid_tabs else "radarr"
    tab_html = "\n      ".join(
        f'<a href="/settings?tab={_attr(key)}" class="settings-tab{" active" if key == active_tab else ""}">{html.escape(label)}</a>'
        for key, label in tabs
    )

    if active_tab == "radarr":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="radarr">
      {radarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Radarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Radarr</button>
      </div>
    </form>"""
    elif active_tab == "sonarr":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="sonarr">
      {sonarr_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Sonarr</button>
        <button type="submit" formaction="/test" class="btn btn-ghost">Test Sonarr</button>
      </div>
    </form>"""
    elif active_tab == "worker":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="worker">
      {worker_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Worker</button>
      </div>
    </form>"""
    elif active_tab == "tasks":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="tasks">
      {tasks_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Tasks</button>
      </div>
    </form>"""
    elif active_tab == "output":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="runtime">
      {output_card(config, ffmpeg_args)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Output</button>
      </div>
    </form>"""
    elif active_tab == "indexer":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="indexer">
      {indexer_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Indexer</button>
      </div>
    </form>"""
    elif active_tab == "downloader":
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="downloader">
      {downloader_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Download Client</button>
      </div>
    </form>"""
    else:
        form = f"""
    <form method="post" action="/save">
      <input type="hidden" name="_section" value="jellyfin">
      {jellyfin_card(config)}
      <div class="actions">
        <button type="submit" class="btn btn-primary">&#10003; Save Jellyfin</button>
      </div>
    </form>"""

    return f"""
    <div class="settings-tabs" role="tablist">
      {tab_html}
    </div>
    {form}"""
