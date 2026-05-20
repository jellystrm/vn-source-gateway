from __future__ import annotations

import html
import json
import time
from typing import Any

from deceptarr.infrastructure.activity import ActivityLog


def _attr(value: object) -> str:
    return html.escape(str(value), quote=True)


def _checked(value: object) -> str:
    return "checked" if bool(value) else ""


def _option(value: str, selected: object) -> str:
    selected_attr = " selected" if str(selected).lower() == value.lower() else ""
    return f'<option value="{_attr(value)}"{selected_attr}>{html.escape(value)}</option>'


def _poll_fields(prefix: str, config: dict[str, Any]) -> str:
    """Poll enable checkbox + interval/max fields. Fields grey-out when polling is disabled."""
    enabled_field = "movie_enabled" if prefix == "movie" else "series_enabled"
    is_enabled = bool(config.get(enabled_field, False))
    disabled = "" if is_enabled else " disabled"
    wrap_opacity = "" if is_enabled else " style='opacity:0.4'"
    media_label = "movies" if prefix == "movie" else "series"
    # Single-line JS keeps the attribute simple; toggles disabled + opacity on sibling div
    js = (
        f"var w=document.getElementById('pf-{prefix}');"
        f"w.style.opacity=this.checked?'':'0.4';"
        f"w.querySelectorAll('input').forEach(function(i){{i.disabled=!this.checked}},this)"
    )
    return f"""
        <div class="checks" style="margin-bottom:10px">
          <label class="check-item">
            <input type="checkbox" name="{enabled_field}" {_checked(is_enabled)} onchange="{js}">
            Poll {media_label}
          </label>
        </div>
        <div id="pf-{prefix}"{wrap_opacity}>
          <div class="row">
            <div class="field"><label class="field-label">Poll Interval (seconds)</label>
              <input name="poll_interval_seconds" type="number" min="10"{disabled}
                value="{_attr(config['poll_interval_seconds'])}"></div>
            <div class="field"><label class="field-label">Max Items Per Poll</label>
              <input name="max_items_per_poll" type="number" min="1"{disabled}
                value="{_attr(config['max_items_per_poll'])}"></div>
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
    """Sources page: combined priority list of built-in + custom sources, with reorder and test panel."""
    from deceptarr.sources import BUILTIN_SOURCES, DEFAULT_SOURCE_ORDER

    sources_data = config.get("hls_template_sources", [])
    custom_names = [s.get("name", "") for s in sources_data if s.get("name")]
    configured_order = config.get("source_order", DEFAULT_SOURCE_ORDER)
    all_available = set(list(BUILTIN_SOURCES.keys()) + custom_names)
    # Preserve user-defined order, then append any new sources not yet listed.
    initial_order: list[str] = [n for n in configured_order if n in all_available]
    for n in list(BUILTIN_SOURCES.keys()) + custom_names:
        if n not in initial_order:
            initial_order.append(n)

    sources_json = json.dumps(sources_data, ensure_ascii=False).replace("</", "<\\/")
    order_json = json.dumps(initial_order, ensure_ascii=False).replace("</", "<\\/")
    builtin_info = {
        name: {"url": url, "label": f"{name} ({url})"}
        for name, url in BUILTIN_SOURCES.items()
    }
    builtin_info_js = json.dumps(builtin_info, ensure_ascii=False).replace("</", "<\\/")

    # --- JavaScript source manager ---
    src_js = (
        "(function(){"
        + "var S=" + sources_json + ";"
        + "var ORDER=" + order_json + ";"
        + "var BUILTIN=" + builtin_info_js + ";"
        + r"""
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function render(){
  var c=document.getElementById('src-list');
  if(!ORDER.length){c.innerHTML='<p style="color:var(--muted);font-size:13px;padding:8px 0">No sources configured. Click &quot;+ Add Source&quot; to add a custom source.</p>';sync();return;}
  c.innerHTML=ORDER.map(function(name,oi){
    if(BUILTIN[name])return builtinRow(name,oi);
    var si=S.findIndex(function(s){return s.name===name;});
    if(si<0)return '';
    return customRow(S[si],si,oi);
  }).join('');
  sync();
}
function rBtn(label,onclick,dis){
  var base='background:none;border:none;color:var(--muted);font-size:15px;line-height:1;cursor:pointer;padding:1px 5px;border-radius:3px;display:block;font-family:inherit';
  var d=dis?';opacity:0.18;cursor:default':'';
  return '<button type="button" '+(dis?'disabled ':'')+' onclick="'+onclick+'" style="'+base+d+'">'+label+'</button>';
}
function rBtns(oi,n){
  return '<div style="display:flex;flex-direction:column;gap:0">'+rBtn('↑','oUp('+oi+')',oi===0)+rBtn('↓','oDn('+oi+')',oi>=n-1)+'</div>';
}
function builtinRow(name,oi){
  var n=ORDER.length;
  return '<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:6px;margin-bottom:6px">'
    +'<span style="min-width:14px;font-size:11px;color:var(--muted);text-align:center;flex-shrink:0">'+(oi+1)+'</span>'
    +rBtns(oi,n)
    +'<div style="flex:1;min-width:0;display:flex;align-items:center;gap:10px;flex-wrap:wrap">'
    +'<span style="font-weight:600;font-size:14px">'+esc(name)+'</span>'
    +'<span style="font-size:12px;color:var(--muted)">'+esc(BUILTIN[name].url)+'</span>'
    +'</div>'
    +'<span style="background:rgba(99,179,237,0.12);color:#63b3ed;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;text-transform:uppercase;letter-spacing:.6px;white-space:nowrap;flex-shrink:0">Built-in</span>'
    +'</div>';
}
function sel(val,opts){
  return opts.map(function(o){return '<option value="'+esc(o[0])+'"'+(val===o[0]?' selected':'')+'>'+esc(o[1])+'</option>';}).join('');
}
function customRow(s,si,oi){
  var n=ORDER.length;
  return '<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 14px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:6px;margin-bottom:6px">'
    +'<span style="min-width:14px;font-size:11px;color:var(--muted);text-align:center;flex-shrink:0;padding-top:30px">'+(oi+1)+'</span>'
    +'<div style="padding-top:26px;flex-shrink:0">'+rBtns(oi,n)+'</div>'
    +'<div style="flex:1;min-width:0">'
    +'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px">'
    +'<div class="field" style="flex:1;min-width:140px"><label class="field-label">Name</label>'
    +'<input value="'+esc(s.name||'')+'" oninput="sSet('+si+',\'name\',this.value)" placeholder="my-source"></div>'
    +'<div class="field"><label class="field-label">Output</label><select onchange="sSet('+si+',\'output_mode\',this.value)">'
    +sel(s.output_mode||'strm',[['strm','STRM (.strm)'],['download','Download (ffmpeg)']])
    +'</select></div>'
    +'<div class="field"><label class="field-label">Container</label><select onchange="sSet('+si+',\'container\',this.value)">'
    +sel(s.container||'mkv',[['mkv','MKV'],['mp4','MP4']])
    +'</select></div>'
    +'</div>'
    +'<details style="margin-top:2px"><summary style="font-size:11px;color:var(--muted);cursor:pointer;user-select:none">URL templates</summary>'
    +'<div style="display:grid;gap:6px;margin-top:6px">'
    +'<div class="field"><label class="field-label">Movie URL template</label>'
    +'<input value="'+esc(s.movie_url_template||'')+'" oninput="sSet('+si+',\'movie_url_template\',this.value)" placeholder="https://…/{tmdb_id}"></div>'
    +'<div class="field"><label class="field-label">Series URL template</label>'
    +'<input value="'+esc(s.series_url_template||'')+'" oninput="sSet('+si+',\'series_url_template\',this.value)" placeholder="https://…/{tmdb_id}/{season}/{episode}"></div>'
    +'<div class="field"><label class="field-label">Movie resolver URL</label>'
    +'<input value="'+esc(s.movie_resolver_url_template||'')+'" oninput="sSet('+si+',\'movie_resolver_url_template\',this.value)" placeholder="Returns JSON {hls_url:…}"></div>'
    +'<div class="field"><label class="field-label">Series resolver URL</label>'
    +'<input value="'+esc(s.series_resolver_url_template||'')+'" oninput="sSet('+si+',\'series_resolver_url_template\',this.value)" placeholder="Returns JSON {hls_url:…}"></div>'
    +'</div></details>'
    +'</div>'
    +'<button type="button" class="btn btn-danger btn-small" onclick="sRm('+si+')" style="align-self:center;margin-left:4px">×</button>'
    +'</div>';
}
function sync(){
  var e=document.getElementById('hls-sources-json');if(e)e.value=JSON.stringify(S);
  var o=document.getElementById('source-order-json');if(o)o.value=JSON.stringify(ORDER);
}
window.oUp=function(i){if(i===0)return;var t=ORDER[i-1];ORDER[i-1]=ORDER[i];ORDER[i]=t;render();};
window.oDn=function(i){if(i>=ORDER.length-1)return;var t=ORDER[i+1];ORDER[i+1]=ORDER[i];ORDER[i]=t;render();};
window.sSet=function(si,k,v){
  var old=S[si][k];S[si][k]=v;
  if(k==='name'){var oi=ORDER.indexOf(String(old));if(oi>=0)ORDER[oi]=v;}
  sync();
};
window.sRm=function(si){
  var name=S[si].name||'?';
  if(!confirm('Remove "'+esc(name)+'"?'))return;
  S.splice(si,1);
  var oi=ORDER.indexOf(name);if(oi>=0)ORDER.splice(oi,1);
  render();
};
window.srcAddNew=function(){
  var nm='new-source';
  S.push({name:nm,output_mode:'strm',container:'mkv',
          movie_url_template:'',series_url_template:'',
          movie_resolver_url_template:'',series_resolver_url_template:''});
  ORDER.push(nm);
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
      <div class="card-desc">Priority-ordered HLS sources — first match wins at grab time. Built-in sources (kkphim, ophim, nguonc) are always available; custom sources can override or supplement them.</div></div>
    </div>
    <div class="card-body">
      <div id="src-list"></div>
      <div class="actions" style="margin:10px 0 0">
        <button type="button" class="btn btn-ghost" onclick="srcAddNew()">+ Add Custom Source</button>
      </div>
      <input type="hidden" name="hls_template_sources" id="hls-sources-json" value="{_attr(templates)}">
      <input type="hidden" name="source_order_json" id="source-order-json" value="">
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
