<template>
  <div>
    <div class="page-head">
      <div>
        <h1>Downloads</h1>
        <p class="sub">Queue grouped by media, season, and episode with per-job progress.</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn" @click="load">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh
        </button>
      </div>
    </div>

    <div class="toolbar">
      <div class="group">
        <button class="btn" @click="bulk('resume_all')">
          <svg viewBox="0 0 24 24" fill="var(--green)" stroke="none"><polygon points="6 4 20 12 6 20"/></svg>
          Resume all
        </button>
        <button class="btn" @click="bulk('pause_all')">
          <svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>
          Pause all
        </button>
        <button class="btn" @click="bulk('clear_done')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          Clear done
        </button>
      </div>
      <div class="divider"></div>
      <div class="group">
        <span class="filter-chip" :class="{ active: activeFilter === 'all' }" @click="activeFilter = 'all'">
          All <span class="n">{{ jobs.length }}</span>
        </span>
        <span class="filter-chip" :class="{ active: activeFilter === 'running' }" @click="activeFilter = 'running'">
          Running <span class="n green">{{ counts.running }}</span>
        </span>
        <span class="filter-chip" :class="{ active: activeFilter === 'error' }" @click="activeFilter = 'error'">
          Errors <span class="n red">{{ counts.error }}</span>
        </span>
      </div>
      <span class="spacer"></span>
      <button class="btn ghost sm" :disabled="!downloadGroups.length" @click="toggleAllPkgs">
        <svg v-if="allPkgsCollapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="7 11 12 6 17 11"/><polyline points="7 18 12 13 17 18"/></svg>
        {{ allPkgsCollapsed ? 'Expand all' : 'Collapse all' }}
      </button>
    </div>

    <div v-if="!jobs.length" class="empty-state">
      <h3>No download tasks yet</h3>
      <p>When a source resolves to a stream, it shows up here with live progress and status.</p>
    </div>

    <div v-else class="pkg-list">
      <div
        v-for="group in downloadGroups"
        :key="group.key"
        class="pkg"
        :class="{ collapsed: collapsedPkgs.has(group.key) }"
      >
        <!-- Package head -->
        <div class="pkg-head" @click="togglePkg(group.key)">
          <div :class="['pkg-mark', group.kind === 'movie' ? 'movie' : 'tv']">
            {{ group.kind === 'movie' ? 'M' : 'TV' }}
          </div>
          <div class="pkg-title-block">
            <div class="pkg-title">
              {{ group.title }}
              <span class="id">{{ group.mediaType === 'movie' ? 'movie' : 'tv' }}</span>
              <a v-if="group.tmdbId" class="id link-id" :href="tmdbUrl(group)" target="_blank" rel="noreferrer" @click.stop>tmdb {{ group.tmdbId }}</a>
            </div>
            <div class="pkg-sub">{{ group.count }} task{{ group.count !== 1 ? 's' : '' }}<template v-if="group.year"> · {{ group.year }}</template></div>
          </div>
          <div class="pkg-right">
            <span>{{ group.count }} tasks</span>
            <span :class="['pill', statusPill(group.status)]">{{ group.status }}</span>
            <span v-if="group.avgPct !== null" style="font-family:var(--font-mono);font-size:11px;">{{ group.avgPct }}%</span>
            <button v-if="canPauseAny(groupJobs(group))" class="row-action" title="Pause all media tasks" @click.stop="pauseJobs(group.jobIds)"><PauseIcon /></button>
            <button v-else-if="canResumeAny(groupJobs(group))" class="row-action" title="Resume all media tasks" @click.stop="resumeJobs(group.jobIds)"><PlayIcon /></button>
            <button class="row-action danger" title="Remove all media tasks" @click.stop="removeJobs(group.jobIds)"><TrashIcon /></button>
            <button class="icon-mini" :title="collapsedPkgs.has(group.key) ? 'Expand' : 'Collapse'" @click.stop="togglePkg(group.key)">
              <svg class="pkg-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Progress bar strip -->
        <div :class="['pkg-bar', pkgBarColor(group.status)]">
          <span :style="{ width: (group.avgPct ?? 0) + '%' }"></span>
        </div>

        <!-- Package body -->
        <div class="pkg-body">

          <!-- MOVIE: grouped by source -->
          <template v-if="group.kind === 'movie'">
            <template v-for="sg in group.sourceGroups" :key="sg.source ?? '__auto__'">
              <!-- Source sub-header (only shown when multiple sources) -->
              <div v-if="group.sourceGroups.length > 1" class="source-group-head">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span>{{ sg.source || '—' }}</span>
              </div>
              <div class="dl-thead-srv movie-flat">
                <span>Source</span><span>File</span><span>Variant</span><span>Output</span><span>Status</span><span>Progress</span><span>Action</span>
              </div>
              <div v-for="job in sg.jobs" :key="job.id" class="dl-variant movie-flat">
                <button class="source-btn" title="Show source raw JSON" @click="showSource(job)">{{ job.source || '—' }}</button>
                <span class="var-file">{{ job.save_path || job.hls_url || job.title }}</span>
                <span class="var-variant">{{ job.server_label || '—' }}</span>
                <span class="var-types">
                  <span :class="['pill flat', outputModePill(job.output_mode)]">{{ job.output_mode.toUpperCase() }}</span>
                </span>
                <span>
                  <span class="status-cell">
                    <button
                      :class="['pill', statusPill(job.status), { clickable: !!job.error }]"
                      :title="job.error ? 'Show error' : job.status"
                      @click="job.error && showError(job)"
                    >{{ job.status }}</button>
                  </span>
                </span>
                <div class="var-prog pct-only">{{ pct(job) }}%</div>
                <span class="leaf-actions">
                  <button v-if="canPause(job)" class="row-action" title="Pause" @click="act('pause', job.id)"><PauseIcon /></button>
                  <button v-else-if="canResume(job)" class="row-action" title="Resume" @click="act('resume', job.id)"><PlayIcon /></button>
                  <button class="row-action danger" title="Remove" @click="removeJobs([job.id])"><TrashIcon /></button>
                </span>
              </div>
            </template>
          </template>

          <!-- TV: grouped by season -->
          <template v-else>
            <template v-for="season in group.seasons" :key="season.key">
              <!-- Season sub-header -->
              <div class="tree-row season" @click="toggleSeason(season.key)">
                <span class="meta">
                  <button class="icon-mini" @click.stop="toggleSeason(season.key)">
                    <svg :class="['tree-chev', { open: !collapsedSeasons.has(season.key) }]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                  </button>
                  {{ season.label }}
                </span>
                <span class="meta mono muted">{{ season.count }} ep</span>
                <span style="flex:1"></span>
                <span class="leaf-actions">
                  <button class="row-action danger" title="Remove season" @click.stop="removeJobs(season.jobIds)"><TrashIcon /></button>
                </span>
              </div>

              <template v-if="!collapsedSeasons.has(season.key)">
                <div class="dl-thead-tv">
                  <span>Episode</span><span>Source</span><span>File</span><span>Variant</span><span>Output</span><span>Status</span><span>Progress</span><span>Action</span>
                </div>
                <template v-for="ep in season.episodes" :key="ep.key">
                  <div v-for="job in ep.jobs" :key="job.id" class="dl-variant tv-flat">
                    <span class="tv-meta">{{ ep.label }}</span>
                    <button class="source-btn" title="Show source raw JSON" @click="showSource(job)">{{ job.source || '—' }}</button>
                    <span class="var-file">{{ job.save_path || job.hls_url || job.title }}</span>
                    <span class="var-variant">{{ job.server_label || '—' }}</span>
                    <span class="var-types">
                      <span :class="['pill flat', outputModePill(job.output_mode)]">{{ job.output_mode.toUpperCase() }}</span>
                    </span>
                    <span>
                      <span class="status-cell">
                        <button
                          :class="['pill', statusPill(job.status), { clickable: !!job.error }]"
                          :title="job.error ? 'Show error' : job.status"
                          @click="job.error && showError(job)"
                        >{{ job.status }}</button>
                      </span>
                    </span>
                    <div class="var-prog pct-only">{{ pct(job) }}%</div>
                    <span class="leaf-actions">
                      <button v-if="canPause(job)" class="row-action" title="Pause" @click="act('pause', job.id)"><PauseIcon /></button>
                      <button v-else-if="canResume(job)" class="row-action" title="Resume" @click="act('resume', job.id)"><PlayIcon /></button>
                      <button class="row-action danger" title="Remove" @click="removeJobs([job.id])"><TrashIcon /></button>
                    </span>
                  </div>
                </template>
              </template>
            </template>
          </template>

          <!-- Footer -->
          <div class="pkg-foot">
            <span>{{ group.count }} task{{ group.count !== 1 ? 's' : '' }}</span>
            <span v-if="hiddenJobsCount > 0">{{ hiddenJobsCount }} duplicate{{ hiddenJobsCount !== 1 ? 's' : '' }} hidden</span>
          </div>

        </div>
      </div>
    </div>

    <div v-if="modal" class="modal-backdrop" @click="modal = null">
      <div class="json-modal" @click.stop>
        <div class="json-modal-head">
          <div>
            <h3>{{ modal.title }}</h3>
            <p>{{ modal.subtitle }}</p>
          </div>
          <button class="icon-mini" title="Close" @click="modal = null">×</button>
        </div>
        <pre>{{ modal.body }}</pre>
      </div>
    </div>
  </div>

  <!-- Remove confirm dialog -->
  <teleport to="body">
    <div v-if="removeDlg" class="confirm-overlay" @click.self="removeDlg = null">
      <div class="confirm-box">
        <div class="confirm-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </div>
        <div class="confirm-body">
          <p class="confirm-title">Remove from queue</p>
          <p class="confirm-msg">Remove {{ removeDlg.ids.length }} {{ removeDlg.ids.length === 1 ? 'task' : 'tasks' }} from the queue? This cannot be undone.</p>
          <label class="confirm-check">
            <input type="checkbox" v-model="removeDlg.deleteFiles" />
            <span class="check-box"></span>
            <span>Also delete output file(s) from disk</span>
          </label>
        </div>
        <div class="confirm-actions">
          <button class="btn ghost sm" @click="removeDlg = null">Cancel</button>
          <button class="btn danger sm" @click="doRemove">Remove</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { getPipeline, jobAction, bulkAction, type PipelineJob } from '../api'

