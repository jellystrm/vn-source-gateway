<template>
  <div class="test-page">
    <div class="page-head">
      <div>
        <h1>Test</h1>
        <p class="sub">Check service health, fake LinkGrabber entries, and trace source resolution from one place.</p>
      </div>
    </div>

    <div class="card health-card">
      <div class="card-head">
        <div>
          <h2>Health</h2>
          <p class="desc">Current reachability for media services and built-in source APIs.</p>
        </div>
      </div>
      <div class="card-body">
        <div class="test-grid">
          <div
            v-for="tile in tiles"
            :key="tile.name"
            class="test-tile"
            @click="runSingle(tile.name)"
          >
            <div class="test-tile-head">
              <span class="name">{{ tile.label }}</span>
              <span :class="['dot', tile.dotClass]"></span>
            </div>
            <span class="desc">
              <template v-if="tile.status === 'loading'">checking...</template>
              <template v-else-if="tile.status === 'ok'">{{ tile.url }} · {{ tile.latency }}ms</template>
              <template v-else-if="tile.status === 'warn'">{{ tile.url }} · {{ tile.latency }}ms</template>
              <template v-else-if="tile.status === 'error'">{{ tile.message || 'unreachable' }}</template>
              <template v-else>click to test</template>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="card testing-card">
      <div class="card-head">
        <div>
          <h2>Testing</h2>
          <p class="desc">Use TMDB metadata and optional overrides to exercise LinkGrabber and source resolution.</p>
        </div>
      </div>
      <div class="card-body">
        <div class="form-grid">
          <div class="field">
            <label>TMDB ID</label>
            <input v-model="tmdbId" class="input mono" type="number" :placeholder="defaults.tmdbId" />
          </div>
          <div class="field">
            <label>Media type</label>
            <select v-model="mediaType" class="select">
              <option value="movie">Movie</option>
              <option value="tv">TV Series</option>
            </select>
          </div>
          <div class="field">
            <label>Title</label>
            <input v-model="title" class="input" :placeholder="defaults.title" />
          </div>
          <div class="field">
            <label>Year</label>
            <input v-model="year" class="input mono" type="number" :placeholder="defaults.year" />
          </div>
          <template v-if="mediaType === 'tv'">
            <div class="field">
              <label>Season</label>
              <input v-model="season" class="input mono" type="number" placeholder="1" />
            </div>
            <div class="field">
              <label>Episode</label>
              <input v-model="episode" class="input mono" type="number" placeholder="1" />
            </div>
          </template>
        </div>

        <div class="action-row">
          <button class="btn" :disabled="testingGrabber" @click="fakeGrabber">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>
            {{ testingGrabber ? 'Adding...' : 'Test Grabber' }}
          </button>
          <button class="btn primary" :disabled="resolving" @click="resolveSources">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            {{ resolving ? 'Resolving...' : 'Resolve sources' }}
          </button>
        </div>

        <div class="run-output">
          <div class="run-output-head">
            <div>
              <h3>Run output <span>{{ lastRun ? '· ' + lastRun : '' }}</span></h3>
              <p class="desc">{{ outputDescription }}</p>
            </div>
            <button class="btn ghost sm" @click="clearLog">Clear</button>
          </div>
          <div class="testlog" ref="logEl">
            <div v-if="!logLines.length" class="l-info">
              <span class="ts">-</span>No test action has run yet.
            </div>
            <div v-for="(line, i) in logLines" :key="i" :class="line.cls">
              <span class="ts">{{ line.ts }}</span>{{ line.text }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, computed } from 'vue'
import { getHealth, sourceTest, testGrabber, type HealthResult, type SourceTestRequest, type SourceResult } from '../api'

interface Tile {
  name: string
  label: string
  url: string
  status: 'idle' | 'loading' | 'ok' | 'warn' | 'error' | 'unknown'
  dotClass: string
  latency: number | null
  message: string
}

interface LogLine { cls: string; ts: string; text: string }

const SERVICES: { name: string; label: string }[] = [
  { name: 'radarr',  label: 'Radarr'  },
  { name: 'sonarr',  label: 'Sonarr'  },
  { name: 'jellyfin',label: 'Jellyfin'},
  { name: 'kkphim',  label: 'kkphim'  },
  { name: 'ophim',   label: 'ophim'   },
  { name: 'nguonc',  label: 'nguonc'  },
]

const tiles = reactive<Tile[]>(
  SERVICES.map(s => ({
    ...s, url: '', status: 'idle', dotClass: 'gray', latency: null, message: '',
  }))
)

