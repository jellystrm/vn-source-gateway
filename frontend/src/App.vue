<template>
  <!-- Auth pages: full-screen, no chrome -->
  <template v-if="isAuthPage">
    <router-view />
  </template>

  <!-- Main app layout -->
  <div v-else class="app">
    <!-- ── Sidebar ── -->
    <aside class="side">
      <div class="brand">
        <div class="brand-mark">D</div>
        <div class="brand-meta">
          <span class="name">Deceptarr</span>
          <span class="path">workspace</span>
        </div>
      </div>

      <nav class="nav">
        <div class="nav-label">Workspace</div>

        <router-link to="/linkgrabber" class="nav-item" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
          <span>LinkGrabber</span>
          <span v-if="activityCount > 0" class="nav-count">{{ activityCount }}</span>
        </router-link>

        <router-link to="/downloads" class="nav-item" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          <span>Downloads</span>
          <span v-if="activeJobsCount > 0" class="nav-count">{{ activeJobsCount }}</span>
        </router-link>

        <router-link to="/sources" class="nav-item" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
          <span>Sources</span>
        </router-link>

        <router-link to="/settings" class="nav-item" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span>Settings</span>
        </router-link>

        <router-link to="/test" class="nav-item" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 2v6l-4 8a4 4 0 0 0 3.5 6h7a4 4 0 0 0 3.5-6l-4-8V2"/>
            <line x1="8" y1="2" x2="16" y2="2"/>
            <line x1="7.5" y1="14" x2="16.5" y2="14"/>
          </svg>
          <span>Test</span>
        </router-link>
      </nav>

      <div class="side-footer">
        <div class="health-row">
          <span class="health-dot">All systems</span>
          <span class="mono" style="color:var(--green)">online</span>
        </div>
        <button class="logout-btn" @click="logout">Sign out</button>
      </div>
    </aside>

    <!-- ── Main ── -->
    <div class="main">
      <header class="topbar">
        <div class="crumbs">
          <span>Deceptarr</span>
          <span class="sep">/</span>
          <span class="here">{{ pageTitle }}</span>
        </div>
        <div class="top-actions">
          <div class="avatar">{{ userInitial }}</div>
        </div>
      </header>

      <div class="content">
        <router-view />
      </div>

      <footer class="statusbar">
        <template v-if="route.path.startsWith('/linkgrabber')">
          <span class="stat"><span class="stat-label">Events</span><span class="stat-val teal">{{ activityCount }}</span></span>
          <span class="stat"><span class="stat-label">With grabs</span><span class="stat-val">{{ grabsCount }}</span></span>
        </template>
        <template v-else-if="route.path.startsWith('/downloads')">
          <span class="stat"><span class="stat-label">Total</span><span class="stat-val">{{ jobs.length }}</span></span>
          <span class="stat"><span class="stat-label">Running</span><span class="stat-val green">{{ runningCount }}</span></span>
          <span class="stat"><span class="stat-label">Errors</span><span class="stat-val red">{{ errorCount }}</span></span>
        </template>
        <template v-else-if="route.path.startsWith('/sources')">
          <span class="stat"><span class="stat-label">Sources</span><span class="stat-val teal">3 built-in</span></span>
        </template>
        <template v-else-if="route.path.startsWith('/settings')">
          <span class="stat"><span class="stat-label">Config</span><span class="stat-val dim">live</span></span>
        </template>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authLogout, getPipeline, getActivity, type PipelineJob, type ActivityEvent } from './api'

const route  = useRoute()
const router = useRouter()

const isAuthPage = computed(() => ['/login', '/setup'].includes(route.path))

const jobs   = ref<PipelineJob[]>([])
const events = ref<ActivityEvent[]>([])

const activityCount   = computed(() => events.value.length)
const grabsCount      = computed(() => events.value.filter(e => e.grabs.length > 0).length)
const activeJobsCount = computed(() => jobs.value.filter(j => j.status !== 'completed' && j.status !== 'error').length)
const runningCount    = computed(() => jobs.value.filter(j => j.status === 'running').length)
const errorCount      = computed(() => jobs.value.filter(j => j.status === 'error').length)

const userInitial = computed(() => {
  const name = localStorage.getItem('deceptarr_user') || 'A'
  return name.slice(0, 2).toUpperCase()
})

