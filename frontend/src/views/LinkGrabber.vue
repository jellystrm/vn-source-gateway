<template>
  <div>
    <div class="page-head">
      <div>
        <h1>Indexer</h1>
        <p class="sub">Recent indexer activity grouped by media, season, episode, and source.</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn" @click="load">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar" style="margin-bottom:18px">
      <div class="group">
        <span
          v-for="f in filters" :key="f.key"
          :class="['filter-chip', { active: activeFilter === f.key }]"
          @click="activeFilter = f.key"
        >
          {{ f.label }}
          <span :class="['n', f.countClass]">{{ f.count }}</span>
        </span>
      </div>
      <div class="divider"></div>
      <span class="spacer"></span>
      <button class="btn ghost sm" :disabled="!displayGroups.length" @click="toggleAllPkgs">
        <svg v-if="allPkgsCollapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 11 12 6 17 11"/><polyline points="7 18 12 13 17 18"/></svg>
        {{ allPkgsCollapsed ? 'Expand all' : 'Collapse all' }}
      </button>
      <button class="btn ghost sm" :disabled="!filteredEvents.length" @click="clearFiltered">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
        Clear {{ activeFilter === 'all' ? 'all' : activeFilter === 'nomatch' ? 'no-match' : 'matched' }}
      </button>
    </div>

    <div v-if="!displayGroups.length" class="empty-state">
      <template v-if="!allSearchEvents.length">
        <h3>No activity yet</h3>
        <p>Start the worker or let Radarr / Sonarr hand queries off automatically once configured.</p>
      </template>
      <template v-else-if="activeFilter === 'matched'">
        <h3>No matched grabs</h3>
        <p>Searches have come in but none returned grab options. Check the <b style="color:var(--text-2)">No match</b> filter to see what queries failed.</p>
      </template>
      <template v-else-if="activeFilter === 'nomatch'">
        <h3>No failed searches</h3>
        <p>All queries returned results.</p>
      </template>
      <template v-else>
        <h3>No activity yet</h3>
        <p>Start the worker or let Radarr / Sonarr hand queries off automatically once configured.</p>
      </template>
    </div>

    <div v-else class="pkg-list">
      <div
        v-for="group in displayGroups"
        :key="group.key"
        class="pkg"
        :class="{ collapsed: collapsedPkgs.has(group.key) || group.linkCount === 0 }"
      >
        <!-- Package head -->
        <div class="pkg-head" @click="togglePkg(group.key)">
          <div :class="['pkg-mark', group.kind === 'movie' ? 'movie' : 'tv']">
            {{ group.kind === 'movie' ? 'M' : 'TV' }}
          </div>
          <div class="pkg-title-block">
            <div class="pkg-title">
              {{ group.title }}
              <span v-if="group.tmdbId" class="id">tmdb {{ group.tmdbId }}</span>
            </div>
            <div class="pkg-sub">{{ pkgSub(group) }}</div>
          </div>
          <div class="pkg-right">
            <template v-if="group.linkCount > 0">
              <span>{{ group.linkCount }} links</span>
              <span class="pill green">matched</span>
            </template>
            <span v-else class="pill red">no match</span>
            <span class="time">{{ relTime(group.ts) }}</span>
            <button class="row-action danger" title="Delete" @click.stop="deleteGroup(group)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
            <button class="icon-mini" :title="collapsedPkgs.has(group.key) ? 'Expand' : 'Collapse'" @click.stop="togglePkg(group.key)">
              <svg class="pkg-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Color strip -->
        <div :class="['pkg-bar', group.linkCount > 0 ? 'teal' : 'red']">
          <span style="width:100%"></span>
        </div>

        <!-- Package body -->
        <div v-if="group.linkCount === 0" class="pkg-body pkg-nomatch">
          <span>No sources matched this query from Radarr / Sonarr.</span>
        </div>
        <div v-else class="pkg-body">

          <!-- MOVIE -->
          <template v-if="group.kind === 'movie'">
            <div class="lg-thead lg-grid-movie">
              <span>Server</span><span>Variant</span><span>File</span><span>Download type</span><span>Status</span>
            </div>
            <div v-for="row in groupVariantRows(group)" :key="row.variant.key" class="lg-row lg-grid-movie">
              <button class="source-btn" title="View source" @click.stop>{{ row.source }}</button>
              <span class="var-dub">
                {{ variantLabel(row) }}
                <span v-if="row.primary" class="primary-dot" title="Primary"></span>
              </span>
              <span class="var-file">{{ variantFilename(group, row.variant) }}</span>
              <span class="grab-actions">
                <button class="grab-btn strm" @click="grab(row.variant.strmToken, 'strm', row.variant.key)">STRM</button>
                <button class="grab-btn hls" @click="grab(row.variant.downloadToken, 'download', row.variant.key)">HLS-DL</button>
              </span>
              <span><span class="pill green flat">ok</span></span>
            </div>
            <div class="pkg-foot">
              {{ group.linkCount }} result(s) — sources: {{ uniqueSources(group) }} · dubs: {{ uniqueDubs(group) }}
            </div>
          </template>

          <!-- TV: season → episode → rows -->
          <template v-else>
            <template v-for="season in group.seasons" :key="season.key">
              <template v-if="season.episodes.some(ep => episodeVariantRows(ep).length > 0)">
                <div
                  class="tree-row season"
                  :class="{ collapsed: collapsedSrvs.has(season.key) }"
                  @click="toggleSrv(season.key)"
                >
                  <svg class="tree-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                  <span class="label">{{ season.label }}</span>
                  <div class="meta">
                    <span>{{ season.episodes.reduce((n, ep) => n + episodeVariantRows(ep).length, 0) }} links</span>
                  </div>
                </div>
                <div class="tree-children">
                  <template v-for="episode in season.episodes" :key="episode.key">
                    <template v-if="episodeVariantRows(episode).length > 0">
                      <div
                        class="tree-row episode"
                        :class="{ collapsed: collapsedSrvs.has(episode.key) }"
                        @click="toggleSrv(episode.key)"
                      >
                        <svg class="tree-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                        <span class="label">{{ episode.label }}</span>
                        <div class="meta">
                          <span>{{ episodeVariantRows(episode).length }} links</span>
                        </div>
                      </div>
                      <div class="tree-children">
                        <div class="lg-thead lg-grid-movie in-episode">
                          <span>Server</span><span>Variant</span><span>File</span><span>Download type</span><span>Status</span>
                        </div>
                        <div
                          v-for="row in episodeVariantRows(episode)"
                          :key="row.variant.key"
                          class="lg-row lg-grid-movie in-episode"
                        >
                          <button class="source-btn" title="View source" @click.stop>{{ row.source }}</button>
                          <span class="var-dub">
                            {{ variantLabel(row) }}
                            <span v-if="row.primary" class="primary-dot" title="Primary"></span>
                          </span>
                          <span class="var-file">{{ variantFilename(group, row.variant) }}</span>
                          <span class="grab-actions">
                            <button class="grab-btn strm" @click="grab(row.variant.strmToken, 'strm', row.variant.key)">STRM</button>
                            <button class="grab-btn hls" @click="grab(row.variant.downloadToken, 'download', row.variant.key)">HLS-DL</button>
                          </span>
                          <span><span class="pill green flat">ok</span></span>
                        </div>
                      </div>
                    </template>
                  </template>
                </div>
              </template>
            </template>
            <div class="pkg-foot">
              {{ group.linkCount }} result(s) — sources: {{ uniqueSources(group) }} · dubs: {{ uniqueDubs(group) }}
            </div>
          </template>

        </div>
      </div>

      <!-- Footer summary -->
      <div class="pkg-foot-bar">
        <span>{{ displayGroups.length }} items · {{ grabsCount }} links</span>
        <span v-if="dupSearchCount > 0" class="pill gray flat">{{ dupSearchCount }} duplicate{{ dupSearchCount !== 1 ? 's' : '' }} hidden</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deleteActivity, getActivity, manualGrab, type ActivityEvent, type GrabToken } from '../api'