const mediaType = ref<'movie' | 'tv'>('movie')
const tmdbId = ref('')
const title = ref('')
const year = ref('')
const season = ref('')
const episode = ref('')

const healthRunning = ref(false)
const testingGrabber = ref(false)
const resolving = ref(false)
const logLines = ref<LogLine[]>([])
const lastRun = ref('')
const outputMode = ref<'idle' | 'grabber' | 'resolve'>('idle')
const logEl = ref<HTMLElement | null>(null)

const DEFAULTS = {
  movie: { tmdbId: '27205', title: 'Inception', year: '2010' },
  tv: { tmdbId: '37854', title: 'One Piece', year: '1999' },
} as const

const defaults = computed(() => DEFAULTS[mediaType.value])
const outputDescription = computed(() => {
  if (outputMode.value === 'grabber') return 'Test Grabber result and generated fake grab options.'
  if (outputMode.value === 'resolve') return 'Resolve Sources result with source URLs and trace lines.'
  return 'Run Test Grabber or Resolve sources to see the matching output here.'
})

const payload = computed<SourceTestRequest>(() => {
  const p: SourceTestRequest = {
    media_type: mediaType.value,
  }
  const id = intVal(valueOrDefault(tmdbId.value, defaults.value.tmdbId))
  const yr = intVal(valueOrDefault(year.value, defaults.value.year))
  if (id !== undefined) p.tmdb_id = id
  p.title = valueOrDefault(title.value, defaults.value.title)
  if (yr !== undefined) p.year = yr
  if (mediaType.value === 'tv') {
    p.season = intVal(season.value) ?? 1
    p.episode = intVal(episode.value) ?? 1
  }
  return p
})

function valueOrDefault(value: string, fallback: string) {
  return value.trim() || fallback
}

function intVal(value: string): number | undefined {
  const n = Number(value)
  return Number.isFinite(n) && value.trim() !== '' ? n : undefined
}

function now() {
  return new Date().toTimeString().slice(0, 8)
}

function addLog(cls: string, text: string) {
  logLines.value.push({ cls, ts: now(), text })
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  })
}

function clearLog() {
  logLines.value = []
  lastRun.value = ''
  outputMode.value = 'idle'
}

function beginOutput(mode: 'grabber' | 'resolve') {
  outputMode.value = mode
  logLines.value = []
  lastRun.value = ''
}

function applyResult(name: string, result: HealthResult, log = true) {
  const tile = tiles.find(t => t.name === name)
  if (!tile) return
  tile.url = result.url || ''
  tile.latency = result.latency
  tile.message = result.message || ''
  tile.status = result.status

  if (result.status === 'ok') {
    tile.dotClass = 'green'
    if (log) addLog('l-ok', `${name.padEnd(8)} -> ${result.url} · ${result.latency}ms`)
  } else if (result.status === 'warn') {
    tile.dotClass = 'amber'
    if (log) addLog('l-warn', `${name.padEnd(8)} -> ${result.url} · ${result.latency}ms`)
  } else if (result.status === 'error') {
    tile.dotClass = 'red'
    if (log) addLog('l-err', `${name.padEnd(8)} -> ${result.message || 'unreachable'}`)
  } else {
    tile.dotClass = 'gray'
    if (log) addLog('l-info', `${name.padEnd(8)} -> not configured`)
  }
}

async function runHealth(log = false) {
  if (healthRunning.value) return
  healthRunning.value = true
  tiles.forEach(t => { t.status = 'loading'; t.dotClass = 'gray' })
  try {
    const results = await getHealth()
    for (const [name, result] of Object.entries(results)) applyResult(name, result, log)
  } catch (e) {
    if (log) addLog('l-err', `Health check failed: ${e}`)
    tiles.forEach(t => { t.status = 'idle'; t.dotClass = 'gray' })
  } finally {
    healthRunning.value = false
  }
}

async function runSingle(name: string) {
  const tile = tiles.find(t => t.name === name)
  if (!tile) return
  tile.status = 'loading'; tile.dotClass = 'gray'
  try {
    const results = await getHealth()
    const result = results[name]
    if (result) applyResult(name, result, false)
  } catch (e) {
    tile.status = 'error'; tile.dotClass = 'red'
    tile.message = String(e)
  }
}

