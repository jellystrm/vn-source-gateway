<template>
  <div>
    <div class="page-head">
      <div>
        <h1>Settings</h1>
        <p class="sub">Configure service connections and system behaviour.</p>
      </div>
    </div>

    <!-- Subnav -->
    <div class="subnav">
      <template v-for="s in sections" :key="s.id">
        <div v-if="s.id === 'sep'" class="subnav-sep"></div>
        <button v-else :class="{ active: active === s.id }" @click="setActive(s.id)">
          <!-- connection icons -->
          <svg v-if="s.icon === 'radarr'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2v20M2 12h20"/></svg>
          <svg v-else-if="s.icon === 'sonarr'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/></svg>
          <svg v-else-if="s.icon === 'jellyfin'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 3 21 18 3 18 12 3"/></svg>
          <svg v-else-if="s.icon === 'tmdb'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <!-- system icons -->
          <svg v-else-if="s.icon === 'schedule'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <svg v-else-if="s.icon === 'output'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <svg v-else-if="s.icon === 'indexer'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <svg v-else-if="s.icon === 'dlclient'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ s.label }}
        </button>
      </template>
    </div>

    <!-- ── Radarr ── -->
    <div v-if="active === 'radarr'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2v20M2 12h20"/></svg></div>
        <div><h3>Radarr</h3><p class="desc">Movie manager connection settings.</p></div>
        <div class="head-conn">
          <span :class="['dot', healthTiles.radarr.dotClass]"></span>
          <span class="head-conn-desc">
            <template v-if="healthTiles.radarr.status === 'loading'">checking…</template>
            <template v-else-if="healthTiles.radarr.status === 'ok'">reachable · {{ healthTiles.radarr.latency }}ms</template>
            <template v-else-if="healthTiles.radarr.status === 'error'">{{ healthTiles.radarr.message || 'unreachable' }}</template>
          </span>
        </div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <div class="field">
            <label>URL <span class="hint">required</span></label>
            <input class="input mono" v-model="cfg.radarr_url" placeholder="http://radarr:7878" />
          </div>
          <div class="field">
            <label>API Key <span class="hint">required</span></label>
            <input class="input mono" v-model="cfg.radarr_api_key" type="password" placeholder="••••••••••••••••" />
          </div>
          <div class="field full">
            <label>Movie .strm root <span class="hint">auto-detected from Radarr root folder</span></label>
            <input class="input mono" v-model="cfg.movie_strm_root" placeholder="/movies" />
            <p class="hint-text">Leave blank to auto-detect from Radarr root folder on each start.</p>
          </div>
        </div>
      </div>
      <div class="path-section">
        <div class="path-section-head">
          <span class="path-section-label">Output paths</span>
          <button class="btn ghost sm" :disabled="pathChecking" @click="testOutputPaths">{{ pathChecking ? 'Checking…' : 'Test paths' }}</button>
        </div>
        <div class="path-panel">
          <div v-if="!radarrPathRows.length" class="path-empty">Press "Test paths" to verify movie directories.</div>
          <div v-else class="path-grid">
            <div v-for="row in radarrPathRows" :key="row.key" class="path-row">
              <div><div class="path-label">{{ row.label }}</div><div class="path-owner">{{ row.owner }}</div></div>
              <code>{{ row.path }}</code>
            </div>
          </div>
          <div v-if="pathWarnings.length" class="path-warnings">
            <div v-for="w in pathWarnings" :key="w">⚠ {{ w }}</div>
          </div>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn ghost sm" @click="runSingle('radarr')" :disabled="healthTiles.radarr.status === 'loading'">Test connection</button>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Sonarr ── -->
    <div v-else-if="active === 'sonarr'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/></svg></div>
        <div><h3>Sonarr</h3><p class="desc">TV series manager connection settings.</p></div>
        <div class="head-conn">
          <span :class="['dot', healthTiles.sonarr.dotClass]"></span>
          <span class="head-conn-desc">
            <template v-if="healthTiles.sonarr.status === 'loading'">checking…</template>
            <template v-else-if="healthTiles.sonarr.status === 'ok'">reachable · {{ healthTiles.sonarr.latency }}ms</template>
            <template v-else-if="healthTiles.sonarr.status === 'error'">{{ healthTiles.sonarr.message || 'unreachable' }}</template>
          </span>
        </div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <div class="field">
            <label>URL <span class="hint">required</span></label>
            <input class="input mono" v-model="cfg.sonarr_url" placeholder="http://sonarr:8989" />
          </div>
          <div class="field">
            <label>API Key <span class="hint">required</span></label>
            <input class="input mono" v-model="cfg.sonarr_api_key" type="password" placeholder="••••••••••••••••" />
          </div>
          <div class="field full">
            <label>Series .strm root <span class="hint">auto-detected from Sonarr root folder</span></label>
            <input class="input mono" v-model="cfg.series_strm_root" placeholder="/series" />
            <p class="hint-text">Leave blank to auto-detect from Sonarr root folder on each start.</p>
          </div>
        </div>
      </div>
      <div class="path-section">
        <div class="path-section-head">
          <span class="path-section-label">Output paths</span>
          <button class="btn ghost sm" :disabled="pathChecking" @click="testOutputPaths">{{ pathChecking ? 'Checking…' : 'Test paths' }}</button>
        </div>
        <div class="path-panel">
          <div v-if="!sonarrPathRows.length" class="path-empty">Press "Test paths" to verify series directories.</div>
          <div v-else class="path-grid">
            <div v-for="row in sonarrPathRows" :key="row.key" class="path-row">
              <div><div class="path-label">{{ row.label }}</div><div class="path-owner">{{ row.owner }}</div></div>
              <code>{{ row.path }}</code>
            </div>
          </div>
          <div v-if="pathWarnings.length" class="path-warnings">
            <div v-for="w in pathWarnings" :key="w">⚠ {{ w }}</div>
          </div>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn ghost sm" @click="runSingle('sonarr')" :disabled="healthTiles.sonarr.status === 'loading'">Test connection</button>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Jellyfin ── -->
    <div v-else-if="active === 'jellyfin'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 3 21 18 3 18 12 3"/></svg></div>
        <div><h3>Jellyfin</h3><p class="desc">Library refresh + playback integration.</p></div>
        <div class="head-conn">
          <span :class="['dot', healthTiles.jellyfin.dotClass]"></span>
          <span class="head-conn-desc">
            <template v-if="healthTiles.jellyfin.status === 'loading'">checking…</template>
            <template v-else-if="healthTiles.jellyfin.status === 'ok'">reachable · {{ healthTiles.jellyfin.latency }}ms</template>
            <template v-else-if="healthTiles.jellyfin.status === 'error'">{{ healthTiles.jellyfin.message || 'unreachable' }}</template>
          </span>
        </div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <div class="field">
            <label>URL</label>
            <input class="input mono" v-model="cfg.jellyfin_url" placeholder="http://jellyfin:8096" />
          </div>
          <div class="field">
            <label>API Key</label>
            <input class="input mono" v-model="cfg.jellyfin_api_key" type="password" placeholder="••••••••••••••••" />
          </div>
          <div class="field full">
            <label class="check">
              <input type="checkbox" v-model="cfg.jellyfin_scan_after_strm" />
              <span class="check-box"></span>
              <span>Trigger library scan after .strm write</span>
            </label>
          </div>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn ghost sm" @click="runSingle('jellyfin')" :disabled="healthTiles.jellyfin.status === 'loading'">Test connection</button>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── TMDB ── -->
    <div v-else-if="active === 'tasks'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></div>
        <div><h3>TMDB</h3><p class="desc">API key for title and year resolution in source queries.</p></div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <div class="field full">
            <label>TMDB API Key <span class="hint">get free key at themoviedb.org</span></label>
            <input class="input mono" v-model="cfg.tmdb_api_key" type="password" placeholder="••••••••••••••••••••••••••••••••" style="max-width:420px" />
            <p class="hint-text">Required for title/year resolution. Free at <a href="https://www.themoviedb.org/settings/api" target="_blank">themoviedb.org</a>.</p>
          </div>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Schedule ── -->
    <div v-else-if="active === 'schedule'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
        <div><h3>Poll schedule</h3><p class="desc">Independent polling schedules for Radarr and Sonarr.</p></div>
      </div>
      <div class="fcard-body">
        <div class="sched-grid">

          <!-- Movies column -->
          <div class="sched-col" :class="{ 'sched-off': !cfg.movie_enabled }">
            <label class="check sched-toggle">
              <input type="checkbox" v-model="cfg.movie_enabled" />
              <span class="check-box"></span>
              <span>Movies <span class="muted">— Radarr</span></span>
            </label>
            <fieldset class="sched-fields" :disabled="!cfg.movie_enabled">
              <div class="sched-row">
                <label class="sched-label">Interval</label>
                <div style="display:flex;gap:0">
                  <input class="input mono" type="number" min="1"
                    :value="moviePollDisplay"
                    @input="setMoviePoll(($event.target as HTMLInputElement).valueAsNumber)"
                    style="border-top-right-radius:0;border-bottom-right-radius:0;border-right:0;width:72px" />
                  <select class="select" v-model="moviePollUnit"
                    style="border-top-left-radius:0;border-bottom-left-radius:0;width:110px">
                    <option value="minutes">minutes</option>
                    <option value="hours">hours</option>
                  </select>
                </div>
                <span class="sched-hint">every {{ moviePollSummary }}</span>
              </div>
              <div class="sched-row">
                <label class="sched-label">Max items</label>
                <input class="input mono" v-model.number="cfg.movie_max_items_per_poll" type="number" min="1" style="width:80px" />
                <span class="sched-hint">per poll</span>
              </div>
            </fieldset>
          </div>

          <div class="sched-divider"></div>

          <!-- Series column -->
          <div class="sched-col" :class="{ 'sched-off': !cfg.series_enabled }">
            <label class="check sched-toggle">
              <input type="checkbox" v-model="cfg.series_enabled" />
              <span class="check-box"></span>
              <span>Series <span class="muted">— Sonarr</span></span>
            </label>
            <fieldset class="sched-fields" :disabled="!cfg.series_enabled">
              <div class="sched-row">
                <label class="sched-label">Interval</label>
                <div style="display:flex;gap:0">
                  <input class="input mono" type="number" min="1"
                    :value="seriesPollDisplay"
                    @input="setSeriesPoll(($event.target as HTMLInputElement).valueAsNumber)"
                    style="border-top-right-radius:0;border-bottom-right-radius:0;border-right:0;width:72px" />
                  <select class="select" v-model="seriesPollUnit"
                    style="border-top-left-radius:0;border-bottom-left-radius:0;width:110px">
                    <option value="minutes">minutes</option>
                    <option value="hours">hours</option>
                  </select>
                </div>
                <span class="sched-hint">every {{ seriesPollSummary }}</span>
              </div>
              <div class="sched-row">
                <label class="sched-label">Max items</label>
                <input class="input mono" v-model.number="cfg.series_max_items_per_poll" type="number" min="1" style="width:80px" />
                <span class="sched-hint">per poll</span>
              </div>
            </fieldset>
          </div>

        </div>

        <!-- Auto-grab -->
        <div class="auto-grab-row">
          <div class="auto-grab-left">
            <label class="check">
              <input type="checkbox" v-model="cfg.auto_grab" />
              <span class="check-box"></span>
              <span>Auto-grab</span>
            </label>
            <p class="hint-text" style="margin:4px 0 0 28px">
              Khi *arr gửi search request, tự động chọn nguồn tốt nhất theo thứ tự
              <b style="color:var(--text-2)">Sources</b> và <b style="color:var(--text-2)">Variant priority</b>
              rồi tải luôn — không cần bấm thủ công trong Indexer.
            </p>
          </div>
          <span v-if="cfg.auto_grab" class="pill green flat" style="flex-shrink:0">Active</span>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Output ── (3 separate cards) -->
    <div v-else-if="active === 'output'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></div>
        <div><h3>Resolver</h3><p class="desc">Source priority and download type settings.</p></div>
      </div>
      <div class="fcard-body" style="display:flex;flex-direction:column;gap:20px">

        <!-- Row 1: Sources -->
        <div>
          <div class="resolver-row-label">Sources <span class="hint">· drag to reorder</span></div>
          <div class="resolver-src-row">
            <div
              v-for="(src, i) in srcOrder"
              :key="src"
              class="resolver-src-chip"
              :class="{ 'drag-over': srcDragOverIdx === i }"
              draggable="true"
              @dragstart="srcDragStart(i)"
              @dragover.prevent="srcDragOver(i)"
              @drop="srcDrop"
              @dragend="srcDragEnd"
            >
              <span class="resolver-drag-handle">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="9" cy="19" r="1" fill="currentColor"/><circle cx="15" cy="5" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="19" r="1" fill="currentColor"/></svg>
              </span>
              <span class="resolver-rank">{{ i + 1 }}</span>
              <div :class="['src-mark sm', SRC_COLORS[src] || '']">{{ SRC_INITIALS[src] || src.slice(0,2).toUpperCase() }}</div>
              <div class="resolver-src-meta">
                <div class="resolver-src-name">{{ src }}</div>
                <div class="resolver-src-url">{{ BUILTIN_URLS[src] || '' }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Variants -->
        <div>
          <div class="resolver-row-label">Variants <span class="hint">· drag to set dub preference</span></div>
          <div class="resolver-src-row">
            <div
              v-for="(vname, vi) in variantOrder"
              :key="vname"
              class="resolver-src-chip"
              :class="{ 'drag-over': varDragOverIdx === vi }"
              draggable="true"
              @dragstart="varDragStart(vi)"
              @dragover.prevent="varDragOver(vi)"
              @drop="varDrop"
              @dragend="varDragEnd"
            >
              <span class="resolver-drag-handle">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="9" cy="19" r="1" fill="currentColor"/><circle cx="15" cy="5" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="19" r="1" fill="currentColor"/></svg>
              </span>
              <span class="resolver-rank">{{ vi + 1 }}</span>
              <div class="resolver-src-meta">
                <div class="resolver-src-name">{{ vname }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Row 3: Download types -->
        <div>
          <div class="resolver-row-label">Download types <span class="hint">· drag to set priority · check to enable auto-grab</span></div>
          <div class="resolver-type-row">
            <div
              v-for="(te, ti) in srcTypes"
              :key="te.key"
              class="resolver-type-chip"
              :class="{ 'type-enabled': te.auto_download, 'drag-over': typeDragOverIdx === ti }"
              draggable="true"
              @dragstart="typeDragStart(ti)"
              @dragover.prevent="typeDragOver(ti)"
              @drop="typeDrop"
              @dragend="typeDragEnd"
            >
              <span class="resolver-drag-handle">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="9" cy="19" r="1" fill="currentColor"/><circle cx="15" cy="5" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="19" r="1" fill="currentColor"/></svg>
              </span>
              <span class="resolver-rank">{{ ti + 1 }}</span>
              <span class="type-badge" :class="te.key">{{ te.key === 'strm' ? 'STRM' : 'HLS-DL' }}</span>
              <label class="check type-check" style="flex:1" @click.stop>
                <input type="checkbox" v-model="te.auto_download" />
                <span class="check-box"></span>
                <span class="check-lbl">Auto download</span>
              </label>
            </div>
          </div>
        </div>

      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Indexer ── -->
    <div v-else-if="active === 'indexer'" class="fcard">
      <div class="fcard-head">
        <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
        <div><h3>Torznab Indexer</h3><p class="desc">Configure the Torznab API — paste the key into Radarr / Sonarr → Indexers.</p></div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <div class="field full">
            <label>API Key</label>
            <div class="key-row">
              <input class="input mono key-input" :value="cfg.torznab_api_key" readonly />
              <button class="icon-btn" :class="{ copied: keyCopied }" title="Copy key" @click="copyKey">
                <svg v-if="!keyCopied" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
              <button class="icon-btn danger" title="Regenerate key" :disabled="keyRegen" @click="regenKey">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              </button>
            </div>
            <p v-if="keyRegenDone" class="hint-text" style="color:var(--amber)">⚠ Requires restart to take effect — update the key in Radarr / Sonarr → Indexers.</p>
            <p v-else class="hint-text">Paste into Radarr / Sonarr → Settings → Indexers → Torznab.</p>
          </div>
          <div class="field">
            <label>Public Base URL</label>
            <input class="input mono" v-model="cfg.public_base_url" placeholder="http://deceptarr:8765" />
          </div>
        </div>
      </div>
      <div class="fcard-foot">
        <span v-if="saved"     class="save-ok">✓ Saved</span>
        <span v-if="saveError" class="save-err">{{ saveError }}</span>
        <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </div>

    <!-- ── Download Client ── -->
    <template v-else-if="active === 'dlclient'">

      <!-- qBittorrent card -->
      <div class="fcard">
        <div class="fcard-head">
          <div class="fcard-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></div>
          <div><h3>qBittorrent</h3><p class="desc">Connection, paths, and queue behaviour.</p></div>
        </div>
        <div class="fcard-body">
          <div class="form">
            <div class="field">
              <label>UI Host</label>
              <input class="input mono" v-model="cfg.ui_host" />
            </div>
            <div class="field">
              <label>UI Port</label>
              <input class="input mono" v-model.number="cfg.ui_port" type="number" />
            </div>
            <div class="field">
              <label>Username</label>
              <input class="input" v-model="cfg.qb_username" />
            </div>
            <div class="field">
              <label>Password</label>
              <input class="input" v-model="cfg.qb_password" type="password" />
            </div>
            <div class="field full">
              <label>Download Root</label>
              <input class="input mono" v-model="cfg.download_root" placeholder="/downloads" />
              <p class="hint-text">Where downloaded files are stored. Leave blank to auto-detect from qBittorrent on start.</p>
            </div>
            <div class="field">
              <label>Retry failed jobs after <span class="hint">seconds</span></label>
              <input class="input mono" v-model.number="cfg.retry_after_seconds" type="number" min="0" />
            </div>
            <div class="field">
              <label>Job retention <span class="hint">hours</span></label>
              <input class="input mono" v-model.number="cfg.job_detail_retention_hours" type="number" min="1" />
            </div>
          </div>
        </div>
        <div class="fcard-foot">
          <span v-if="saved"     class="save-ok">✓ Saved</span>
          <span v-if="saveError" class="save-err">{{ saveError }}</span>
          <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>

      <!-- HLS Download card -->
      <div class="fcard" style="margin-top:16px">
        <div class="fcard-head">
          <div class="fcard-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h18M3 12h18M3 17h12"/></svg>
          </div>
          <div><h3>HLS Download</h3><p class="desc">Container format, import mode, and ffmpeg settings.</p></div>
        </div>
        <div class="fcard-body" style="display:flex;flex-direction:column;gap:20px">
          <div class="form" style="margin:0">
            <div class="field">
              <label>Container</label>
              <select class="select" v-model="cfg.download_container">
                <option value="mkv">mkv</option>
                <option value="mp4">mp4</option>
                <option value="ts">ts (raw, no remux)</option>
              </select>
            </div>
            <div class="field">
              <label>Import mode <span class="hint">*arr → library</span></label>
              <select class="select" v-model="cfg.import_mode">
                <option value="Move">Move</option>
                <option value="Copy">Copy</option>
                <option value="Hardlink">Hardlink</option>
              </select>
              <p class="hint-text">How *arr moves the downloaded file into your library.</p>
            </div>
          </div>
          <div>
            <div class="out-section-label" style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
              ffmpeg
              <span v-if="ffmpegChecking" class="ff-badge ff-checking">checking…</span>
              <span v-else-if="ffmpegStatus?.ok" class="ff-badge ff-ok">✓ {{ ffmpegStatus.version?.split(' ').slice(0,3).join(' ') }}</span>
              <span v-else-if="ffmpegStatus" class="ff-badge ff-err">✗ not found</span>
            </div>
            <div class="form" style="margin:0">
              <div class="field">
                <label>Binary path</label>
                <input class="input mono" v-model="cfg.ffmpeg_path" placeholder="ffmpeg"
                  @change="recheckFfmpeg" @blur="recheckFfmpeg" />
                <p v-if="ffmpegStatus && !ffmpegStatus.ok" class="hint-text" style="color:var(--red)">{{ ffmpegStatus.hint }}</p>
                <p v-else class="hint-text">Leave blank to use <code>ffmpeg</code> from PATH.</p>
              </div>
              <div class="field">
                <label>Extra args <span class="hint">comma-separated</span></label>
                <input class="input mono" v-model="ffmpegArgs" placeholder="-c:v copy, -c:a aac" />
              </div>
            </div>
          </div>
        </div>
        <div class="fcard-foot">
          <span v-if="saved"     class="save-ok">✓ Saved</span>
          <span v-if="saveError" class="save-err">{{ saveError }}</span>
          <button class="btn primary" @click="save" :disabled="saving || !isDirty">{{ saving ? 'Saving…' : 'Save' }}</button>
        </div>
      </div>

    </template>

  </div>

  <!-- Unsaved changes confirm modal -->
  <teleport to="body">
    <div v-if="confirmVisible" class="confirm-overlay" @click.self="confirmStay">
      <div class="confirm-box">
        <div class="confirm-icon" style="color:var(--amber)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        </div>
        <div class="confirm-body">
          <p class="confirm-title">Unsaved changes</p>
          <p class="confirm-msg">{{ confirmMsg }}</p>
        </div>
        <div class="confirm-actions">
          <button class="btn ghost sm" @click="confirmStay">Stay</button>
          <button class="btn sm" @click="confirmDiscard">Discard</button>
          <button class="btn primary sm" @click="confirmDoSave">Save &amp; continue</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { getConfig, saveSettings, checkFfmpeg, getHealth, checkOutputPaths, type FfmpegCheckResult, type HealthResult } from '../api'

// ── Resolver constants ────────────────────────────────────────────────────────
type SrcTypeKey = 'strm' | 'hls_dl'
interface SrcTypeEntry { key: SrcTypeKey; auto_download: boolean }

const BUILTINS     = ['kkphim', 'ophim', 'nguonc']
const BUILTIN_URLS: Record<string, string> = {
  kkphim: 'https://phimapi.com', ophim: 'https://ophim1.com', nguonc: 'https://phim.nguonc.com',
}
const SRC_COLORS:   Record<string, string> = { kkphim: 'teal', ophim: 'blue', nguonc: 'purple' }
const SRC_INITIALS: Record<string, string> = { kkphim: 'KK',   ophim: 'OP',   nguonc: 'NC' }

const sectionBackendId: Record<string, string> = {
  tasks:    'tasks',
  output:   'runtime',
  dlclient: 'downloader',
  schedule: 'schedule',
}

// Fields that belong to each settings section (for per-section dirty tracking)
const SECTION_FIELDS: Record<string, string[]> = {
  radarr:   ['radarr_url', 'radarr_api_key', 'movie_enabled', 'movie_strm_root'],
  sonarr:   ['sonarr_url', 'sonarr_api_key', 'series_enabled', 'series_strm_root'],
  jellyfin: ['jellyfin_url', 'jellyfin_api_key', 'jellyfin_scan_after_strm'],
  tasks:    ['tmdb_api_key'],
  schedule: ['movie_enabled', 'movie_poll_interval_seconds', 'movie_max_items_per_poll',
             'series_enabled', 'series_poll_interval_seconds', 'series_max_items_per_poll', 'auto_grab'],
  output:   [],
  indexer:  ['public_base_url'],
  dlclient: ['ui_host', 'ui_port', 'qb_username', 'qb_password', 'download_root',
             'retry_after_seconds', 'job_detail_retention_hours',
             'download_container', 'import_mode', 'ffmpeg_path', 'ffmpeg_extra_args'],
}

const sections = [
  // System
  { id: 'indexer',  label: 'Indexer',         icon: 'indexer'  },
  { id: 'dlclient', label: 'Download Client', icon: 'dlclient' },
  { id: 'output',   label: 'Resolver',        icon: 'output'   },
  { id: 'schedule', label: 'Schedule',        icon: 'schedule' },
  // separator
  { id: 'sep',      label: '',                icon: ''         },
  // Connections
  { id: 'radarr',   label: 'Radarr',          icon: 'radarr'   },
  { id: 'sonarr',   label: 'Sonarr',          icon: 'sonarr'   },
  { id: 'jellyfin', label: 'Jellyfin',        icon: 'jellyfin' },
  { id: 'tasks',    label: 'TMDB',            icon: 'tmdb'     },
]

const SETTINGS_TAB_KEY = 'deceptarr:settings:tab'
const _firstTab = sections.find(s => s.id !== 'sep')?.id ?? 'indexer'
const _savedTab = localStorage.getItem(SETTINGS_TAB_KEY)
const active = ref(sections.some(s => s.id === _savedTab) ? _savedTab! : _firstTab)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const cfg         = ref<Record<string, any>>({})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const originalCfg = ref<Record<string, any>>({})
const saving    = ref(false)
const saved     = ref(false)
const saveError = ref('')

// ── Resolver state ────────────────────────────────────────────────────────────
const DEFAULT_VARIANTS = ['Vietsub', 'Lồng tiếng', 'Thuyết minh']

const srcOrder       = ref<string[]>([])
const variantOrder   = ref<string[]>([...DEFAULT_VARIANTS])
const srcTypes       = ref<SrcTypeEntry[]>([
  { key: 'strm',   auto_download: false },
  { key: 'hls_dl', auto_download: false },
])
const srcOriginal = ref('')

function srcSnapshot() {
  return JSON.stringify({ order: srcOrder.value, variants: variantOrder.value, types: srcTypes.value })
}
const srcIsDirty = computed(() => srcSnapshot() !== srcOriginal.value)

let srcDragIdx = -1
const srcDragOverIdx = ref(-1)
function srcDragStart(i: number) { srcDragIdx = i }
function srcDragOver(i: number)  { srcDragOverIdx.value = i }
function srcDrop() {
  if (srcDragIdx < 0 || srcDragIdx === srcDragOverIdx.value) { srcDragEnd(); return }
  const arr = [...srcOrder.value]; const [item] = arr.splice(srcDragIdx, 1)
  arr.splice(srcDragOverIdx.value, 0, item); srcOrder.value = arr; srcDragEnd()
}
function srcDragEnd() { srcDragIdx = -1; srcDragOverIdx.value = -1 }
function srcMoveUp(i: number) {
  if (i === 0) return; const arr = [...srcOrder.value];
  [arr[i-1], arr[i]] = [arr[i], arr[i-1]]; srcOrder.value = arr
}
function srcMoveDown(i: number) {
  if (i >= srcOrder.value.length - 1) return; const arr = [...srcOrder.value];
  [arr[i], arr[i+1]] = [arr[i+1], arr[i]]; srcOrder.value = arr
}
function srcTypeMoveUp(ti: number) {
  if (ti === 0) return; const arr = [...srcTypes.value];
  [arr[ti-1], arr[ti]] = [arr[ti], arr[ti-1]]; srcTypes.value = arr
}
function srcTypeMoveDown(ti: number) {
  if (ti >= srcTypes.value.length - 1) return; const arr = [...srcTypes.value];
  [arr[ti], arr[ti+1]] = [arr[ti+1], arr[ti]]; srcTypes.value = arr
}
// variant drag
let varDragIdx = -1
const varDragOverIdx = ref(-1)
function varDragStart(i: number) { varDragIdx = i }
function varDragOver(i: number)  { varDragOverIdx.value = i }
function varDrop() {
  if (varDragIdx < 0 || varDragIdx === varDragOverIdx.value) { varDragEnd(); return }
  const arr = [...variantOrder.value]; const [item] = arr.splice(varDragIdx, 1)
  arr.splice(varDragOverIdx.value, 0, item); variantOrder.value = arr; varDragEnd()
}
function varDragEnd() { varDragIdx = -1; varDragOverIdx.value = -1 }

// type drag
let typeDragIdx = -1
const typeDragOverIdx = ref(-1)
function typeDragStart(i: number) { typeDragIdx = i }
function typeDragOver(i: number)  { typeDragOverIdx.value = i }
function typeDrop() {
  if (typeDragIdx < 0 || typeDragIdx === typeDragOverIdx.value) { typeDragEnd(); return }
  const arr = [...srcTypes.value]; const [item] = arr.splice(typeDragIdx, 1)
  arr.splice(typeDragOverIdx.value, 0, item); srcTypes.value = arr; typeDragEnd()
}
function typeDragEnd() { typeDragIdx = -1; typeDragOverIdx.value = -1 }

function loadSources(loaded: Record<string, unknown>) {
  // Source order
  const savedOrder = [...((loaded.source_order as string[] | undefined) || [])].filter(n => BUILTINS.includes(n))
  srcOrder.value = [...savedOrder, ...BUILTINS.filter(b => !savedOrder.includes(b))]

  // Variant order
  const rawVariants = (loaded.variant_order as string[] | undefined) || [...DEFAULT_VARIANTS]
  const vOrdered = rawVariants.filter(v => v.trim())
  for (const v of DEFAULT_VARIANTS) { if (!vOrdered.includes(v)) vOrdered.push(v) }
  variantOrder.value = vOrdered

  // Type order + auto_download
  const rawTypeOrder = (loaded.type_order as string[] | undefined) || ['strm', 'hls_dl']
  const strmAuto = Boolean(loaded.strm_auto_download)
  const hlsAuto  = Boolean(loaded.hls_dl_auto_download)
  const autoMap: Record<string, boolean> = { strm: strmAuto, hls_dl: hlsAuto }
  const validKeys: SrcTypeKey[] = ['strm', 'hls_dl']
  const ordered = rawTypeOrder.filter((k): k is SrcTypeKey => validKeys.includes(k as SrcTypeKey))
  for (const k of validKeys) { if (!ordered.includes(k)) ordered.push(k) }
  srcTypes.value = ordered.map(k => ({ key: k, auto_download: autoMap[k] ?? false }))

  srcOriginal.value = srcSnapshot()
}

// ── Dirty tracking ────────────────────────────────────────────────────────────
function sectionSnapshot(section: string) {
  const fields = SECTION_FIELDS[section] || []
  return JSON.stringify(Object.fromEntries(fields.map(f => [f, originalCfg.value[f]])))
}
function sectionCurrent(section: string) {
  const fields = SECTION_FIELDS[section] || []
  return JSON.stringify(Object.fromEntries(fields.map(f => [f, cfg.value[f]])))
}
const isDirty = computed(() => {
  const dirty = sectionCurrent(active.value) !== sectionSnapshot(active.value)
  return active.value === 'output' ? dirty || srcIsDirty.value : dirty
})

// ── Unsaved-changes confirm modal ─────────────────────────────────────────────
const confirmVisible = ref(false)
const confirmMsg     = ref('')
let   _pendingAction: (() => void) | null = null
let   _pendingNavNext: ((v?: boolean | string) => void) | null = null

function _showConfirm(msg: string, onConfirm: () => void) {
  confirmMsg.value    = msg
  _pendingAction      = onConfirm
  confirmVisible.value = true
}
function confirmStay() {
  confirmVisible.value = false
  _pendingNavNext?.(false)
  _pendingNavNext = null
  _pendingAction  = null
}
async function confirmDoSave() {
  confirmVisible.value = false
  await save()
  const act = _pendingAction
  _pendingAction = null
  _pendingNavNext?.()
  _pendingNavNext = null
  act?.()
}
function confirmDiscard() {
  const fields = SECTION_FIELDS[active.value] || []
  for (const f of fields) cfg.value[f] = JSON.parse(JSON.stringify(originalCfg.value[f] ?? null))
  if (active.value === 'output') loadSources(originalCfg.value)
  confirmVisible.value = false
  const act = _pendingAction
  _pendingAction = null
  _pendingNavNext?.()
  _pendingNavNext = null
  act?.()
}

// ── Tab switching with dirty check ────────────────────────────────────────────
function setActive(id: string) {
  if (id === active.value || id === 'sep') return
  if (!isDirty.value) { active.value = id; localStorage.setItem(SETTINGS_TAB_KEY, id); return }
  _showConfirm(
    `Unsaved changes in ${sections.find(s => s.id === active.value)?.label ?? active.value}.`,
    () => { active.value = id; localStorage.setItem(SETTINGS_TAB_KEY, id) },
  )
}

// ── Route leave guard ─────────────────────────────────────────────────────────
onBeforeRouteLeave((_, __, next) => {
  if (!isDirty.value) { next(); return }
  _pendingNavNext = next
  _showConfirm(
    `Unsaved changes in ${sections.find(s => s.id === active.value)?.label ?? active.value}.`,
    () => {},
  )
})
const keyCopied     = ref(false)
const keyRegen      = ref(false)
const keyRegenDone  = ref(false)
const ffmpegStatus  = ref<FfmpegCheckResult | null>(null)
const ffmpegChecking = ref(false)

async function recheckFfmpeg() {
  ffmpegChecking.value = true
  try {
    ffmpegStatus.value = await checkFfmpeg(cfg.value.ffmpeg_path || '')
  } catch { ffmpegStatus.value = null }
  finally { ffmpegChecking.value = false }
}

// ── Poll interval helpers ─────────────────────────────────────────────────────
type PollUnit = 'minutes' | 'hours'

const moviePollUnit  = ref<PollUnit>('minutes')
const seriesPollUnit = ref<PollUnit>('hours')

function secsToDisplay(secs: number, unit: PollUnit) {
  return unit === 'hours' ? Math.round(secs / 3600) : Math.round(secs / 60)
}
function displayToSecs(v: number, unit: PollUnit) {
  return unit === 'hours' ? v * 3600 : v * 60
}
function secsSummary(secs: number) {
  if (secs < 3600) return `${Math.round(secs / 60)} min`
  if (secs % 3600 === 0) return `${secs / 3600}h`
  return `${Math.round(secs / 60)} min`
}

const moviePollDisplay = computed(() =>
  secsToDisplay(cfg.value.movie_poll_interval_seconds || 300, moviePollUnit.value))
const seriesPollDisplay = computed(() =>
  secsToDisplay(cfg.value.series_poll_interval_seconds || 3600, seriesPollUnit.value))

function setMoviePoll(v: number) {
  if (!Number.isFinite(v) || v < 1) return
  cfg.value.movie_poll_interval_seconds = displayToSecs(v, moviePollUnit.value)
}
function setSeriesPoll(v: number) {
  if (!Number.isFinite(v) || v < 1) return
  cfg.value.series_poll_interval_seconds = displayToSecs(v, seriesPollUnit.value)
}

const moviePollSummary  = computed(() => secsSummary(cfg.value.movie_poll_interval_seconds  || 300))
const seriesPollSummary = computed(() => secsSummary(cfg.value.series_poll_interval_seconds || 3600))

// ── ffmpeg args ───────────────────────────────────────────────────────────────
const ffmpegArgs = computed({
  get: () => ((cfg.value.ffmpeg_extra_args as string[]) || []).join(', '),
  set: (v: string) => { cfg.value.ffmpeg_extra_args = v.split(',').map((s: string) => s.trim()).filter(Boolean) },
})

// ── Actions ───────────────────────────────────────────────────────────────────
async function copyKey() {
  try {
    await navigator.clipboard.writeText(String(cfg.value.torznab_api_key || ''))
    keyCopied.value = true
    setTimeout(() => { keyCopied.value = false }, 1800)
  } catch {}
}

async function regenKey() {
  keyRegen.value = true
  keyRegenDone.value = false
  try {
    const res = await fetch('/api/regen-torznab-key', { method: 'POST' })
    const data = await res.json()
    cfg.value.torznab_api_key = data.torznab_api_key
    keyRegenDone.value = true
  } catch {}
  finally { keyRegen.value = false }
}

async function save() {
  saving.value = true
  saveError.value = ''
  saved.value = false
  try {
    const backendSection = sectionBackendId[active.value] || active.value
    const payload: Record<string, unknown> = { _section: backendSection, ...cfg.value }
    await saveSettings(payload)
    const fields = SECTION_FIELDS[active.value] || []
    for (const f of fields) originalCfg.value[f] = JSON.parse(JSON.stringify(cfg.value[f] ?? null))
    // Also save resolver config when in output section
    if (active.value === 'output') {
      const strmEntry   = srcTypes.value.find(t => t.key === 'strm')
      const hlsEntry    = srcTypes.value.find(t => t.key === 'hls_dl')
      const typePayload: Record<string, unknown> = {
        _section: 'sources',
        source_order_json:  JSON.stringify(srcOrder.value),
        variant_order_json: JSON.stringify(variantOrder.value),
        type_order_json:    JSON.stringify(srcTypes.value.map(t => t.key)),
      }
      if (strmEntry?.auto_download)  typePayload.strm_auto_download  = '1'
      if (hlsEntry?.auto_download)   typePayload.hls_dl_auto_download = '1'
      await saveSettings(typePayload)
      srcOriginal.value = srcSnapshot()
    }
    saved.value = true
    setTimeout(() => { saved.value = false }, 2500)
  } catch (e: unknown) {
    saveError.value = String(e)
  } finally {
    saving.value = false
  }
}

// ── Health check ─────────────────────────────────────────────────────────────
interface HealthTile {
  name: string; status: 'idle'|'loading'|'ok'|'warn'|'error'|'unknown'
  dotClass: string; latency: number|null; message: string; url: string
}
const ALL_SERVICES = ['radarr','sonarr','jellyfin','kkphim','ophim','nguonc']
const healthTiles = reactive<Record<string, HealthTile>>(
  Object.fromEntries(ALL_SERVICES.map(n => [n, { name: n, status: 'idle', dotClass: 'gray', latency: null, message: '', url: '' }]))
)
const healthRunning = ref(false)

function applyTile(name: string, r: HealthResult) {
  const t = healthTiles[name]; if (!t) return
  t.url = r.url || ''; t.latency = r.latency; t.message = r.message || ''; t.status = r.status
  t.dotClass = r.status === 'ok' ? 'green' : r.status === 'warn' ? 'amber' : r.status === 'error' ? 'red' : 'gray'
}
async function runHealth() {
  if (healthRunning.value) return
  healthRunning.value = true
  ALL_SERVICES.forEach(n => { healthTiles[n].status = 'loading'; healthTiles[n].dotClass = 'gray' })
  try { const res = await getHealth(); for (const [k, v] of Object.entries(res)) applyTile(k, v) }
  catch {}
  finally { healthRunning.value = false }
}
async function runSingle(name: string) {
  const t = healthTiles[name]; if (!t) return
  t.status = 'loading'; t.dotClass = 'gray'
  try { const res = await getHealth(); if (res[name]) applyTile(name, res[name]) }
  catch { t.status = 'error'; t.dotClass = 'red' }
}

// ── Output paths (per-tab) ────────────────────────────────────────────────────
type PathRow = { key: string; label: string; owner: string; path: string }
const pathChecking  = ref(false)
const allPathRows   = ref<PathRow[]>([])
const pathWarnings  = ref<string[]>([])

const radarrPathRows  = computed(() => allPathRows.value.filter(r => r.key.startsWith('movie')))
const sonarrPathRows  = computed(() => allPathRows.value.filter(r => r.key.startsWith('series')))

async function testOutputPaths() {
  if (pathChecking.value) return
  pathChecking.value = true
  try {
    const result = await checkOutputPaths()
    allPathRows.value  = result.paths
    pathWarnings.value = result.warnings || []
  } catch {}
  finally { pathChecking.value = false }
}

onMounted(async () => {
  try {
    const loaded = await getConfig() as Record<string, any>
    cfg.value         = loaded
    originalCfg.value = JSON.parse(JSON.stringify(loaded))
    loadSources(loaded)
    const ms = cfg.value.movie_poll_interval_seconds  || 300
    const ss = cfg.value.series_poll_interval_seconds || 3600
    moviePollUnit.value  = ms  >= 3600 && ms  % 3600 === 0 ? 'hours' : 'minutes'
    seriesPollUnit.value = ss  >= 3600 && ss  % 3600 === 0 ? 'hours' : 'minutes'
    recheckFfmpeg()
    runHealth()
  } catch {}
})
</script>

<style scoped>
.subnav-sep {
  width: 1px; height: 20px; background: var(--border);
  margin: 0 4px; align-self: center; flex-shrink: 0;
}
/* ── API key row ── */
.key-row {
  display: flex; gap: 0; max-width: 520px;
}
.key-input {
  flex: 1; border-top-right-radius: 0; border-bottom-right-radius: 0;
  cursor: default; font-size: 13px;
}
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; flex-shrink: 0;
  background: var(--surface-2); border: 1px solid var(--border);
  border-left: 0; color: var(--text-2);
  cursor: pointer; transition: background .12s, color .12s;
}
.key-row .icon-btn                { border-radius: 0; }
.key-row .icon-btn:last-of-type   { border-radius: 0 8px 8px 0; }
.icon-btn:hover { background: var(--surface-3); color: var(--text); }
.icon-btn.copied { color: var(--teal); }
.icon-btn.danger { color: var(--red-muted, var(--text-3)); }
.icon-btn.danger:hover { background: var(--red-soft); color: var(--red); }
.icon-btn:disabled { opacity: .4; cursor: default; pointer-events: none; }

/* ── Global input max-width in settings forms ── */
.fcard-body .input:not(.key-input),
.fcard-body .select { max-width: 480px; }
.fcard-body .input-group { max-width: 480px; }

.key-copied { color: var(--green) !important; border-color: rgba(74,222,128,.3) !important; }
.save-ok  { font-size: 12px; color: var(--green); }
.save-err { font-size: 12px; color: var(--red); }

/* ── Schedule 2-column layout ── */
.sched-grid {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  gap: 0 28px;
}
.sched-col { display: flex; flex-direction: column; gap: 0; }
.sched-divider { background: var(--border); }

.sched-toggle { font-size: 14px; font-weight: 600; padding-bottom: 14px; border-bottom: 1px solid var(--border); margin-bottom: 14px; }
.muted { color: var(--text-3); font-weight: 400; }

.sched-fields {
  border: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 10px;
  transition: opacity .15s;
}
.sched-fields:disabled { opacity: .38; pointer-events: none; }

.sched-row { display: flex; align-items: center; gap: 10px; }
.sched-label { font-size: 12.5px; color: var(--text-3); width: 72px; flex-shrink: 0; white-space: nowrap; }
.sched-hint  { font-size: 11.5px; color: var(--text-3); }

.sched-off .sched-toggle { opacity: .7; }

/* ── Auto-grab row ── */
.auto-grab-row {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border);
}
.auto-grab-left { flex: 1; }

