<template>
  <div>
    <div class="page-head">
      <div>
        <h1>LinkGrabber</h1>
        <p class="sub">Recent indexer activity — resolve and grab streams from your sources.</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn" @click="load">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!events.length" class="empty-state">
      <h3>No activity yet</h3>
      <p>Start the worker or let Radarr / Sonarr hand queries off automatically once configured.</p>
    </div>

    <!-- Table -->
    <div v-else class="card">
      <table class="table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Kind</th>
            <th>Status</th>
            <th class="right">Links</th>
            <th>Time</th>
            <th class="grab-col">Grab options</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ev in events" :key="ev.ts + ev.title">
            <td>
              <div class="row-title">{{ ev.title }}</div>
              <div v-if="ev.detail" class="row-sub">{{ ev.detail }}</div>
            </td>
            <td>
              <span :class="['pill', kindPill(ev.kind)]">{{ ev.kind }}</span>
            </td>
            <td>
              <span v-if="ev.status" :class="['pill', statusPill(ev.status)]">{{ ev.status }}</span>
              <span v-else class="pill gray">—</span>
            </td>
            <td class="num">{{ ev.results.length || '—' }}</td>
            <td>
              <span style="font-size:12px;color:var(--text-3);white-space:nowrap">{{ relTime(ev.ts) }}</span>
            </td>
            <td>
              <div v-if="ev.grabs.length" class="grab-list">
                <div v-for="g in ev.grabs" :key="g.token" class="grab-option">
                  <div class="grab-title">{{ g.title }}</div>
                  <div class="grab-actions">
                    <button class="grab-btn" @click="grab(g.token, 'strm')" title="Create STRM file">
                      STRM
                    </button>
                    <button class="grab-btn grab-btn-dl" @click="grab(g.token, 'hls-dl')" title="Download HLS to media file">
                      HLS-DL
                    </button>
                  </div>
                </div>
              </div>
              <span v-else style="color:var(--text-3);font-size:12px">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="card-foot">
        <span style="font-size:12.5px;color:var(--text-3)">{{ events.length }} events · {{ grabsCount }} with grabs</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getActivity, manualGrab, type ActivityEvent } from '../api'

const events = ref<ActivityEvent[]>([])
let timer: ReturnType<typeof setInterval>

const grabsCount = computed(() => events.value.filter(e => e.grabs.length > 0).length)

async function load() {
  try { events.value = await getActivity() } catch {}
}

function kindPill(kind: string) {
  if (kind === 'search') return 'blue'
  if (kind === 'grab')   return 'teal'
  return 'gray'
}

function statusPill(status: string) {
  if (status === 'ok')    return 'green'
  if (status === 'error') return 'red'
  return 'amber'
}

function relTime(ts: number) {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(ts * 1000).toLocaleDateString()
}

async function grab(token: string, mode: string) {
  await manualGrab(token, mode)
  await load()
}

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.grab-btn {
  min-width: 54px;
  font-size: 11px; font-weight: 700;
  background: var(--teal-soft); border: 1px solid var(--teal-line);
  border-radius: 5px; color: var(--teal); padding: 4px 8px;
  cursor: pointer; transition: background .12s; white-space: nowrap;
  font-family: var(--font-sans);
}
.grab-btn:hover { background: rgba(94,224,189,.2); }
.grab-btn-dl {
  background: var(--surface-2); border-color: var(--border-2); color: var(--text-2);
}
.grab-btn-dl:hover { background: var(--surface-3); color: var(--text); }
.grab-col { min-width: 520px; }
.grab-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.grab-option {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 7px 8px;
  background: rgba(255,255,255,.025);
  border: 1px solid var(--border);
  border-radius: 7px;
}
.grab-title {
  min-width: 0;
  color: var(--text-2);
  font-size: 12px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.grab-actions {
  display: flex;
  gap: 5px;
}
@media (max-width: 1000px) {
  .grab-col { min-width: 360px; }
  .grab-option { grid-template-columns: 1fr; align-items: stretch; }
  .grab-actions { justify-content: flex-start; }
}
</style>