const iconBase = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': '2.2',
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
  'aria-hidden': 'true',
}

const PlayIcon = () => h('svg', { ...iconBase, fill: 'currentColor', stroke: 'none' }, [
  h('polygon', { points: '7 5 19 12 7 19' }),
])

const PauseIcon = () => h('svg', iconBase, [
  h('rect', { x: '7', y: '5', width: '3.5', height: '14', rx: '1' }),
  h('rect', { x: '13.5', y: '5', width: '3.5', height: '14', rx: '1' }),
])

const TrashIcon = () => h('svg', iconBase, [
  h('path', { d: 'M3 6h18' }),
  h('path', { d: 'M8 6V4h8v2' }),
  h('path', { d: 'M19 6l-1 14H6L5 6' }),
  h('path', { d: 'M10 11v5' }),
  h('path', { d: 'M14 11v5' }),
])

// ── Interfaces ────────────────────────────────────────────────────────────────

interface EpisodeGroup {
  key: string
  label: string
  jobs: PipelineJob[]
  status: string
  progress: number
  jobIds: string[]
}

interface SeasonGroup {
  key: string
  label: string
  episodes: EpisodeGroup[]
  count: number
  jobIds: string[]
}

interface MovieSourceGroup {
  source: string | null
  jobs: PipelineJob[]
}