const pageTitles: Record<string, string> = {
  '/linkgrabber': 'LinkGrabber',
  '/downloads':   'Downloads',
  '/sources':     'Sources',
  '/settings':    'Settings',
  '/test':        'Test',
}

const pageTitle = computed(() => {
  for (const [prefix, title] of Object.entries(pageTitles)) {
    if (route.path.startsWith(prefix)) return title
  }
  return 'Deceptarr'
})

// Polling errors are silenced — the router guard handles session-expiry redirects
// on the next navigation. Do NOT redirect from here (causes post-login loop).
async function loadJobs()   { try { jobs.value   = await getPipeline() } catch {} }
async function loadEvents() { try { events.value = await getActivity() } catch {} }

let timer: ReturnType<typeof setInterval>

function startPolling() {
  if (timer) return
  loadJobs(); loadEvents()
  timer = setInterval(() => { loadJobs(); loadEvents() }, 5000)
}

function stopPolling() {
  clearInterval(timer)
  timer = undefined as unknown as ReturnType<typeof setInterval>
}

// Start/stop polling based on whether we're on an auth page.
// Watch handles the case where auth state changes after mount.
watch(isAuthPage, (onAuth) => {
  if (onAuth) stopPolling()
  else        startPolling()
}, { immediate: true })

onUnmounted(stopPolling)

async function logout() {
  await authLogout()
  localStorage.removeItem('deceptarr_user')
  router.replace('/login')
}
</script>

<style>
/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* ── Design tokens ── */
:root {
  --bg:             #0a0e13;
  --bg-2:           #0d1218;
  --surface:        #131a22;
  --surface-2:      #182029;
  --surface-3:      #1e2832;
  --border:         #232f3b;
  --border-2:       #2c3a48;
  --border-strong:  #38495b;
  --text:           #e6ebf2;
  --text-2:         #9aa6b4;
  --text-3:         #6b7886;
  --accent:         #f5a623;
  --accent-soft:    rgba(245,166,35,.12);
  --accent-strong:  #ffb840;
  --teal:           #5ee0bd;
  --teal-soft:      rgba(94,224,189,.10);
  --teal-line:      rgba(94,224,189,.25);
  --red:            #ff6b6b;
  --red-soft:       rgba(255,107,107,.12);
  --green:          #4ade80;
  --green-soft:     rgba(74,222,128,.10);
  --blue:           #60a5fa;
  --blue-soft:      rgba(96,165,250,.12);
  --input-bg:       #0d1117;
  --radius-sm:      6px;
  --radius:         10px;
  --radius-lg:      14px;
  --side-w:         248px;
  --topbar-h:       60px;
  --font-sans:      'Geist', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  --font-mono:      'JetBrains Mono', ui-monospace, Menlo, monospace;
}

html, body { height: 100%; overflow: hidden; }

body {
  font-family: var(--font-sans);
  font-feature-settings: 'cv11', 'ss01';
  background:
    radial-gradient(1200px 600px at 0% 0%, rgba(94,224,189,.05), transparent 60%),
    radial-gradient(900px 600px at 100% 100%, rgba(245,166,35,.04), transparent 60%),
    var(--bg);
  color: var(--text);
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  letter-spacing: -0.005em;
}

/* ── App shell ── */
.app {
  display: grid;
  grid-template-columns: var(--side-w) 1fr;
  height: 100vh;
}

/* ── Sidebar ── */
.side {
  background: linear-gradient(180deg, var(--bg-2) 0%, var(--bg) 100%);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  padding: 18px 14px;
  gap: 18px;
  overflow: hidden;
}