// ── Interfaces ────────────────────────────────────────────────────────────────

interface Variant {
  key: string
  server: string
  strmToken: string
  downloadToken: string
}

interface ServerNode {
  key: string
  source: string
  variants: Variant[]
}

interface VariantRow {
  source: string
  variant: Variant
  primary: boolean
}

interface EpisodeNode {
  key: string
  label: string
  servers: ServerNode[]
}

interface SeasonNode {
  key: string
  label: string
  episodes: EpisodeNode[]
  linkCount: number
}

interface MediaNode {
  key: string
  kind: 'movie' | 'tv'
  title: string
  tmdbId: string | null
  status: string
  detail: string
  ts: number
  servers: ServerNode[]
  seasons: SeasonNode[]
  linkCount: number
  rawTitle: string
}

// ── State ─────────────────────────────────────────────────────────────────────

const events            = ref<ActivityEvent[]>([])
const router            = useRouter()
const collapsedPkgs     = ref<Set<string>>(new Set())
const collapsedSrvs     = ref<Set<string>>(new Set())
const activeFilter      = ref<'all' | 'matched' | 'nomatch'>('matched')
const grabbedVariantKeys = ref<Set<string>>(new Set())
let timer: ReturnType<typeof setInterval>

// ── Computed ──────────────────────────────────────────────────────────────────