interface DownloadGroup {
  key: string
  kind: 'movie' | 'tv'
  title: string
  mediaType: 'movie' | 'tv'
  tmdbId: number | null
  year: number | null
  status: string
  count: number
  avgPct: number | null
  jobs: PipelineJob[]
  sourceGroups: MovieSourceGroup[]
  seasons: SeasonGroup[]
  jobIds: string[]
}

// ── State ─────────────────────────────────────────────────────────────────────

const jobs = ref<PipelineJob[]>([])
const activeFilter = ref<'all' | 'running' | 'error'>('all')
const collapsedPkgs = ref<Set<string>>(new Set())
const collapsedSeasons = ref<Set<string>>(new Set())
const modal = ref<{ title: string; subtitle: string; body: string } | null>(null)
let timer: ReturnType<typeof setInterval>

// ── Computed ──────────────────────────────────────────────────────────────────

const counts = computed(() => ({
  running:   jobs.value.filter(j => j.status === 'running').length,
  error:     jobs.value.filter(j => j.status === 'error').length,
  completed: jobs.value.filter(j => j.status === 'completed').length,
}))

const filteredJobs = computed(() => {
  if (activeFilter.value === 'running') return jobs.value.filter(j => j.status === 'running')
  if (activeFilter.value === 'error')   return jobs.value.filter(j => j.status === 'error')
  return jobs.value
})