.brand {
  display: flex; align-items: center; gap: 11px;
  padding: 6px 8px;
}
.brand-mark {
  width: 38px; height: 38px; border-radius: 10px;
  background: linear-gradient(135deg, #ffb840 0%, #f5a623 50%, #d68910 100%);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 20px; color: #0d1218;
  box-shadow: 0 1px 0 rgba(255,255,255,.3) inset, 0 6px 18px -4px rgba(245,166,35,.5);
  letter-spacing: -.04em; flex-shrink: 0;
}
.brand-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.brand-meta .name { font-weight: 700; font-size: 15px; letter-spacing: -.02em; }
.brand-meta .path {
  font-family: var(--font-mono); font-size: 10.5px; color: var(--text-3);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.nav { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.nav-label {
  font-size: 10.5px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
  color: var(--text-3); padding: 6px 10px 4px;
}
.nav-item {
  display: flex; align-items: center; gap: 11px;
  padding: 9px 11px; border-radius: 8px; cursor: pointer;
  color: var(--text-2); font-weight: 500; font-size: 13.5px;
  transition: background .12s, color .12s;
  user-select: none; position: relative;
  text-decoration: none;
}
.nav-item:hover { background: rgba(255,255,255,.03); color: var(--text); }
.nav-item.active {
  background: linear-gradient(90deg, rgba(94,224,189,.12), rgba(94,224,189,.03));
  color: var(--text);
}
.nav-item.active::before {
  content: ""; position: absolute; left: -14px; top: 8px; bottom: 8px;
  width: 2.5px; border-radius: 0 2px 2px 0;
  background: var(--teal); box-shadow: 0 0 8px var(--teal);
}
.nav-icon {
  width: 18px; height: 18px; flex-shrink: 0; color: currentColor;
}
.nav-item.active .nav-icon { color: var(--teal); }
.nav-count {
  margin-left: auto; font-size: 11px; font-weight: 600;
  background: var(--surface-2); color: var(--text-3);
  padding: 1px 7px; border-radius: 99px; min-width: 22px; text-align: center;
  border: 1px solid var(--border);
}
.nav-item.active .nav-count {
  background: rgba(94,224,189,.15); color: var(--teal); border-color: var(--teal-line);
}

.side-footer {
  margin-top: auto; border-top: 1px solid var(--border);
  padding: 14px 8px 4px; display: flex; flex-direction: column; gap: 10px;
}
.health-row {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 11.5px; color: var(--text-3);
}
.health-dot {
  display: inline-flex; align-items: center; gap: 6px; font-weight: 500;
}
.health-dot::before {
  content: ""; width: 6px; height: 6px; border-radius: 50%;
  background: var(--green); box-shadow: 0 0 8px var(--green);
  animation: pulse 2s infinite;
}
@keyframes pulse { 50% { opacity: .5 } }
.mono { font-family: var(--font-mono); font-size: 11px; }
.logout-btn {
  background: none; border: 1px solid var(--border); border-radius: 6px;
  color: var(--text-3); font-size: 12px; font-family: var(--font-sans);
  padding: 6px 10px; cursor: pointer; text-align: center;
  transition: color .12s, border-color .12s;
}
.logout-btn:hover { color: var(--red); border-color: rgba(255,107,107,.3); }

/* ── Main area ── */
.main {
  display: flex; flex-direction: column;
  min-width: 0; overflow: hidden;
}

/* ── Topbar ── */
.topbar {
  height: var(--topbar-h);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center;
  padding: 0 24px; gap: 14px;
  background: rgba(13,18,24,.7);
  backdrop-filter: blur(10px);
  flex-shrink: 0;
}
.crumbs { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--text-2); font-weight: 500; }
.crumbs .sep { color: var(--text-3); opacity: .5; }
.crumbs .here { color: var(--text); font-weight: 600; }
.top-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #5ee0bd, #2a8b75);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; color: #0a1f1a; font-size: 12.5px;
  border: 1px solid rgba(255,255,255,.08);
  cursor: default; user-select: none; flex-shrink: 0;
}
.icon-btn {
  width: 34px; height: 34px; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-2); display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .12s;
}
.icon-btn:hover { background: var(--surface-2); color: var(--text); border-color: var(--border-2); }

/* ── Content ── */
.content {
  flex: 1; overflow-y: auto;
  padding: 28px 32px 40px;
  scrollbar-width: thin;
  scrollbar-color: var(--border-2) transparent;
}
.content::-webkit-scrollbar { width: 10px; }
.content::-webkit-scrollbar-thumb {
  background: var(--border-2); border-radius: 5px;
  border: 3px solid transparent; background-clip: content-box;
}

/* ── Status bar ── */
.statusbar {
  border-top: 1px solid var(--border);
  background: var(--bg-2);
  padding: 0 32px;
  display: flex; align-items: center; gap: 18px;
  height: 36px;
  font-size: 12px; color: var(--text-3);
  flex-shrink: 0;
}
.stat { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); }
.stat-label { font-family: var(--font-sans); color: var(--text-3); }
.stat-val { color: var(--text); font-weight: 600; }
.stat-val.dim { color: var(--text-3); font-weight: 500; }
.stat-val.green { color: var(--green); }
.stat-val.red { color: var(--red); }
.stat-val.amber { color: var(--accent); }
.stat-val.teal { color: var(--teal); }