/* ── Output type selector ── */
.out-type-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.out-type-card {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 14px 16px; border-radius: 10px;
  border: 1.5px solid var(--border); background: var(--bg);
  cursor: pointer; transition: border-color .12s, background .12s;
}
.out-type-card:hover { border-color: var(--border-strong); }
.out-type-card.active { border-color: var(--teal); background: var(--teal-soft); }
.out-type-radio { flex-shrink: 0; margin-top: 2px; }
.radio-dot {
  width: 16px; height: 16px; border-radius: 50%;
  border: 1.5px solid var(--border-strong); display: block;
  transition: all .12s;
}
.radio-dot.on { border-color: var(--teal); border-width: 5px; background: var(--bg); }
.out-type-name { font-size: 13.5px; font-weight: 600; color: var(--text-2); margin-bottom: 4px; }
.out-type-desc { font-size: 12px; color: var(--text-3); line-height: 1.5; }

.out-info {
  display: flex; gap: 8px; align-items: flex-start;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 14px;
  font-size: 12.5px; color: var(--text-3); line-height: 1.5;
}
.out-info svg { flex-shrink: 0; margin-top: 2px; color: var(--text-3); }
.out-section-label {
  font-size: 11.5px; font-weight: 600; color: var(--text-3);
  text-transform: uppercase; letter-spacing: .06em;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}