async function fakeGrabber() {
  testingGrabber.value = true
  beginOutput('grabber')
  addLog('l-info', `Adding fake LinkGrabber entry for ${describePayload()}...`)
  try {
    const res = await testGrabber(payload.value)
    addLog(res.count > 0 ? 'l-ok' : 'l-warn', `LinkGrabber fake event added with ${res.count} grab option(s)`)
    for (const item of res.results.slice(0, 8)) addLog('l-info', `grab: ${item}`)
    if (res.results.length > 8) addLog('l-info', `... ${res.results.length - 8} more`)
    lastRun.value = 'just now'
  } catch (e) {
    addLog('l-err', `Test Grabber failed: ${e}`)
  } finally {
    testingGrabber.value = false
  }
}

async function resolveSources() {
  resolving.value = true
  beginOutput('resolve')
  addLog('l-info', `Resolving ${describePayload()} on kkphim, ophim, nguonc...`)
  try {
    const results = await sourceTest(payload.value)
    for (const name of ['kkphim', 'ophim', 'nguonc']) {
      const result = results[name]
      if (!result) continue
      logSourceResult(name, result)
    }
    lastRun.value = 'just now'
  } catch (e) {
    addLog('l-err', `Resolve failed: ${e}`)
  } finally {
    resolving.value = false
  }
}

function logSourceResult(name: string, result: SourceResult) {
  if (result.status === 'ok') {
    const urls = result.urls || (result.url ? [{ url: result.url }] : [])
    const found = result.episodes ? `${result.found || 0}/${result.total || 0} episode(s)` : `${urls.length || 1} URL(s)`
    addLog('l-ok', `${name.padEnd(8)} -> ${found}`)
    for (const hit of urls.slice(0, 6)) {
      const label = [hit.server, hit.name].filter(Boolean).join(' / ')
      addLog('l-info', `${name.padEnd(8)}    ${label ? label + ' · ' : ''}${hit.url}`)
    }
    if (result.episodes) {
      for (const ep of result.episodes.filter(e => e.url).slice(0, 12)) {
        addLog('l-info', `${name.padEnd(8)}    E${String(ep.num).padStart(2, '0')} · ${ep.url}`)
      }
    }
  } else {
    addLog('l-err', `${name.padEnd(8)} -> ${result.message || 'Not found'}`)
  }
  for (const line of (result.log || []).slice(0, 18)) addLog('l-trace', `${name.padEnd(8)}    ${line}`)
}

function describePayload() {
  const p = payload.value
  const id = p.tmdb_id ? `TMDB ${p.tmdb_id}` : 'no TMDB'
  const name = p.title ? `"${p.title}"` : id
  if (p.media_type === 'tv') return `${name} S${String(p.season || 1).padStart(2, '0')}E${String(p.episode || 1).padStart(2, '0')}`
  return name
}

onMounted(() => runHealth(false))
</script>

<style scoped>
.test-page > .card + .card {
  margin-top: 18px;
}
.test-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.test-tile {
  min-height: 86px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 13px 14px;
  cursor: pointer;
  transition: border-color .12s, background .12s;
}
.test-tile:hover { border-color: var(--border-2); background: var(--surface-2); }
.test-tile-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.test-tile .name { font-weight: 700; font-size: 13px; }
.test-tile .desc {
  display: block;
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
  word-break: break-word;
}
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; background: var(--text-3); }
.dot.green { background: var(--green); box-shadow: 0 0 9px var(--green); }
.dot.amber { background: var(--accent); box-shadow: 0 0 9px var(--accent); }
.dot.red { background: var(--red); box-shadow: 0 0 9px var(--red); }
.dot.gray { background: var(--text-3); opacity: .55; }
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.field label { font-size: 12px; font-weight: 700; color: var(--text-2); }
.input, .select {
  height: 38px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: 0 11px;
  font-family: var(--font-sans);
  font-size: 13px;
  outline: none;
}
.input:focus, .select:focus { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(94,224,189,.12); }
.action-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.run-output {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
}
.run-output-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.run-output h3 {
  margin: 0;
  font-size: 14px;
}
.run-output h3 span {
  color: var(--text-3);
  font-weight: 500;
}
.testlog {
  height: 340px;
  overflow: auto;
  background: #070a0f;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.55;
}
.testlog > div { white-space: pre-wrap; word-break: break-word; }
.ts { color: var(--text-3); margin-right: 9px; }
.l-ok { color: var(--green); }
.l-warn { color: var(--accent); }
.l-err { color: var(--red); }
.l-info { color: var(--text-2); }
.l-trace { color: var(--text-3); }
@media (max-width: 900px) {
  .form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