const allSearchEvents = computed(() => events.value.filter(e => e.kind === 'search'))
const matchedEvents   = computed(() => allSearchEvents.value.filter(e => e.grabs.length > 0))
const noMatchEvents   = computed(() => allSearchEvents.value.filter(e => e.grabs.length === 0))

const filteredEvents = computed(() => {
  if (activeFilter.value === 'matched')  return matchedEvents.value
  if (activeFilter.value === 'nomatch')  return noMatchEvents.value
  return allSearchEvents.value
})

const grabsCount = computed(() => matchedEvents.value.reduce((sum, e) => sum + e.grabs.length, 0))

const filters = computed(() => [
  { key: 'all'     as const, label: 'All',      count: allSearchEvents.value.length, countClass: '' },
  { key: 'matched' as const, label: 'Matched',  count: matchedEvents.value.length,   countClass: 'green' },
  { key: 'nomatch' as const, label: 'No match', count: noMatchEvents.value.length,   countClass: noMatchEvents.value.length ? 'red' : '' },
])

const deduplicatedEvents = computed(() => {
  const seen = new Map<string, ActivityEvent>()
  for (const ev of [...filteredEvents.value].sort((a, b) => b.ts - a.ts)) {
    const first = ev.grabs[0]
    const kind = isTvEvent(ev, first) ? 'tv' : 'movie'
    const tmdbId = ev.tmdb_id ?? first?.tmdb_id
    const key = tmdbId ? `${kind}:tmdb:${tmdbId}` : `${kind}:${mediaTitle(ev, first).toLowerCase().trim()}`
    if (!seen.has(key)) seen.set(key, ev)
  }
  return [...seen.values()].sort((a, b) => b.ts - a.ts)
})

const dupSearchCount = computed(() => filteredEvents.value.length - deduplicatedEvents.value.length)
const visibleGroups  = computed(() => deduplicatedEvents.value.map(toMediaNode))

// ── Actions ───────────────────────────────────────────────────────────────────

let initialLoadDone = false

async function load() {
  try { events.value = await getActivity() } catch {}
  if (!initialLoadDone) {
    initialLoadDone = true
    const keys = displayGroups.value.map(g => g.key)
    if (keys.length > 1) collapsedPkgs.value = new Set(keys.slice(1))
  }
}

async function grab(token: string, mode: string, variantKey: string) {
  const next = new Set(grabbedVariantKeys.value)
  next.add(variantKey)
  grabbedVariantKeys.value = next
  await manualGrab(token, mode)
  await router.push('/downloads')
}

async function deleteGroup(group: MediaNode) {
  await deleteActivity(group.ts, group.rawTitle)
  await load()
}

async function clearFiltered() {
  const toDelete = [...filteredEvents.value]
  for (const ev of toDelete) {
    try { await deleteActivity(ev.ts, ev.title) } catch {}
  }
  await load()
}

// ── Grabbed filtering ─────────────────────────────────────────────────────────