/* ── ffmpeg status badge ── */
.ff-badge {
  font-size: 11px; font-weight: 500; padding: 2px 8px;
  border-radius: 5px; font-family: var(--font-mono);
}
.ff-checking { background: var(--surface-2); color: var(--text-3); }
.ff-ok  { background: var(--teal-soft);   color: var(--teal);   border: 1px solid var(--teal-line); }
.ff-err { background: var(--red-soft);    color: var(--red);    border: 1px solid var(--red-line); }

/* ── Connection status in fcard-head ── */
.head-conn {
  display: flex; align-items: center; gap: 7px;
  margin-left: auto; flex-shrink: 0;
}
.head-conn-desc { font-size: 12px; color: var(--text-3); }

/* ── Output paths panel ── */
.path-panel {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px;
}
.path-empty { color: var(--text-3); font-size: 13px; }
.path-grid  { display: grid; gap: 6px; }
.path-row {
  display: grid; grid-template-columns: minmax(130px, 200px) minmax(0, 1fr);
  gap: 12px; align-items: center;
  padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px;
}
.path-label { font-size: 13px; font-weight: 600; color: var(--text); }
.path-owner { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.path-row code { font-family: var(--font-mono); font-size: 12px; color: var(--text-2); overflow-wrap: anywhere; }
.path-warnings { margin-top: 8px; display: grid; gap: 3px; font-size: 12px; color: var(--amber, #f5a623); }

.path-section {
  border-top: 1px solid var(--border);
  padding: 14px 20px;
}
.path-section-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.path-section-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-3);
}

.src-health-inline {
  font-size: 11px; color: var(--text-3); font-family: var(--font-mono);
}

/* ── Unsaved changes modal (teleported, not scoped) ── */

/* ── Resolver tab ── */
.icon-mini.xs { width: 20px; height: 20px; }
.resolver-row-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-3); margin-bottom: 10px;
}
.resolver-src-row {
  display: flex; gap: 10px; flex-wrap: wrap;
}
.resolver-drag-handle {
  color: var(--text-3); flex-shrink: 0; cursor: grab; display: flex; align-items: center;
}
.resolver-drag-handle:active { cursor: grabbing; }
.resolver-src-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; min-width: 180px;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 10px; cursor: grab; transition: border-color .12s;
}
.resolver-src-chip:active { cursor: grabbing; }
.resolver-src-chip.drag-over { border-color: var(--teal); box-shadow: 0 0 0 2px rgba(94,224,189,.15); }
.resolver-rank {
  font-family: var(--font-mono); font-size: 10px; color: var(--text-3);
  width: 14px; text-align: center; flex-shrink: 0;
}
.src-mark.sm { width: 32px; height: 32px; font-size: 11px; }
.resolver-src-meta { flex: 1; min-width: 0; }
.resolver-src-name { font-weight: 600; font-size: 13px; }
.resolver-src-url  { font-family: var(--font-mono); font-size: 11px; color: var(--text-3); margin-top: 2px; }

.resolver-type-row {
  display: flex; gap: 10px; flex-wrap: wrap;
}
.resolver-type-chip {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px; min-width: 220px;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 10px; transition: background .1s, border-color .1s;
}
.resolver-type-chip.type-enabled {
  background: rgba(94,224,189,.04); border-color: rgba(94,224,189,.2);
}
.type-badge {
  display: inline-block; flex-shrink: 0; width: 56px; text-align: center;
  padding: 2px 0; border-radius: 5px;
  font: 600 10.5px/1.4 var(--font-mono); letter-spacing: .04em; white-space: nowrap;
}
.type-badge.strm   { background: rgba(94,224,189,.12); color: var(--teal); }
.type-badge.hls_dl { background: rgba(245,166,35,.12);  color: var(--accent); }
.type-check { display: flex; align-items: center; gap: 6px; cursor: pointer; }
.check-lbl  { font-size: 12px; color: var(--text); }
</style>

