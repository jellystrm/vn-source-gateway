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
          <svg class="pkg-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
          <div :class="['pkg-mark', group.kind === 'movie' ? 'movie' : 'tv']">
            {{ group.kind === 'movie' ? 'M' : 'TV' }}
          </div>
          <div class="pkg-title-block">
            <div class="pkg-title">{{ group.title }}</div>
            <div class="pkg-sub">{{ group.count }} task{{ group.count !== 1 ? 's' : '' }}</div>
          </div>
          <div class="pkg-right">
            <span>{{ group.count }} tasks</span>
            <span :class="['pill', statusPill(group.status)]">{{ group.status }}</span>
            <span v-if="group.avgPct !== null" style="font-family:var(--font-mono);font-size:11px;">{{ group.avgPct }}%</span>
            <button class="icon-mini danger" title="Delete media tasks" @click.stop="deleteJobs(group.jobIds)">✕</button>
          </div>
        </div>

        <!-- Progress bar strip -->
        <div :class="['pkg-bar', pkgBarColor(group.status)]">
          <span :style="{ width: (group.avgPct ?? 0) + '%' }"></span>
        </div>

        <!-- Package body -->
        <div class="pkg-body">

          <!-- MOVIE -->
          <template v-if="group.kind === 'movie'">
            <div class="dl-thead-srv">
              <span>File</span><span>Output</span><span>Status</span><span>Progress</span><span>Action</span>
            </div>
            <div v-for="job in group.jobs" :key="job.id" class="dl-variant">
              <span class="var-file">{{ job.save_path || job.hls_url || job.title }}</span>
              <span class="var-types">
                <span :class="['pill flat', outputModePill(job.output_mode)]">{{ job.output_mode.toUpperCase() }}</span>
              </span>
              <span>
                <span :class="['pill', statusPill(job.status)]">{{ job.status }}</span>
              </span>
              <div class="var-prog">
                <div :class="['var-prog-bar', progBarColor(job.status)]">
                  <span :style="{ width: pct(job) + '%' }"></span>
                </div>
                <div class="var-prog-meta">
                  <span class="a">{{ pct(job) }}%</span>
                  <span :class="statusTextClass(job.status)">{{ statusText(job) }}</span>
                </div>
              </div>
              <span class="leaf-actions">
                <button v-if="canResume(job)" class="icon-mini" title="Resume" @click="act('resume', job.id)">▶</button>
                <button v-if="canPause(job)" class="icon-mini" title="Pause" @click="act('pause', job.id)">Ⅱ</button>
                <button class="icon-mini danger" title="Delete" @click="act('delete', job.id)">×</button>
              </span>
            </div>
          </template>

          <!-- TV -->
          <template v-else>
            <template v-for="season in group.seasons" :key="season.key">
              <div
                class="tree-row season"
                :class="{ collapsed: collapsedSeasons.has(season.key) }"
                @click="toggleSeason(season.key)"
              >
                <svg class="tree-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
                <span class="label">{{ season.label }}</span>
                <div class="meta">
                  <span>{{ season.count }} tasks</span>
                  <button class="icon-mini danger" title="Delete season tasks" @click.stop="deleteJobs(season.jobIds)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </button>
                </div>
              </div>
              <div class="tree-children">
                <template v-for="episode in season.episodes" :key="episode.key">
                  <div
                    class="tree-row episode"
                    :class="{ collapsed: collapsedEpisodes.has(episode.key) }"
                    @click="toggleEpisode(episode.key)"
                  >
                    <svg class="tree-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                    <span class="label">{{ episode.label }}</span>
                    <div class="meta">
                      <span :class="['pill', statusPill(episode.status)]">{{ episode.status }}</span>
                      <span style="font-family:var(--font-mono);font-size:11px;color:var(--text-3)">{{ episode.progress }}%</span>
                      <button class="icon-mini danger" title="Delete episode tasks" @click.stop="deleteJobs(episode.jobIds)">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    </div>
                  </div>
                  <div class="tree-children">
                    <div class="dl-thead-srv in-episode">
                      <span>File</span><span>Output</span><span>Status</span><span>Progress</span><span>Action</span>
                    </div>
                    <div v-for="job in episode.jobs" :key="job.id" class="dl-variant in-episode">
                      <span class="var-file">{{ job.save_path || job.hls_url || job.title }}</span>
                      <span class="var-types">
                        <span :class="['pill flat', outputModePill(job.output_mode)]">{{ job.output_mode.toUpperCase() }}</span>
                      </span>
                      <span>
                        <span :class="['pill', statusPill(job.status)]">{{ job.status }}</span>
                      </span>
                      <div class="var-prog">
                        <div :class="['var-prog-bar', progBarColor(job.status)]">
                          <span :style="{ width: pct(job) + '%' }"></span>
                        </div>
                        <div class="var-prog-meta">
                          <span class="a">{{ pct(job) }}%</span>
                          <span :class="statusTextClass(job.status)">{{ statusText(job) }}</span>
                        </div>
                      </div>
                      <span class="leaf-actions">
                        <button v-if="canResume(job)" class="icon-mini" title="Resume" @click="act('resume', job.id)">▶</button>
                        <button v-if="canPause(job)" class="icon-mini" title="Pause" @click="act('pause', job.id)">Ⅱ</button>
                        <button class="icon-mini danger" title="Delete" @click="act('delete', job.id)">×</button>
                      </span>
                    </div>
                  </div>
                </template>
              </div>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getPipeline, jobAction, bulkAction, type PipelineJob } from '../api'

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

