<template>
  <div>
    <div class="toolbar">
      <span class="heading">Recent Pipeline Activity</span>
      <button class="btn-sm ml-auto" @click="load">↺ Refresh</button>
    </div>

    <div v-if="!events.length" class="empty">No activity yet — start the worker to see searches and grabs here.</div>

    <div v-for="ev in events" :key="ev.ts + ev.title" :class="['event-card', ev.kind, ev.status]">
      <div class="ev-header">
        <span class="ev-kind">{{ kindLabel(ev.kind) }}</span>
        <span class="ev-title">{{ ev.title }}</span>
        <span v-if="ev.status" :class="['ev-badge', ev.status]">{{ ev.status }}</span>
        <span class="ev-time">{{ relTime(ev.ts) }}</span>
      </div>

      <div v-if="ev.detail" class="ev-detail">{{ ev.detail }}</div>

      <!-- Search results list -->
      <div v-if="ev.results.length" class="ev-results">
        <span v-for="r in ev.results.slice(0,8)" :key="r" class="result-tag">{{ r }}</span>
        <span v-if="ev.results.length > 8" class="muted xs">+{{ ev.results.length - 8 }} more</span>
      </div>

      <!-- Grab buttons for manual download -->
      <div v-if="ev.grabs.length" class="ev-grabs">
        <span class="xs muted" style="margin-right:8px">Grab as:</span>
        <template v-for="g in ev.grabs" :key="g.token">
          <button class="grab-btn" @click="grab(g.token, 'strm')">{{ g.title }} (strm)</button>
          <button class="grab-btn" @click="grab(g.token, 'hls-dl')">{{ g.title }} (dl)</button>
        </template>
      </div>

      <!-- Torznab search URL -->
      <div v-if="ev.url" class="ev-url">
        <a :href="ev.url" target="_blank" class="url-link">{{ ev.url.slice(0, 120) }}{{ ev.url.length > 120 ? '…' : '' }}</a>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getActivity, manualGrab, type ActivityEvent } from '../api'

const events = ref<ActivityEvent[]>([])
let timer: ReturnType<typeof setInterval>

async function load() {
  try { events.value = await getActivity() } catch {}
}

function kindLabel(kind: string) {
  return kind === 'search' ? '🔍 Search' : kind === 'grab' ? '📥 Grab' : '⚙ Job'
}

function relTime(ts: number) {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60)  return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(ts * 1000).toLocaleDateString()
}

async function grab(token: string, mode: string) {
  await manualGrab(token, mode)
}

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.toolbar { display:flex; align-items:center; margin-bottom:14px; }
.heading { font-size:14px; font-weight:600; color:var(--text-bright); }
.btn-sm {
  background:var(--surface); border:1px solid var(--border); border-radius:4px;
  color:var(--text); font-size:12px; padding:5px 12px; cursor:pointer;
}
.btn-sm:hover { border-color:var(--accent); color:var(--accent); }
.ml-auto { margin-left:auto; }
.empty { color:var(--muted); font-size:13px; padding:32px 0; text-align:center; }
.event-card {
  background:var(--surface); border:1px solid var(--border); border-radius:6px;
  padding:12px 14px; margin-bottom:8px;
}
.event-card.grab  { border-left:3px solid var(--accent); }
.event-card.search { border-left:3px solid var(--muted); }
.event-card.ok    { border-left-color:var(--green); }
.event-card.error { border-left-color:var(--red); }
.ev-header { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:4px; }
.ev-kind  { font-size:11px; color:var(--muted); width:72px; flex-shrink:0; }
.ev-title { font-size:13px; font-weight:500; color:var(--text-bright); flex:1; min-width:0; word-break:break-word; }
.ev-badge { font-size:10px; border-radius:3px; padding:1px 6px; font-weight:600; }
.ev-badge.ok    { background:rgba(152,195,121,.15); color:var(--green); }
.ev-badge.error { background:rgba(224,108,117,.15); color:var(--red); }
.ev-time  { font-size:11px; color:var(--muted); margin-left:auto; white-space:nowrap; }
.ev-detail { font-size:11px; color:var(--muted); margin-bottom:4px; }
.ev-results { display:flex; flex-wrap:wrap; gap:4px; margin-top:6px; }
.result-tag {
  font-size:10px; background:var(--input-bg); border:1px solid var(--border);
  border-radius:3px; padding:1px 7px; color:var(--muted);
}
.ev-grabs { display:flex; flex-wrap:wrap; align-items:center; gap:4px; margin-top:6px; }
.grab-btn {
  font-size:11px; background:var(--input-bg); border:1px solid var(--border);
  border-radius:4px; color:var(--accent); padding:2px 9px; cursor:pointer;
}
.grab-btn:hover { border-color:var(--accent); background:rgba(97,175,239,.08); }
.ev-url { margin-top:6px; }
.url-link { font-size:11px; color:var(--muted); word-break:break-all; }
.url-link:hover { color:var(--accent); }
.xs { font-size:11px; }
.muted { color:var(--muted); }
</style>