// ── Dedup helpers ──────────────────────────────────────────────────────────────

function bestJob(a: PipelineJob, b: PipelineJob): PipelineJob {
  const priority: Record<string, number> = { running: 5, queued: 4, completed: 3, paused: 2, error: 1 }
  const pa = priority[a.status] ?? 0
  const pb = priority[b.status] ?? 0
  if (pa !== pb) return pa > pb ? a : b
  return a.created_at >= b.created_at ? a : b
}

function deduplicateByMode(items: PipelineJob[]): { kept: PipelineJob[]; hidden: number } {
  const modeMap = new Map<string, PipelineJob>()
  for (const job of items) {
    const existing = modeMap.get(job.output_mode)
    modeMap.set(job.output_mode, existing ? bestJob(existing, job) : job)
  }
  return { kept: [...modeMap.values()], hidden: items.length - modeMap.size }
}

// ── Groups ────────────────────────────────────────────────────────────────────

const _groupsResult = computed(() => {
  let hiddenJobs = 0
  const map = new Map<string, PipelineJob[]>()
  for (const job of filteredJobs.value) {
    // Use query as fallback for title to avoid "Sonarr series" placeholder grouping
    const displayName = job.query || job.title
    const key = `${job.kind}:${displayName}`
    const list = map.get(key) || []
    list.push(job)
    map.set(key, list)
  }

  const groups: DownloadGroup[] = [...map.entries()].map(([key, items]) => {
    const first = items[0]
    const kind = first.kind === 'movie' ? 'movie' : 'tv'
    const displayTitle = first.query || first.title
    const group: DownloadGroup = {
      key,
      kind,
      title: displayTitle,
      mediaType: first.media_type || (kind === 'movie' ? 'movie' : 'tv'),
      tmdbId: first.tmdb_id || null,
      year: first.year || null,
      status: aggregateStatus(items),
      count: items.length,
      avgPct: null,
      jobs: [],
      sourceGroups: [],
      seasons: [],
      jobIds: items.map(j => j.id),
    }

    if (kind === 'movie') {
      // Group by source, dedup within each source by output_mode
      const sourceMap = new Map<string | null, PipelineJob[]>()
      for (const item of items) {
        const src = item.source || null
        const list = sourceMap.get(src) || []
        list.push(item)
        sourceMap.set(src, list)
      }
      let allKept: PipelineJob[] = []
      group.sourceGroups = [...sourceMap.entries()].map(([source, srcJobs]) => {
        const { kept, hidden } = deduplicateByMode(srcJobs)
        hiddenJobs += hidden
        allKept = allKept.concat(kept)
        return { source, jobs: sortJobs(kept) }
      })
      group.jobs = allKept
      group.count = allKept.length
      group.avgPct = avgPct(allKept)
      return group
    }

    const seasonMap = new Map<number, PipelineJob[]>()
    for (const item of items) {
      const season = item.season || 1
      const list = seasonMap.get(season) || []
      list.push(item)
      seasonMap.set(season, list)
    }

    group.seasons = [...seasonMap.entries()].sort(([a], [b]) => a - b).map(([season, seasonJobs]) => {
      const episodeMap = new Map<number, PipelineJob[]>()
      for (const job of seasonJobs) {
        const episode = job.episode || 0
        const list = episodeMap.get(episode) || []
        list.push(job)
        episodeMap.set(episode, list)
      }
      const episodes = [...episodeMap.entries()].sort(([a], [b]) => a - b).map(([episode, epJobs]) => {
        const { kept, hidden } = deduplicateByMode(epJobs)
        hiddenJobs += hidden
        return {
          key: `${key}:s${season}:e${episode}`,
          label: episode ? `E${String(episode).padStart(2, '0')}` : 'Season pack',
          jobs: sortJobs(kept),
          status: aggregateStatus(kept),
          progress: Math.round((kept.reduce((sum, job) => sum + job.progress, 0) / Math.max(kept.length, 1)) * 100),
          jobIds: epJobs.map(j => j.id),
        }
      })
      return {
        key: `${key}:s${season}`,
        label: `Season ${season}`,
        episodes,
        count: seasonJobs.length,
        jobIds: seasonJobs.map(j => j.id),
      }
    })

    const allKept = group.seasons.flatMap(s => s.episodes.flatMap(e => e.jobs))
    group.avgPct = avgPct(allKept)
    return group
  })

  return { groups, hiddenJobs }
})

