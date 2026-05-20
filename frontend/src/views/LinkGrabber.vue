<template>
  <div>
    <div class="page-head">
      <div>
        <h1>LinkGrabber</h1>
        <p class="sub">Recent indexer activity grouped by media, season, episode, and source link.</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn" @click="load">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh
        </button>
      </div>
    </div>

    <div v-if="!grabEvents.length" class="empty-state">
      <h3>No activity yet</h3>
      <p>Start the worker or let Radarr / Sonarr hand queries off automatically once configured.</p>
    </div>

    <div v-else class="tree-card">
      <details v-for="group in mediaGroups" :key="group.key" class="tree-node media-node" open>
        <summary>
          <span class="chev"></span>
          <span class="media-icon">{{ group.kind === 'movie' ? 'M' : 'TV' }}</span>
          <span class="node-title">{{ group.title }}</span>
          <span class="node-meta">{{ group.linkCount }} links</span>
          <span :class="['pill', group.status === 'error' ? 'red' : 'green']">{{ group.status }}</span>
          <span class="node-time">{{ relTime(group.ts) }}</span>
        </summary>

        <div class="tree-children">
          <template v-if="group.kind === 'movie'">
            <div v-for="link in group.links" :key="link.key" class="leaf-row">
              <div class="leaf-main">
                <span class="leaf-title">{{ link.label }}</span>
                <span class="leaf-sub">{{ link.title }}</span>
              </div>
              <GrabActions :link="link" @grab="grab" />
            </div>
          </template>

          <template v-else>
            <details v-for="season in group.seasons" :key="season.key" class="tree-node season-node" open>
              <summary>
                <span class="chev"></span>
                <span class="node-title">{{ season.label }}</span>
                <span class="node-meta">{{ season.linkCount }} links</span>
              </summary>
              <div class="tree-children">
                <details v-for="episode in season.episodes" :key="episode.key" class="tree-node episode-node" open>
                  <summary>
                    <span class="chev"></span>
                    <span class="node-title">{{ episode.label }}</span>
                    <span class="node-meta">{{ episode.links.length }} links</span>
                  </summary>
                  <div class="tree-children">
                    <div v-for="link in episode.links" :key="link.key" class="leaf-row">
                      <div class="leaf-main">
                        <span class="leaf-title">{{ link.label }}</span>
                        <span class="leaf-sub">{{ link.title }}</span>
                      </div>
                      <GrabActions :link="link" @grab="grab" />
                    </div>
                  </div>
                </details>
              </div>
            </details>
          </template>

          <div v-if="group.detail" class="event-detail">{{ group.detail }}</div>
        </div>
      </details>

      <div class="card-foot">
        <span style="font-size:12.5px;color:var(--text-3)">{{ grabEvents.length }} grab lists · {{ grabsCount }} links</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, onUnmounted, ref, type PropType } from 'vue'
import { useRouter } from 'vue-router'
import { getActivity, manualGrab, type ActivityEvent, type GrabToken } from '../api'

interface LinkOption {
  key: string
  title: string
  label: string
  strmToken: string
  downloadToken: string
}

interface EpisodeNode { key: string; label: string; links: LinkOption[] }
interface SeasonNode { key: string; label: string; episodes: EpisodeNode[]; linkCount: number }
interface MediaNode {
  key: string
  kind: 'movie' | 'tv'
  title: string
  status: string
  detail: string
  ts: number
  links: LinkOption[]
  seasons: SeasonNode[]
  linkCount: number
}

const GrabActions = defineComponent({
  props: {
    link: { type: Object as PropType<LinkOption>, required: true },
  },
  emits: ['grab'],
  setup(props, { emit }) {
    return () => h('div', { class: 'grab-actions' }, [
      h('button', {
        class: 'grab-btn',
        title: 'Create STRM file',
        onClick: () => emit('grab', props.link.strmToken, 'strm'),
      }, 'STRM'),
      h('button', {
        class: 'grab-btn grab-btn-dl',
        title: 'Download HLS to media file',
        onClick: () => emit('grab', props.link.downloadToken, 'hls-dl'),
      }, 'HLS-DL'),
    ])
  },
})

const events = ref<ActivityEvent[]>([])
const router = useRouter()
let timer: ReturnType<typeof setInterval>

const grabEvents = computed(() => events.value.filter(e => e.kind === 'search' && e.grabs.length > 0))
const grabsCount = computed(() => grabEvents.value.reduce((sum, e) => sum + e.grabs.length, 0))
const mediaGroups = computed(() => grabEvents.value.map(toMediaNode))

async function load() {
  try { events.value = await getActivity() } catch {}
}

async function grab(token: string, mode: string) {
  await manualGrab(token, mode)
  await router.push('/downloads')
}