function ungrabbedCount(group: MediaNode): number {
  if (group.kind === 'movie') return groupVariantRows(group).length
  return group.seasons.reduce((sum, s) =>
    sum + s.episodes.reduce((n, ep) => n + episodeVariantRows(ep).length, 0), 0)
}

const displayGroups = computed(() =>
  visibleGroups.value.filter(g => g.linkCount === 0 || ungrabbedCount(g) > 0)
)

const allPkgsCollapsed = computed(() =>
  displayGroups.value.length > 0 &&
  displayGroups.value.every(g => collapsedPkgs.value.has(g.key))
)

function toggleAllPkgs() {
  if (allPkgsCollapsed.value) {
    collapsedPkgs.value = new Set()
  } else {
    collapsedPkgs.value = new Set(displayGroups.value.map(g => g.key))
  }
}

function togglePkg(key: string) {
  const s = new Set(collapsedPkgs.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedPkgs.value = s
}

function toggleSrv(key: string) {
  const s = new Set(collapsedSrvs.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedSrvs.value = s
}

// ── Build tree ────────────────────────────────────────────────────────────────

function toMediaNode(ev: ActivityEvent): MediaNode {
  const first = ev.grabs[0]
  const kind: 'movie' | 'tv' = isTvEvent(ev, first) ? 'tv' : 'movie'
  const title = mediaTitle(ev, first)
  const tmdbId = ev.tmdb_id ?? first?.tmdb_id ?? null
  const node: MediaNode = {
    key: `${ev.ts}:${ev.title}`,
    kind,
    title,
    tmdbId: tmdbId != null ? String(tmdbId) : null,
    status: ev.status || 'ok',
    detail: ev.detail,
    ts: ev.ts,
    servers: [],
    seasons: [],
    linkCount: ev.grabs.length,
    rawTitle: ev.title,
  }

  if (kind === 'movie') {
    node.servers = toServerNodes(ev.grabs, node.key)
    node.linkCount = node.servers.reduce((sum, s) => sum + s.variants.length, 0)
    return node
  }

  const seasonMap = new Map<number, GrabToken[]>()
  for (const g of ev.grabs) {
    const season = g.season || parseSeasonEpisode(g.title).season || 1
    const list = seasonMap.get(season) || []
    list.push(g)
    seasonMap.set(season, list)
  }

  node.seasons = [...seasonMap.entries()]
    .sort(([a], [b]) => a - b)
    .map(([season, seasonGrabs]) => {
      const episodeMap = new Map<number, GrabToken[]>()
      for (const g of seasonGrabs) {
        const ep = g.episode || parseSeasonEpisode(g.title).episode || 0
        const list = episodeMap.get(ep) || []
        list.push(g)
        episodeMap.set(ep, list)
      }
      const episodes: EpisodeNode[] = [...episodeMap.entries()]
        .sort(([a], [b]) => a - b)
        .map(([episode, epGrabs]) => ({
          key: `${node.key}:s${season}:e${episode}`,
          label: episode ? `Episode ${episode}` : 'Season pack',
          servers: toServerNodes(epGrabs, `${node.key}:s${season}:e${episode}`),
        }))
      const linkCount = episodes.reduce((sum, ep) => sum + ep.servers.reduce((n, s) => n + s.variants.length, 0), 0)
      return {
        key: `${node.key}:s${season}`,
        label: `Season ${season}`,
        episodes,
        linkCount,
      }
    })

  node.linkCount = node.seasons.reduce((sum, s) => sum + s.linkCount, 0)
  return node
}

function toServerNodes(grabs: GrabToken[], baseKey: string): ServerNode[] {
  const sourceMap = new Map<string, Map<string, { strm: string; download: string }>>()

  for (const g of grabs) {
    const source = g.source || stripMode(g.title)
    const server = g.server || ''
    const mode = g.output_mode === 'download' ? 'download' : 'strm'

    if (!sourceMap.has(source)) sourceMap.set(source, new Map())
    const varMap = sourceMap.get(source)!

    const existing = varMap.get(server)
    if (existing) {
      if (mode === 'download') existing.download = g.token
      else existing.strm = g.token
    } else {
      varMap.set(server, {
        strm: mode === 'strm' ? g.token : g.token,
        download: mode === 'download' ? g.token : g.token,
      })
    }
  }

  return [...sourceMap.entries()].map(([source, varMap], si) => {
    const variants: Variant[] = [...varMap.entries()].map(([server, tokens], vi) => ({
      key: `${baseKey}:src${si}:v${vi}`,
      server,
      strmToken: tokens.strm,
      downloadToken: tokens.download,
    }))
    return { key: `${baseKey}:src${si}`, source, variants }
  })
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function pkgSub(group: MediaNode): string {
  const sources = uniqueSources(group)
  const dubs = uniqueDubs(group)
  const srcCount = sources.split(', ').filter(Boolean).length
  const dubCount = dubs.split(', ').filter(Boolean).length
  const year = new Date(group.ts * 1000).getFullYear()
  return `${year} · ${srcCount} source${srcCount !== 1 ? 's' : ''} × ${dubCount} dub${dubCount !== 1 ? 's' : ''}`
}

function uniqueSources(group: MediaNode): string {
  const all: string[] = []
  if (group.kind === 'movie') {
    all.push(...group.servers.map(s => s.source))
  } else {
    for (const season of group.seasons)
      for (const ep of season.episodes)
        all.push(...ep.servers.map(s => s.source))
  }
  return [...new Set(all)].join(', ')
}

function uniqueDubs(group: MediaNode): string {
  const all: string[] = []
  if (group.kind === 'movie') {
    for (const srv of group.servers)
      all.push(...srv.variants.map(v => v.server || srv.source))
  } else {
    for (const season of group.seasons)
      for (const ep of season.episodes)
        for (const srv of ep.servers)
          all.push(...srv.variants.map(v => v.server || srv.source))
  }
  return [...new Set(all.filter(Boolean))].join(', ')
}

function groupVariantRows(group: MediaNode): VariantRow[] {
  return group.servers.flatMap(serverVariantRows)
    .filter(r => !grabbedVariantKeys.value.has(r.variant.key))
}

function episodeVariantRows(episode: EpisodeNode): VariantRow[] {
  return episode.servers.flatMap(serverVariantRows)
    .filter(r => !grabbedVariantKeys.value.has(r.variant.key))
}

function serverVariantRows(srv: ServerNode): VariantRow[] {
  return srv.variants.map((variant, index) => ({
    source: srv.source,
    variant,
    primary: index === 0,
  }))
}

function variantLabel(row: VariantRow): string {
  return row.variant.server || row.source
}

function variantFilename(group: MediaNode, variant: Variant): string {
  const dub = variant.server || ''
  const parts = [group.title, dub ? `[${dub}]` : '', '[STRM]'].filter(Boolean)
  return parts.join(' ')
}

function mediaTitle(ev: ActivityEvent, first?: GrabToken) {
  if (first?.media_title) return first.media_title
  return ev.title.replace(/^(Movie|TV):\s*/i, '') || first?.title || 'Unknown media'
}

function isTvEvent(ev: ActivityEvent, first?: GrabToken) {
  return first?.media_kind === 'episode' || /^TV:/i.test(ev.title) || ev.grabs.some(g => /S\d{1,2}E\d{1,3}/i.test(g.title))
}

function parseSeasonEpisode(title: string) {
  const match = title.match(/S(\d{1,2})(?:E(\d{1,3}))?/i)
  return {
    season: match ? Number(match[1]) : null,
    episode: match?.[2] ? Number(match[2]) : null,
  }
}

function stripMode(title: string) {
  return title.replace(/\s+\[(STRM|HLS-DL)\]\s*$/i, '')
}

function relTime(ts: number) {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(ts * 1000).toLocaleDateString()
}

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
/* ── Table grid ── */
.lg-grid-movie {
  display: grid;
  grid-template-columns: 100px 160px minmax(200px, 1fr) 140px 70px;
  gap: 14px;
  align-items: center;
  padding: 0 18px;
}
.lg-grid-movie.in-episode {
  padding-left: 36px;
}

.lg-thead {
  padding-top: 8px; padding-bottom: 8px;
  background: var(--bg-2);
  color: var(--text-3); font-family: var(--font-mono);
  font-size: 10px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
  border-bottom: 1px solid var(--border);
}

.lg-row {
  min-height: 38px; padding-top: 6px; padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.lg-row:last-of-type { border-bottom: none; }

/* ── Source button ── */
.source-btn {
  border: 0; background: transparent;
  color: var(--blue); cursor: pointer;
  font: 700 12px/1 var(--font-mono);
  overflow: hidden; padding: 0; text-align: left;
  text-overflow: ellipsis; white-space: nowrap;
}
.source-btn:hover { color: #9cc9ff; text-decoration: underline; }

/* ── Variant / dub ── */
.var-dub {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.primary-dot {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  background: var(--teal);
  box-shadow: 0 0 0 2px rgba(94,224,189,.15), 0 0 5px rgba(94,224,189,.35);
}

/* ── File name ── */
.var-file {
  font-family: var(--font-mono); font-size: 11.5px; color: var(--text-3);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Grab action buttons ── */
.grab-actions { display: flex; gap: 5px; align-items: center; }
.grab-btn {
  height: 24px; padding: 0 9px; border-radius: 5px; cursor: pointer;
  font: 600 10.5px/1 var(--font-mono); letter-spacing: .04em;
  transition: background .12s, border-color .12s, color .12s;
}
.grab-btn.strm {
  background: rgba(94,224,189,.12); color: var(--teal);
  border: 1px solid rgba(94,224,189,.25);
}
.grab-btn.strm:hover { background: rgba(94,224,189,.22); border-color: var(--teal); }
.grab-btn.hls {
  background: rgba(245,166,35,.10); color: var(--accent, #f5a623);
  border: 1px solid rgba(245,166,35,.25);
}
.grab-btn.hls:hover { background: rgba(245,166,35,.20); border-color: var(--accent, #f5a623); }

/* ── Row action (delete button in pkg-head) ── */
.row-action {
  height: 28px; width: 30px; padding: 0; border-radius: 7px;
  border: 1px solid var(--border-2); background: var(--surface-2); color: var(--text);
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer; transition: border-color .12s, background .12s, color .12s;
  flex-shrink: 0;
}
.row-action svg { width: 14px; height: 14px; flex-shrink: 0; }
.row-action:hover { border-color: var(--blue-line); background: var(--blue-soft); color: #dbeafe; }
.row-action.danger:hover { border-color: rgba(255,107,122,.45); background: rgba(255,107,122,.12); color: #ffd6dc; }

/* ── Pkg color strip ── */
:global(.pkg-bar.teal span) { background: var(--teal) !important; }
:global(.pkg-bar.red   span) { background: var(--red)  !important; width: 100% !important; }

/* ── No-match body ── */
.pkg-nomatch {
  padding: 11px 18px;
  font-size: 12.5px; color: var(--text-3); font-family: var(--font-mono);
}

/* ── Pkg foot ── */
.pkg-foot {
  padding: 10px 18px;
  font-family: var(--font-mono); font-size: 11.5px; color: var(--text-3);
  border-top: 1px solid var(--border); background: var(--bg-2);
}
.pkg-foot-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 18px; border-top: 1px solid var(--border);
  font-size: 12px; color: var(--text-3);
}

/* ── Filter chips (same as Downloads) ── */
.filter-chip {
  display: inline-flex; align-items: center; gap: 7px; padding: 6px 11px; border-radius: 7px;
  background: transparent; border: 1px solid transparent; color: var(--text-2);
  font: 500 13px/1 var(--font-sans); cursor: pointer; transition: all .12s; user-select: none;
}
.filter-chip:hover { background: var(--surface-2); color: var(--text); }
.filter-chip.active { background: var(--surface-2); border-color: var(--border-2); color: var(--text); }
.filter-chip .n { font-family: var(--font-mono); font-size: 11.5px; font-weight: 600; color: var(--text-3); }
.filter-chip .n.green { color: var(--green); }
.filter-chip .n.red   { color: var(--red); }

/* ── Time badge ── */
.time { font-size: 12px; color: var(--text-3); font-family: var(--font-mono); }

/* ── Tree season/episode indent ── */
:global(.tree-row.season), :global(.tree-row.episode) { padding-left: 18px; }
</style>