const downloadGroups = computed(() => _groupsResult.value.groups)
const hiddenJobsCount = computed(() => _groupsResult.value.hiddenJobs)

// ── Actions ───────────────────────────────────────────────────────────────────

let initialLoadDone = false

async function load() {
  try { jobs.value = await getPipeline() } catch {}
  if (!initialLoadDone) {
    initialLoadDone = true
    const keys = downloadGroups.value.map(g => g.key)
    if (keys.length > 1) collapsedPkgs.value = new Set(keys.slice(1))
  }
}

async function act(action: 'resume' | 'pause' | 'delete', id: string) {
  if (action === 'delete') {
    await removeJobs([id])
    return
  }
  await jobAction(action, id)
  await load()
}

async function resumeJobs(ids: string[]) {
  if (!ids.length) return
  await jobAction('resume', ids.join(','))
  await load()
}

async function pauseJobs(ids: string[]) {
  if (!ids.length) return
  await jobAction('pause', ids.join(','))
  await load()
}

// ── Remove confirm dialog ─────────────────────────────────────────────────────
interface RemoveDlg { ids: string[]; deleteFiles: boolean }
const removeDlg = ref<RemoveDlg | null>(null)

function removeJobs(ids: string[]) {
  if (!ids.length) return
  removeDlg.value = { ids, deleteFiles: false }
}

async function doRemove() {
  if (!removeDlg.value) return
  const { ids, deleteFiles } = removeDlg.value
  removeDlg.value = null
  await jobAction('delete', ids.join(','), { deleteFiles })
  await load()
}

function showSource(job: PipelineJob) {
  modal.value = {
    title: `${job.source || 'auto'} source`,
    subtitle: job.title,
    body: JSON.stringify(job.source_raw ?? sourceFallback(job), null, 2),
  }
}

function showError(job: PipelineJob) {
  modal.value = {
    title: 'Job error',
    subtitle: job.title,
    body: job.error || 'Unknown error',
  }
}

async function bulk(action: 'resume_all' | 'pause_all' | 'clear_done') {
  await bulkAction(action)
  await load()
}

const allPkgsCollapsed = computed(() =>
  downloadGroups.value.length > 0 &&
  downloadGroups.value.every(g => collapsedPkgs.value.has(g.key))
)

function toggleAllPkgs() {
  if (allPkgsCollapsed.value) {
    collapsedPkgs.value = new Set()
  } else {
    collapsedPkgs.value = new Set(downloadGroups.value.map(g => g.key))
  }
}