function toMediaNode(ev: ActivityEvent): MediaNode {
  const first = ev.grabs[0]
  const kind: 'movie' | 'tv' = isTvEvent(ev, first) ? 'tv' : 'movie'
  const title = mediaTitle(ev, first)
  const node: MediaNode = {
    key: `${ev.ts}:${ev.title}`,
    kind,
    title,
    status: ev.status || 'ok',
    detail: ev.detail,
    ts: ev.ts,
    links: [],
    seasons: [],
    linkCount: ev.grabs.length,
  }

  if (kind === 'movie') {
    node.links = mergeLinks(ev.grabs)
    node.linkCount = node.links.length
    return node
  }

  const seasonMap = new Map<number, GrabToken[]>()
  for (const grab of ev.grabs) {
    const season = grab.season || parseSeasonEpisode(grab.title).season || 1
    const list = seasonMap.get(season) || []
    list.push(grab)
    seasonMap.set(season, list)
  }
  node.seasons = [...seasonMap.entries()]
    .sort(([a], [b]) => a - b)
    .map(([season, grabs]) => {
      const episodeMap = new Map<number, GrabToken[]>()
      for (const grab of grabs) {
        const parsed = parseSeasonEpisode(grab.title)
        const ep = grab.episode || parsed.episode || 0
        const list = episodeMap.get(ep) || []
        list.push(grab)
        episodeMap.set(ep, list)
      }
      const episodes = [...episodeMap.entries()]
        .sort(([a], [b]) => a - b)
        .map(([episode, epGrabs]) => ({
          key: `${node.key}:s${season}:e${episode}`,
          label: episode ? `Episode ${episode}` : 'Season pack',
          links: mergeLinks(epGrabs),
        }))
      return {
        key: `${node.key}:s${season}`,
        label: `Season ${season}`,
        episodes,
        linkCount: episodes.reduce((sum, ep) => sum + ep.links.length, 0),
      }
    })
  node.linkCount = node.seasons.reduce((sum, season) => sum + season.linkCount, 0)
  return node
}

function mergeLinks(grabs: GrabToken[]): LinkOption[] {
  const map = new Map<string, LinkOption>()
  for (const grab of grabs) {
    const key = [
      grab.media_title || stripMode(grab.title),
      grab.season || '',
      grab.episode || '',
      grab.source || '',
      grab.server || '',
      stripMode(grab.title),
    ].join('|')
    const existing = map.get(key)
    const mode = grab.output_mode === 'download' ? 'download' : 'strm'
    if (existing) {
      if (mode === 'download') existing.downloadToken = grab.token
      else existing.strmToken = grab.token
      continue
    }
    map.set(key, {
      key,
      title: grab.title,
      label: linkLabel(grab),
      strmToken: grab.token,
      downloadToken: grab.token,
    })
  }
  return [...map.values()]
}

function linkLabel(grab: GrabToken) {
  const parts = [grab.source, grab.server].filter(Boolean)
  return parts.length ? parts.join(' / ') : stripMode(grab.title)
}

function stripMode(title: string) {
  return title.replace(/\s+\[(STRM|HLS-DL)\]\s*$/i, '')
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
.tree-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  overflow: hidden;
}
.tree-node {
  border-bottom: 1px solid var(--border);
}
.tree-node:last-child { border-bottom: 0; }
.tree-node > summary {
  display: grid;
  grid-template-columns: 18px auto minmax(180px, 1fr) auto auto auto;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  list-style: none;
}
.tree-node > summary::-webkit-details-marker { display: none; }
.tree-node > summary:hover { background: var(--surface-2); }
.season-node > summary {
  grid-template-columns: 18px minmax(160px, 1fr) auto;
  padding: 9px 12px;
}
.episode-node > summary {
  grid-template-columns: 18px minmax(160px, 1fr) auto;
  padding: 8px 12px;
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
.node-meta, .node-time {
  color: var(--text-3);
  font-size: 12px;
  white-space: nowrap;
}
.tree-children {
  margin-left: 28px;
  border-left: 1px solid var(--border);
  padding: 0 12px 10px;
}
.leaf-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  margin-top: 7px;
  background: rgba(255,255,255,.025);
  border: 1px solid var(--border);
  border-radius: 7px;
}
.leaf-main { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.leaf-title { color: var(--text); font-size: 12.5px; font-weight: 650; }
.leaf-sub {
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-detail {
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 8px 10px 0;
}
.grab-actions { display: flex; gap: 5px; }
.grab-btn {
  min-width: 72px;
  font-size: 11px;
  font-weight: 800;
  background: var(--accent);
  border: 1px solid rgba(245,166,35,.55);
  border-radius: 6px;
  color: #15100a;
  padding: 6px 10px;
  cursor: pointer;
  transition: filter .12s, transform .12s;
  white-space: nowrap;
  font-family: var(--font-sans);
}
.grab-btn:hover { filter: brightness(1.08); transform: translateY(-1px); }
.grab-btn-dl {
  background: var(--surface-2);
  border-color: var(--border-strong);
  color: var(--text);
}
.grab-btn-dl:hover { background: var(--surface-3); }
@media (max-width: 900px) {
  .tree-node > summary { grid-template-columns: 18px auto minmax(120px, 1fr) auto; }
  .tree-node > summary .pill, .node-time { display: none; }
  .leaf-row { grid-template-columns: 1fr; }
}
</style>