/* ── Page head ── */
.page-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 22px; gap: 24px;
}
.page-head h1 { font-size: 24px; font-weight: 700; letter-spacing: -.025em; margin: 0 0 4px; }
.page-head .sub { color: var(--text-2); font-size: 13.5px; margin: 0; line-height: 1.5; max-width: 560px; }

/* ── Toolbar ── */
.toolbar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 18px;
}
.toolbar .group { display: flex; align-items: center; gap: 6px; }
.toolbar .divider { width: 1px; height: 20px; background: var(--border); margin: 0 4px; }
.toolbar .spacer { flex: 1; }

/* ── Buttons ── */
.btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 12px; border-radius: 7px;
  background: var(--surface-2); border: 1px solid var(--border-2);
  color: var(--text); font: 500 13px/1 var(--font-sans);
  cursor: pointer; transition: all .12s;
  user-select: none; white-space: nowrap;
}
.btn:hover { background: var(--surface-3); border-color: var(--border-strong); }
.btn:active { transform: translateY(.5px); }
.btn svg { width: 14px; height: 14px; flex-shrink: 0; }
.btn.ghost { background: transparent; border-color: transparent; color: var(--text-2); }
.btn.ghost:hover { background: var(--surface-2); color: var(--text); }
.btn.primary {
  background: linear-gradient(180deg, #ffb840, #f5a623);
  border-color: #d68910; color: #1a1208; font-weight: 600;
  box-shadow: 0 1px 0 rgba(255,255,255,.3) inset, 0 4px 12px -2px rgba(245,166,35,.35);
}
.btn.primary:hover { filter: brightness(1.05); }
.btn.teal {
  background: linear-gradient(180deg, rgba(94,224,189,.18), rgba(94,224,189,.10));
  border-color: var(--teal-line); color: var(--teal);
}
.btn.teal:hover { background: rgba(94,224,189,.22); }
.btn.danger { color: var(--red); border-color: rgba(255,107,107,.25); background: var(--red-soft); }
.btn.danger:hover { background: rgba(255,107,107,.18); }
.btn.sm { padding: 5px 9px; font-size: 12px; }
.btn:disabled { opacity: .5; cursor: default; transform: none; filter: none; }

/* ── Pill badges ── */
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 99px;
  background: var(--surface-2); border: 1px solid var(--border); color: var(--text-2);
  white-space: nowrap;
}
.pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; opacity: .9; }
.pill.green  { color: var(--green);  background: var(--green-soft);  border-color: rgba(74,222,128,.2); }
.pill.amber  { color: var(--accent); background: var(--accent-soft); border-color: rgba(245,166,35,.25); }
.pill.red    { color: var(--red);    background: var(--red-soft);    border-color: rgba(255,107,107,.25); }
.pill.blue   { color: var(--blue);   background: var(--blue-soft);   border-color: rgba(96,165,250,.2); }
.pill.teal   { color: var(--teal);   background: var(--teal-soft);   border-color: var(--teal-line); }
.pill.gray   { color: var(--text-3); }

