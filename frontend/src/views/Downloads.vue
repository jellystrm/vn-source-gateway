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
        <span class="filter-tag">All <b>{{ jobs.length }}</b></span>
        <span class="filter-tag green-v">Running <b>{{ counts.running }}</b></span>
        <span class="filter-tag red-v">Errors <b>{{ counts.error }}</b></span>
      </div>
    </div>

    <div v-if="!jobs.length" class="empty-state">
      <h3>No download tasks yet</h3>
      <p>When a source resolves to a stream, it shows up here with live progress and status.</p>
    </div>

    <div v-else class="tree-card">
      <details v-for="group in downloadGroups" :key="group.key" class="tree-node media-node" open>
        <summary>
          <span class="chev"></span>
          <span class="media-icon">{{ group.kind === 'movie' ? 'M' : 'TV' }}</span>
          <span class="node-title">{{ group.title }}</span>
          <span class="node-meta">{{ group.count }} tasks</span>
          <span :class="['pill', statusPill(group.status)]">{{ group.status }}</span>
        </summary>

        <div class="tree-children">
          <template v-if="group.kind === 'movie'">
            <JobRow v-for="job in group.jobs" :key="job.id" :job="job" @act="act" />
          </template>

          <template v-else>
            <details v-for="season in group.seasons" :key="season.key" class="tree-node season-node" open>
              <summary>
                <span class="chev"></span>
                <span class="node-title">{{ season.label }}</span>
                <span class="node-meta">{{ season.count }} tasks</span>
              </summary>
              <div class="tree-children compact-children">
                <details v-for="episode in season.episodes" :key="episode.key" class="tree-node episode-node">
                  <summary>
                    <span class="chev"></span>
                    <span class="node-title">{{ episode.label }}</span>
                    <span class="node-meta">{{ episode.jobs.length }} tasks</span>
                    <span :class="['pill', statusPill(episode.status)]">{{ episode.status }}</span>
                    <span class="episode-progress">{{ episode.progress }}%</span>
                  </summary>
                  <div class="tree-children">
                    <JobRow v-for="job in episode.jobs" :key="job.id" :job="job" @act="act" />
                  </div>
                </details>
              </div>
            </details>
          </template>
        </div>
      </details>

      <div class="card-foot">
        <span style="font-size:12.5px;color:var(--text-3)">
          {{ jobs.length }} tasks · {{ counts.running }} running · {{ counts.error }} errors · {{ counts.completed }} done
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, onUnmounted, ref, type PropType } from 'vue'
import { getPipeline, jobAction, bulkAction, type PipelineJob } from '../api'

interface EpisodeGroup { key: string; label: string; jobs: PipelineJob[]; status: string; progress: number }
interface SeasonGroup { key: string; label: string; episodes: EpisodeGroup[]; count: number }
interface DownloadGroup {
  key: string
  kind: 'movie' | 'tv'
  title: string
  status: string
  count: number
  jobs: PipelineJob[]
  seasons: SeasonGroup[]
}

const JobRow = defineComponent({
  props: {
    job: { type: Object as PropType<PipelineJob>, required: true },
  },
  emits: ['act'],
  setup(props, { emit }) {
    const pct = () => `${(props.job.progress * 100).toFixed(0)}%`
    const canResume = () => ['paused', 'error', 'queued'].includes(props.job.status)
    const canPause = () => ['running', 'queued'].includes(props.job.status)
    return () => h('div', { class: 'job-row' }, [
      h('div', { class: 'job-main' }, [
        h('div', { class: 'job-title' }, [
          props.job.output_mode,
          props.job.hls_url ? h('span', { class: 'job-tag' }, 'resolved') : null,
        ]),
        props.job.error
          ? h('div', { class: 'job-sub error-text' }, props.job.error)
          : props.job.save_path && props.job.status === 'completed'
            ? h('div', { class: 'job-sub done-text' }, `Done · ${props.job.save_path}`)
            : h('div', { class: 'job-sub' }, props.job.hls_url || 'Waiting for source resolution'),
      ]),
      h('div', { class: ['prog', progColor(props.job.status)] }, [
        h('div', { class: 'prog-bar' }, [h('span', { style: { width: pct() } })]),
        h('div', { class: 'prog-meta' }, [
          h('span', { class: 'a' }, pct()),
          h('span', props.job.status),
        ]),
      ]),
      h('div', { class: 'job-actions' }, [
        canResume() ? h('button', { class: 'icon-mini', title: 'Resume', onClick: () => emit('act', 'resume', props.job.id) }, '▶') : null,
        canPause() ? h('button', { class: 'icon-mini', title: 'Pause', onClick: () => emit('act', 'pause', props.job.id) }, 'Ⅱ') : null,
        h('button', { class: 'icon-mini danger', title: 'Delete', onClick: () => emit('act', 'delete', props.job.id) }, '×'),
      ]),
    ])
  },
})

const jobs = ref<PipelineJob[]>([])
let timer: ReturnType<typeof setInterval>

const counts = computed(() => ({
  running:   jobs.value.filter(j => j.status === 'running').length,
  error:     jobs.value.filter(j => j.status === 'error').length,
  completed: jobs.value.filter(j => j.status === 'completed').length,
}))