function togglePkg(key: string) {
  const s = new Set(collapsedPkgs.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedPkgs.value = s
}

function toggleSeason(key: string) {
  const s = new Set(collapsedSeasons.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedSeasons.value = s
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function sortJobs(items: PipelineJob[]) {
  return [...items].sort((a, b) => b.created_at - a.created_at)
}

function aggregateStatus(items: PipelineJob[]) {
  if (items.some(j => j.status === 'running')) return 'running'
  if (items.some(j => j.status === 'error')) return 'error'
  if (items.some(j => j.status === 'queued')) return 'queued'
  if (items.some(j => j.status === 'paused')) return 'paused'
  if (items.every(j => j.status === 'completed')) return 'completed'
  return items[0]?.status || 'queued'
}

function avgPct(items: PipelineJob[]): number {
  if (!items.length) return 0
  return Math.round((items.reduce((sum, j) => sum + j.progress, 0) / items.length) * 100)
}

function pct(job: PipelineJob): number {
  return Math.round(job.progress * 100)
}

function statusPill(status: string): string {
  if (status === 'running')   return 'green'
  if (status === 'completed') return 'teal'
  if (status === 'error')     return 'red'
  if (status === 'paused')    return 'amber'
  return 'gray'
}

function pkgBarColor(status: string): string {
  if (status === 'error')  return 'red'
  if (status === 'paused') return 'amber'
  if (status === 'queued' || status === 'completed') return 'gray'
  return ''
}

function outputModePill(mode: string): string {
  if (mode === 'strm') return 'teal'
  return 'blue'
}

function tmdbUrl(group: DownloadGroup): string {
  return `https://www.themoviedb.org/${group.mediaType === 'movie' ? 'movie' : 'tv'}/${group.tmdbId}`
}

function sourceFallback(job: PipelineJob) {
  return {
    source: job.source,
    media_type: job.media_type,
    tmdb_id: job.tmdb_id,
    tvdb_id: job.tvdb_id,
    hls_url: job.hls_url,
    save_path: job.save_path,
    search_log: job.search_log || [],
  }
}

function canResume(job: PipelineJob): boolean {
  return ['paused', 'error', 'queued'].includes(job.status)
}

function canPause(job: PipelineJob): boolean {
  return ['running', 'queued'].includes(job.status)
}

function canResumeAny(items: PipelineJob[]): boolean {
  return items.some(canResume)
}

function canPauseAny(items: PipelineJob[]): boolean {
  return items.some(canPause)
}

function seasonJobs(season: SeasonGroup): PipelineJob[] {
  return season.episodes.flatMap(episode => episode.jobs)
}

function groupJobs(group: DownloadGroup): PipelineJob[] {
  if (group.kind === 'movie') return group.jobs
  return group.seasons.flatMap(seasonJobs)
}


onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
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

.leaf-actions { display: flex; gap: 4px; align-items: center; flex-shrink: 0; }

.row-action {
  height: 28px;
  width: 30px;
  padding: 0;
  border-radius: 7px;
  border: 1px solid var(--border-2);
  background: var(--surface-2);
  color: var(--text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color .12s, background .12s, color .12s;
}
.row-action svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
.row-action:hover {
  border-color: var(--blue-line);
  background: var(--blue-soft);
  color: #dbeafe;
}
.row-action.danger:hover {
  border-color: rgba(255,107,122,.45);
  background: rgba(255,107,122,.12);
  color: #ffd6dc;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.status-error {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--red);
  font-family: var(--font-mono);
  font-size: 11px;
}

.source-btn {
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--blue);
  cursor: pointer;
  font: 700 12px/1 var(--font-mono);
  overflow: hidden;
  padding: 0;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-btn:hover { color: #9cc9ff; text-decoration: underline; }

.pill.clickable {
  appearance: none;
  font-family: inherit;
  cursor: pointer;
}

.pill.clickable:hover {
  filter: brightness(1.14);
}

.link-id {
  text-decoration: none;
}
.link-id:hover {
  border-color: var(--blue-line);
  color: #cfe4ff;
}

.pct-only {
  justify-content: center;
  color: var(--text-2);
  font-family: var(--font-mono);
  font-size: 11.5px;
}

.var-variant {
  font-size: 11.5px;
  color: var(--text-2);
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-group-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  color: var(--blue);
  font: 700 11px/1 var(--font-mono);
  text-transform: uppercase;
  letter-spacing: .06em;
}

.tv-meta {
  color: var(--text-2);
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 600;
}

.pkg-foot {
  padding: 10px 18px;
  font-family: var(--font-mono); font-size: 11.5px; color: var(--text-3);
  border-top: 1px solid var(--border); background: var(--bg-2);
  display: flex; align-items: center; justify-content: space-between;
}

:global(.pkg-head) {
  padding: 12px 14px 12px 18px;
}

:global(.pkg-right) {
  gap: 8px;
}

:global(.pkg-right .icon-mini .pkg-chev),
:global(.tree-row .meta .icon-mini .tree-chev) {
  width: 14px;
  height: 14px;
}

:global(.tree-row.season) {
  padding: 8px 14px 8px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  user-select: none;
}

:global(.tree-row.season:hover) {
  background: color-mix(in srgb, var(--surface-2) 80%, var(--border));
}

:global(.tree-row.season .meta) {
  display: flex;
  align-items: center;
  gap: 6px;
  font: 600 12px/1 var(--font-sans);
  color: var(--text);
}

:global(.tree-row.season .meta.mono.muted) {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-3);
  font-weight: 400;
}

:global(.tree-chev) {
  width: 14px;
  height: 14px;
  transition: transform .18s;
  transform: rotate(-90deg);
}

:global(.tree-chev.open) {
  transform: rotate(0deg);
}

:global(.dl-thead-srv),
:global(.dl-thead-srv.in-episode),
:global(.dl-variant),
:global(.dl-variant.in-episode) {
  grid-template-columns: minmax(220px, 1fr) 90px minmax(190px, 320px) 78px 180px;
  padding-left: 18px;
}

:global(.dl-thead-srv.movie-flat),
:global(.dl-variant.movie-flat) {
  display: grid;
  grid-template-columns: 92px minmax(160px, .72fr) 110px 90px minmax(110px, 200px) 66px 76px !important;
  gap: 12px;
  align-items: center;
  padding: 8px 18px !important;
  border-bottom: 1px solid var(--border);
}

:global(.dl-thead-srv.movie-flat) {
  background: var(--bg-2);
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

:global(.dl-variant.movie-flat) {
  min-height: 38px;
}

:global(.dl-thead-tv),
:global(.dl-variant.tv-flat) {
  display: grid;
  grid-template-columns: 52px 92px minmax(160px, .72fr) 110px 90px minmax(110px, 200px) 66px 76px;
  gap: 12px;
  align-items: center;
  padding: 8px 18px;
  border-bottom: 1px solid var(--border);
}

:global(.dl-thead-tv) {
  background: var(--bg-2);
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

:global(.dl-variant.tv-flat) {
  min-height: 38px;
}

:global(.dl-variant .var-prog.pct-only) {
  display: block;
  min-width: auto;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, .58);
}

.json-modal {
  width: min(860px, 92vw);
  max-height: min(760px, 86vh);
  overflow: hidden;
  border: 1px solid var(--border-2);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}

.json-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.json-modal-head h3 { margin: 0; font-size: 15px; }
.json-modal-head p {
  margin: 3px 0 0;
  color: var(--text-3);
  font: 11.5px/1.4 var(--font-mono);
}
.json-modal pre {
  max-height: calc(min(760px, 86vh) - 72px);
  margin: 0;
  overflow: auto;
  padding: 16px;
  background: var(--bg);
  color: var(--text-2);
  font: 11.5px/1.55 var(--font-mono);
  white-space: pre-wrap;
}
</style>