interface DownloadGroup {
  key: string
  kind: 'movie' | 'tv'
  title: string
  status: string
  count: number
  avgPct: number | null
  jobs: PipelineJob[]
  seasons: SeasonGroup[]
  jobIds: string[]
}

// ── State ─────────────────────────────────────────────────────────────────────

const jobs = ref<PipelineJob[]>([])
const activeFilter = ref<'all' | 'running' | 'error'>('all')
const collapsedPkgs = ref<Set<string>>(new Set())
const collapsedSeasons = ref<Set<string>>(new Set())
const collapsedEpisodes = ref<Set<string>>(new Set())
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
    const key = `${job.kind}:${job.title}`
    const list = map.get(key) || []
    list.push(job)
    map.set(key, list)
  }

  const groups: DownloadGroup[] = [...map.entries()].map(([key, items]) => {
    const first = items[0]
    const kind = first.kind === 'movie' ? 'movie' : 'tv'
    const group: DownloadGroup = {
      key,
      kind,
      title: first.title,
      status: aggregateStatus(items),
      count: items.length,
      avgPct: null,
      jobs: [],
      seasons: [],
      jobIds: items.map(j => j.id),
    }

    if (kind === 'movie') {
      const { kept, hidden } = deduplicateByMode(items)
      hiddenJobs += hidden
      group.jobs = sortJobs(kept)
      group.count = kept.length
      group.avgPct = avgPct(kept)
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
          label: episode ? `Episode ${episode}` : 'Season pack',
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
  await jobAction(action, id)
  await load()
}

async function deleteJobs(ids: string[]) {
  if (!ids.length) return
  await jobAction('delete', ids.join(','))
  await load()
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

function toggleEpisode(key: string) {
  const s = new Set(collapsedEpisodes.value)
  if (s.has(key)) s.delete(key); else s.add(key)
  collapsedEpisodes.value = s
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

function progBarColor(status: string): string {
  if (status === 'error')  return 'red'
  if (status === 'paused') return 'amber'
  if (status === 'queued' || status === 'completed') return 'gray'
  return ''
}

function outputModePill(mode: string): string {
  if (mode === 'strm') return 'teal'
  return 'blue'
}

function statusText(job: PipelineJob): string {
  if (job.error) return job.error
  if (job.status === 'completed') return 'done'
  if (job.status === 'paused') return 'paused'
  if (job.status === 'queued') return 'waiting'
  if (job.status === 'running') return 'downloading'
  return job.status
}

function statusTextClass(status: string): string {
  if (status === 'running') return 'green'
  if (status === 'error') return 'red'
  if (status === 'paused') return 'amber'
  return ''
}

function canResume(job: PipelineJob): boolean {
  return ['paused', 'error', 'queued'].includes(job.status)
}

function canPause(job: PipelineJob): boolean {
  return ['running', 'queued'].includes(job.status)
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

.pkg-foot {
  padding: 10px 18px;
  font-family: var(--font-mono); font-size: 11.5px; color: var(--text-3);
  border-top: 1px solid var(--border); background: var(--bg-2);
  display: flex; align-items: center; justify-content: space-between;
}
</style>