const downloadGroups = computed<DownloadGroup[]>(() => {
  const map = new Map<string, PipelineJob[]>()
  for (const job of jobs.value) {
    const key = `${job.kind}:${job.title}`
    const list = map.get(key) || []
    list.push(job)
    map.set(key, list)
  }
  return [...map.entries()].map(([key, items]) => {
    const first = items[0]
    const kind = first.kind === 'movie' ? 'movie' : 'tv'
    const group: DownloadGroup = {
      key,
      kind,
      title: first.title,
      status: aggregateStatus(items),
      count: items.length,
      jobs: [],
      seasons: [],
    }
    if (kind === 'movie') {
      group.jobs = sortJobs(items)
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
      const episodes = [...episodeMap.entries()].sort(([a], [b]) => a - b).map(([episode, epJobs]) => ({
        key: `${key}:s${season}:e${episode}`,
        label: episode ? `Episode ${episode}` : 'Season pack',
        jobs: sortJobs(epJobs),
        status: aggregateStatus(epJobs),
        progress: Math.round((epJobs.reduce((sum, job) => sum + job.progress, 0) / Math.max(epJobs.length, 1)) * 100),
      }))
      return {
        key: `${key}:s${season}`,
        label: `Season ${season}`,
        episodes,
        count: seasonJobs.length,
      }
    })
    return group
  })
})

async function load() {
  try { jobs.value = await getPipeline() } catch {}
}

async function act(action: 'resume' | 'pause' | 'delete', id: string) {
  await jobAction(action, id)
  await load()
}

async function bulk(action: 'resume_all' | 'pause_all' | 'clear_done') {
  await bulkAction(action)
  await load()
}

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

function statusPill(status: string) {
  if (status === 'running')   return 'green'
  if (status === 'completed') return 'teal'
  if (status === 'error')     return 'red'
  if (status === 'paused')    return 'amber'
  return 'gray'
}

function progColor(status: string) {
  if (status === 'error')  return 'red'
  if (status === 'paused') return 'amber'
  return ''
}

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.filter-tag {
  font-size: 12px; color: var(--text-3); padding: 2px 8px;
}
.filter-tag b { font-weight: 600; color: var(--text-2); margin-left: 3px; }
.filter-tag.green-v b { color: var(--green); }
.filter-tag.red-v b   { color: var(--red); }
.tree-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
}
.tree-node { border-bottom: 1px solid var(--border); }
.tree-node:last-child { border-bottom: 0; }
.tree-node > summary {
  display: grid;
  grid-template-columns: 18px auto minmax(180px, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  list-style: none;
}
.tree-node > summary::-webkit-details-marker { display: none; }
.tree-node > summary:hover { background: var(--surface-2); }
.season-node > summary,
.episode-node > summary {
  grid-template-columns: 18px minmax(160px, 1fr) auto;
  padding: 9px 12px;
}
.episode-node > summary {
  grid-template-columns: 18px minmax(160px, 1fr) auto auto auto;
  padding: 6px 10px;
}
.chev::before {
  content: "›";
  display: inline-block;
  color: var(--text-3);
  transition: transform .12s;
}
details[open] > summary .chev::before { transform: rotate(90deg); }
.media-icon {
  min-width: 28px;
  height: 22px;
  border-radius: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--blue-soft);
  color: var(--blue);
  font-size: 11px;
  font-weight: 800;
}
.node-title { font-weight: 700; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-meta { color: var(--text-3); font-size: 12px; white-space: nowrap; }
.tree-children {
  margin-left: 28px;
  border-left: 1px solid var(--border);
  padding: 0 12px 10px;
}
.compact-children {
  padding-bottom: 6px;
}
.episode-node {
  border-bottom: 0;
}
.episode-node > summary:hover {
  background: rgba(255,255,255,.025);
}
.episode-progress {
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 11px;
  min-width: 38px;
  text-align: right;
}
.job-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(180px, 260px) auto;
  align-items: center;
  gap: 14px;
  padding: 7px 9px;
  margin-top: 5px;
  background: rgba(255,255,255,.025);
  border: 1px solid var(--border);
  border-radius: 7px;
}
.job-main { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.job-title { display: flex; align-items: center; gap: 6px; font-weight: 700; font-family: var(--font-mono); font-size: 11px; }
.job-sub {
  color: var(--text-3);
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.job-tag {
  color: var(--green);
  background: var(--green-soft);
  border: 1px solid rgba(74,222,128,.22);
  border-radius: 4px;
  padding: 1px 5px;
  font-family: var(--font-sans);
  font-size: 10px;
}
.error-text { color: var(--red); }
.done-text { color: var(--green); }
.job-actions { display: flex; gap: 5px; justify-content: flex-end; }
@media (max-width: 900px) {
  .tree-node > summary { grid-template-columns: 18px auto minmax(120px, 1fr) auto; }
  .tree-node > summary .pill { display: none; }
  .episode-node > summary { grid-template-columns: 18px minmax(120px, 1fr) auto auto; }
  .job-row { grid-template-columns: 1fr; }
  .job-actions { justify-content: flex-start; }
}
</style>
