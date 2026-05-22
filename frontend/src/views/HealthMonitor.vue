<template>
  <div>
    <div class="page-head">
      <div>
        <h1>Testing sandbox</h1>
        <p class="sub">Dry-run sandbox to simulate the LinkGrabber → resolve flow without touching your queue.</p>
      </div>
      </div>

    <div class="fcard" style="margin-bottom:18px">
      <div class="fcard-head">
        <div class="fcard-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </div>
        <div>
          <h3>Media reference</h3>
          <p class="desc">Switch to TV Series to enter season / episode.</p>
        </div>
        <div style="margin-left:auto">
          <div class="seg-radio">
            <button :class="{ active: mediaType === 'movie' }" @click="mediaType = 'movie'">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="7" y1="4" x2="7" y2="20"/><line x1="17" y1="4" x2="17" y2="20"/></svg>
              Movie
            </button>
            <button :class="{ active: mediaType === 'tv' }" @click="mediaType = 'tv'">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2"/><polyline points="17 2 12 7 7 2"/></svg>
              TV Series
            </button>
          </div>
        </div>
      </div>
      <div class="fcard-body">
        <div class="form">
          <template v-if="mediaType === 'tv'">
            <div class="field">
              <label>TVDB ID <span class="hint">primary · like Sonarr</span></label>
              <input v-model="tvdbId" class="input mono" type="number" :placeholder="defaults.tvdbId || 'optional'" />
            </div>
          </template>
          <div class="field">
            <label>TMDB ID <span class="hint">{{ mediaType === 'tv' ? 'optional · auto-resolved from TVDB' : 'required' }}</span></label>
            <input v-model="tmdbId" class="input mono" type="number" :placeholder="mediaType === 'tv' ? 'auto' : defaults.tmdbId" />
          </div>
          <div class="field">
            <label>Title <span class="hint">fuzzy match</span></label>
            <input v-model="title" class="input" :placeholder="defaults.title" />
          </div>
          <template v-if="mediaType === 'tv'">
            <div class="field">
              <label>Season <span class="hint">optional</span></label>
              <input v-model="season" class="input mono" type="number" placeholder="all" />
            </div>
            <div class="field">
              <label>Episode <span class="hint">optional</span></label>
              <input v-model="episode" class="input mono" type="number" placeholder="all" />
            </div>
          </template>
        </div>
      </div>
      <div class="fcard-foot">
        <span style="display:inline-flex;align-items:center;gap:6px;font-size:12px">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          Dry-run · nothing is queued or written to disk
        </span>
        <div style="margin-left:auto;display:flex;gap:8px">
          <button v-if="resolving" class="btn ghost sm" @click="cancelResolve">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
            Cancel
          </button>
          <button class="btn sm" :disabled="resolving" @click="resolveSources">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            {{ resolving ? 'Resolving…' : 'Test all sources' }}
          </button>
          <button class="btn primary sm" :disabled="testingIndexer" @click="testTorznab">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
            {{ testingIndexer ? 'Testing…' : 'Test indexer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Resolve on source ── -->
    <div class="section-h">
      <div>
        <h2>Resolve on source <span class="num-pill">3 sources</span></h2>
        <p class="desc">Run the resolver pipeline against one source at a time. Useful for diagnosing "No match" errors.</p>
      </div>
    </div>

    <div class="fcard" style="margin-bottom:18px">
      <div class="fcard-body" style="padding:14px 16px">
        <div
          v-for="(src, i) in srcTests"
          :key="src.name"
          class="src-test"
        >
          <div class="src-test-badge">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="src-test-meta">
            <div class="n">
              {{ src.name }}
              <span v-if="i === 0" class="pill teal flat">Primary</span>
            </div>
            <div class="u">{{ src.url }}</div>
          </div>
          <div class="actions">
            <span class="result" :class="src.resultClass">{{ src.resultText }}</span>
            <button class="btn sm" :disabled="src.loading" @click="testSingleSource(src.name)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              {{ src.loading ? 'Testing…' : 'Test resolve' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Run output ── -->
    <div class="section-h">
      <div>
        <h2>Run output</h2>
        <p class="desc">Live log from health check + sandbox actions in this session.</p>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn ghost sm" @click="copyLog">Copy</button>
        <button class="btn ghost sm" @click="clearLog">Clear</button>
      </div>
    </div>

    <div class="fcard">
      <div style="padding:14px 16px">
        <div class="testlog" ref="logEl">
          <div v-if="!logLines.length" class="l-info">
            <span class="ts">–</span>No test action has run yet. Run a health check or use the sandbox above.
          </div>
          <div v-for="(line, i) in logLines" :key="i" :class="line.cls">
            <span class="ts">{{ line.ts }}</span>{{ line.text }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { sourceTest, testIndexer, type SourceTestRequest, type SourceResult } from '../api'

interface SrcTest {
  name: string; url: string
  loading: boolean; resultText: string; resultClass: string
}
interface LogLine { cls: string; ts: string; text: string }

const SRC_URLS: Record<string, string> = {
  kkphim: 'https://phimapi.com',
  ophim:  'https://ophim1.com',
  nguonc: 'https://phim.nguonc.com',
}

const srcTests = reactive<SrcTest[]>(
  ['kkphim', 'ophim', 'nguonc'].map(name => ({
    name, url: SRC_URLS[name] || '',
    loading: false, resultText: '· not run yet', resultClass: '',
  }))
)

const mediaType     = ref<'movie' | 'tv'>('movie')
const tmdbId        = ref('')
const tvdbId        = ref('')
const title         = ref('')
const year          = ref('')
const season        = ref('')
const episode       = ref('')
const testingIndexer = ref(false)
const resolving      = ref(false)
let   activeAbort:  AbortController | null = null

function cancelResolve() {
  activeAbort?.abort()
  activeAbort = null
}

onUnmounted(() => { cancelResolve() })
const logLines       = ref<LogLine[]>([])
const logEl          = ref<HTMLElement | null>(null)

const DEFAULTS = {
  movie: { tmdbId: '27205', tvdbId: '',      title: 'Inception',  year: '2010' },
  tv:    { tmdbId: '37854', tvdbId: '81797', title: 'One Piece',  year: '1999' },
} as const

const defaults = computed(() => DEFAULTS[mediaType.value])

function valueOrDefault(value: string, fallback: string) { return value.trim() || fallback }
function intVal(value: string): number | undefined {
  const n = Number(value)
  return Number.isFinite(n) && value.trim() !== '' ? n : undefined
}

const payload = computed<SourceTestRequest>(() => {
  const p: SourceTestRequest = { media_type: mediaType.value }
  const id = intVal(valueOrDefault(tmdbId.value, defaults.value.tmdbId))
  const yr = intVal(valueOrDefault(year.value, defaults.value.year))
  if (id !== undefined) p.tmdb_id = id
  p.title = valueOrDefault(title.value, defaults.value.title)
  if (yr !== undefined) p.year = yr
  if (mediaType.value === 'tv') {
    const tvdb = intVal(valueOrDefault(tvdbId.value, defaults.value.tvdbId))
    if (tvdb !== undefined) p.tvdb_id = tvdb
    const s = intVal(season.value)
    const ep = intVal(episode.value)
    if (s !== undefined) p.season = s
    if (ep !== undefined) p.episode = ep
  }
  return p
})

function now() { return new Date().toTimeString().slice(0, 8) }

function addLog(cls: string, text: string) {
  logLines.value.push({ cls, ts: now(), text })
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  })
}

function clearLog() { logLines.value = [] }

async function copyLog() {
  const text = logLines.value.map(l => `[${l.ts}] ${l.text}`).join('\n')
  try { await navigator.clipboard.writeText(text) } catch {}
}

async function testTorznab() {
  testingIndexer.value = true
  addLog('l-info', `── Test Indexer · ${describePayload()} ──`)
  try {
    const res = await testIndexer(payload.value)
    addLog('l-info', `request: ${res.url}`)
    addLog(res.count > 0 ? 'l-ok' : 'l-err', `Indexer returned ${res.count} result(s)`)
    for (const item of res.results.slice(0, 10)) addLog('l-info', `  ${item}`)
    if (res.results.length > 10) addLog('l-info', `  … ${res.results.length - 10} more`)
  } catch (e) {
    addLog('l-err', `Test Indexer failed: ${e}`)
  } finally {
    testingIndexer.value = false
  }
}

async function resolveSources() {
  cancelResolve()
  activeAbort = new AbortController()
  resolving.value = true
  addLog('l-info', `── Resolve sources · ${describePayload()} ──`)
  srcTests.forEach(s => { s.loading = true; s.resultText = '… resolving'; s.resultClass = '' })
  try {
    const results = await sourceTest(payload.value, activeAbort.signal)
    for (const src of srcTests) {
      src.loading = false
      const result = results[src.name]
      if (result) {
        applySrcResult(src, result)
        logSourceResult(src.name, result)
      } else {
        src.resultText = '· no result'; src.resultClass = ''
      }
    }
  } catch (e: unknown) {
    if (e instanceof Error && e.name === 'AbortError') {
      addLog('l-warn', 'Resolve cancelled')
      srcTests.forEach(s => { s.loading = false; s.resultText = '· cancelled'; s.resultClass = '' })
    } else {
      addLog('l-err', `Resolve failed: ${e}`)
      srcTests.forEach(s => { s.loading = false; s.resultText = '· failed'; s.resultClass = 'err' })
    }
  } finally {
    resolving.value = false
    activeAbort = null
  }
}

async function testSingleSource(name: string) {
  const src = srcTests.find(s => s.name === name)
  if (!src) return
  cancelResolve()
  activeAbort = new AbortController()
  src.loading = true; src.resultText = '… resolving'; src.resultClass = ''
  addLog('l-info', `── Resolve ${name} · ${describePayload()} ──`)
  try {
    // Pass source_name so backend only runs this one source (faster, no wasted work)
    const results = await sourceTest({ ...payload.value, source_name: name }, activeAbort.signal)
    src.loading = false
    const result = results[name]
    if (result) {
      applySrcResult(src, result)
      logSourceResult(name, result)
    } else {
      src.resultText = '· no result'; src.resultClass = ''
    }
  } catch (e: unknown) {
    src.loading = false
    if (e instanceof Error && e.name === 'AbortError') {
      src.resultText = '· cancelled'; src.resultClass = ''
    } else {
      src.resultText = '· failed'; src.resultClass = 'err'
      addLog('l-err', `${name} → ${e}`)
    }
  } finally {
    activeAbort = null
  }
}

function applySrcResult(src: SrcTest, result: SourceResult) {
  if (result.status === 'ok') {
    const urls = result.urls || (result.url ? [{ url: result.url }] : [])
    const found = result.episodes ? `${result.found || 0}/${result.total || 0} ep` : `${urls.length || 1} URL(s)`
    src.resultText = `✓ matched · ${found}`
    src.resultClass = 'ok'
  } else {
    src.resultText = `✗ ${result.message || 'not found'}`
    src.resultClass = 'err'
  }
}

function logSourceResult(name: string, result: SourceResult) {
  if (result.status === 'ok') {
    const urls = result.urls || (result.url ? [{ url: result.url }] : [])
    const found = result.episodes ? `${result.found || 0}/${result.total || 0} episode(s)` : `${urls.length || 1} URL(s)`
    addLog('l-ok', `${name.padEnd(9)} → ${found}`)
    for (const hit of urls.slice(0, 6)) {
      const label = [hit.server, hit.name].filter(Boolean).join(' / ')
      addLog('l-info', `  ${label ? label + ' · ' : ''}${hit.url}`)
    }
    if (result.episodes) {
      for (const ep of result.episodes.filter((e: { url?: string | null }) => e.url).slice(0, 12)) {
        const prefix = ep.season
          ? `S${String(ep.season).padStart(2, '0')}E${String(ep.num).padStart(2, '0')}`
          : `E${String(ep.num).padStart(2, '0')}`
        addLog('l-info', `  ${prefix} · ${ep.url}`)
      }
    }
  } else {
    addLog('l-err', `${name.padEnd(9)} → ${result.message || 'Not found'}`)
  }
  for (const line of (result.log || []).slice(0, 18)) addLog('l-trace', `  ${line}`)
}

function describePayload() {
  const p = payload.value
  const id = p.tmdb_id ? `TMDB ${p.tmdb_id}` : 'no TMDB'
  const name = p.title ? `"${p.title}"` : id
  if (p.media_type === 'tv') {
    const seasonLabel = p.season ? `S${String(p.season).padStart(2, '0')}` : 'all seasons'
    const epLabel = p.episode ? `E${String(p.episode).padStart(2, '0')}` : 'all episodes'
    return `${name} ${seasonLabel} ${epLabel}`
  }
  return name
}

onMounted(() => {})
</script>

<style scoped>
.path-empty {
  color: var(--text-3);
  font-size: 13px;
}
.path-grid {
  display: grid;
  gap: 8px;
}
.path-row {
  display: grid;
  grid-template-columns: minmax(150px, 220px) minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255,255,255,.02);
}
.path-label {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}
.path-owner {
  margin-top: 3px;
  color: var(--text-3);
  font-size: 12px;
}
.path-row code {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--text-2);
  font-family: var(--font-mono);
  font-size: 12px;
}
.path-warnings {
  display: grid;
  gap: 4px;
  margin-top: 10px;
  color: var(--amber);
  font-size: 12px;
}
/* Log trace lines */
:global(.testlog .l-trace) { color: var(--text-3); }
:global(.testlog .l-warn)  { color: var(--amber); }
@media (max-width: 720px) {
  .path-row { grid-template-columns: 1fr; }
}
</style>