/* ── Progress ── */
.prog { width: 100%; max-width: 240px; display: flex; flex-direction: column; gap: 5px; }
.prog-bar { height: 5px; background: var(--surface-3); border-radius: 99px; overflow: hidden; }
.prog-bar > span {
  display: block; height: 100%;
  background: linear-gradient(90deg, var(--teal), #8ef0d3);
  border-radius: 99px; box-shadow: 0 0 8px rgba(94,224,189,.4);
  transition: width .4s ease;
}
.prog.amber .prog-bar > span { background: linear-gradient(90deg, var(--accent), var(--accent-strong)); box-shadow: 0 0 8px rgba(245,166,35,.4); }
.prog.red   .prog-bar > span { background: linear-gradient(90deg, #ff8080, var(--red)); box-shadow: none; }
.prog.gray  .prog-bar > span { background: var(--border-strong); box-shadow: none; }
.prog-meta { display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 11px; color: var(--text-3); }
.prog-meta .a { color: var(--text-2); }

/* ── Data table ── */
.table { width: 100%; border-collapse: separate; border-spacing: 0; }
.table thead th {
  text-align: left; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--text-3); padding: 10px 14px; border-bottom: 1px solid var(--border);
  background: var(--bg-2);
}
.table tbody td { padding: 13px 14px; border-bottom: 1px solid var(--border); font-size: 13px; vertical-align: middle; }
.table tbody tr:hover td { background: rgba(255,255,255,.015); }
.table tbody tr:last-child td { border-bottom: 0; }
.table .row-title { font-weight: 600; color: var(--text); }
.table .row-sub { color: var(--text-3); font-size: 11.5px; margin-top: 2px; font-family: var(--font-mono); }
.table .num { font-family: var(--font-mono); color: var(--text-2); font-size: 12.5px; text-align: right; }
.table .right { text-align: right; }
.row-flex { display: flex; align-items: center; gap: 12px; }

/* ── Thumb ── */
.thumb {
  width: 46px; height: 64px; border-radius: 6px;
  background: linear-gradient(135deg, #1a2530, #2a3848);
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  color: var(--text-3); font-size: 10px; font-weight: 700; font-family: var(--font-mono);
  position: relative; overflow: hidden; border: 1px solid var(--border);
}
.thumb::after {
  content: ""; position: absolute; inset: 0;
  background: repeating-linear-gradient(45deg, transparent 0 4px, rgba(255,255,255,.02) 4px 8px);
}

/* ── Card ── */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); overflow: hidden;
}
.card-head {
  padding: 18px 22px 14px; border-bottom: 1px solid var(--border);
  display: flex; align-items: flex-start; justify-content: space-between; gap: 24px;
}
.card-head h2 { margin: 0 0 4px; font-size: 15px; font-weight: 600; letter-spacing: -.01em; }
.card-head .desc { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.5; }
.card-body { padding: 18px 22px; }
.card-foot {
  padding: 14px 22px; border-top: 1px solid var(--border);
  background: var(--bg-2);
  display: flex; align-items: center; gap: 10px;
}

/* ── fcard (settings) ── */
.fcard { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.fcard-head { padding: 16px 22px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 14px; }
.fcard-icon {
  width: 36px; height: 36px; border-radius: 9px;
  background: var(--surface-3); border: 1px solid var(--border-2);
  display: flex; align-items: center; justify-content: center; color: var(--accent);
  flex-shrink: 0;
}
.fcard-head h3 { margin: 0; font-size: 14px; font-weight: 600; }
.fcard-head .desc { margin: 2px 0 0; color: var(--text-3); font-size: 12.5px; }
.fcard-body { padding: 20px 22px; }

/* ── Settings subnav ── */
.subnav {
  display: flex; gap: 2px; padding: 4px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; margin-bottom: 20px; overflow-x: auto;
}
.subnav button {
  appearance: none; background: none; border: 0; color: var(--text-2);
  padding: 8px 14px; border-radius: 7px; cursor: pointer;
  font: 500 13px/1 var(--font-sans); transition: all .12s;
  display: inline-flex; align-items: center; gap: 7px; white-space: nowrap;
}
.subnav button:hover { color: var(--text); background: var(--surface-2); }
.subnav button.active { background: var(--surface-3); color: var(--text); box-shadow: 0 1px 0 rgba(255,255,255,.04) inset, 0 1px 2px rgba(0,0,0,.3); }
.subnav button svg { width: 14px; height: 14px; opacity: .8; }

/* ── Settings form ── */
.form { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.field { display: flex; flex-direction: column; gap: 7px; }
.field.full { grid-column: 1 / -1; }
.field label {
  font-size: 12px; font-weight: 600; color: var(--text-2); letter-spacing: .005em;
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.field label .hint { font-weight: 400; color: var(--text-3); font-size: 11.5px; }
.input, .select {
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; color: var(--text);
  font: 14px/1.3 var(--font-sans); width: 100%;
  transition: border-color .12s, background .12s; outline: 0;
}
.input.mono { font-family: var(--font-mono); font-size: 13px; }
.input::placeholder { color: var(--text-3); }
.input:focus, .select:focus { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(94,224,189,.12); }
.input-group { display: flex; align-items: stretch; gap: 0; }
.input-group .input { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: 0; }
.input-group .btn { border-top-left-radius: 0; border-bottom-left-radius: 0; }
.check {
  display: inline-flex; align-items: center; gap: 9px;
  cursor: pointer; font-size: 13.5px; color: var(--text); user-select: none;
}
.check input { position: absolute; opacity: 0; pointer-events: none; }
.check-box {
  width: 17px; height: 17px; border-radius: 5px;
  background: var(--bg); border: 1.5px solid var(--border-strong);
  display: inline-flex; align-items: center; justify-content: center;
  transition: all .12s; flex-shrink: 0;
}
.check input:checked + .check-box { background: var(--teal); border-color: var(--teal); }
.check input:checked + .check-box::after {
  content: ""; width: 9px; height: 5px;
  border: 2px solid #0a1612; border-top: 0; border-right: 0;
  transform: rotate(-45deg) translate(1px,-1px);
}

/* ── Test ── */
.test-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; margin-bottom: 18px; }
.test-tile {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px; cursor: pointer;
  transition: all .12s; display: flex; flex-direction: column; gap: 6px;
}
.test-tile:hover { background: var(--surface-3); border-color: var(--border-2); transform: translateY(-1px); }
.test-tile-head { display: flex; align-items: center; justify-content: space-between; }
.test-tile-head .name { font-weight: 600; font-size: 13.5px; }
.test-tile .desc { font-size: 12px; color: var(--text-3); line-height: 1.45; }
.dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot.green { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot.red   { background: var(--red);   box-shadow: 0 0 6px var(--red); }
.dot.amber { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.dot.gray  { background: var(--text-3); }
.testlog {
  background: var(--bg); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; font-family: var(--font-mono); font-size: 12.5px;
  line-height: 1.7; color: var(--text-2); max-height: 380px; overflow: auto;
}
.testlog .l-ok::before   { content: "✓ "; color: var(--green); }
.testlog .l-err::before  { content: "✗ "; color: var(--red); }
.testlog .l-info::before { content: "› "; color: var(--text-3); }
.testlog .l-warn::before { content: "! "; color: var(--accent); }
.testlog .ts { color: var(--text-3); margin-right: 8px; }

/* ── Source list ── */
.src-list { display: flex; flex-direction: column; gap: 8px; }
.src {
  display: grid;
  grid-template-columns: 30px 28px 1fr auto auto;
  align-items: center; gap: 14px;
  padding: 12px 16px;
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 10px; transition: border-color .12s, background .12s;
}
.src:hover { border-color: var(--border-2); }
.src-idx { font-family: var(--font-mono); font-size: 12.5px; color: var(--text-3); text-align: center; font-weight: 500; }
.src-handle { display: flex; flex-direction: column; gap: 1px; color: var(--text-3); }
.src-handle button {
  background: none; border: 0; color: inherit; padding: 0;
  width: 18px; height: 14px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; border-radius: 3px;
}
.src-handle button:hover { background: var(--surface-3); color: var(--text); }
.src-name { font-weight: 600; font-size: 14px; }
.src-url { font-family: var(--font-mono); font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.src-actions { display: flex; gap: 6px; }
.badge {
  font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  padding: 3px 7px; border-radius: 5px;
  background: var(--blue-soft); color: var(--blue); border: 1px solid rgba(96,165,250,.2);
}
.badge.amber { background: var(--accent-soft); color: var(--accent); border-color: rgba(245,166,35,.25); }
.badge.teal  { background: var(--teal-soft);   color: var(--teal);   border-color: var(--teal-line); }
.icon-mini {
  width: 28px; height: 28px; border-radius: 6px;
  background: transparent; border: 1px solid var(--border);
  color: var(--text-3); display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .12s;
}
.icon-mini:hover { background: var(--surface-3); color: var(--text); border-color: var(--border-2); }
.icon-mini.danger:hover { color: var(--red); border-color: rgba(255,107,107,.3); background: var(--red-soft); }

/* ── Empty state ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 80px 24px; text-align: center;
  border: 1px dashed var(--border-2); border-radius: var(--radius-lg);
  background: radial-gradient(600px 240px at 50% 0%, rgba(94,224,189,.04), transparent 70%), var(--surface);
  min-height: 320px;
}
.empty-state h3 { margin: 0 0 6px; font-size: 16px; font-weight: 600; }
.empty-state p { margin: 0; color: var(--text-2); font-size: 13.5px; line-height: 1.55; max-width: 380px; }

/* ── Hint text ── */
.hint-text { font-size: 12px; color: var(--text-3); margin-top: 2px; line-height: 1.4; }
.hint-text a { color: var(--teal); }
</style>
