<template>
  <div>
    <div class="toolbar">
      <button class="btn-sm" @click="bulk('resume_all')">▶ Resume All</button>
      <button class="btn-sm" @click="bulk('pause_all')">⏸ Pause All</button>
      <div class="sep" />
      <button class="btn-sm" @click="bulk('clear_done')">✕ Clear Done</button>
      <div class="sep" />
      <button class="btn-sm ml-auto" @click="load">↺ Refresh</button>
    </div>

    <div class="statusbar">
      <span class="stat">Total: <b>{{ jobs.length }}</b></span>
      <span class="stat">Running: <b style="color:var(--green)">{{ counts.running }}</b></span>
      <span class="stat">Errors: <b style="color:var(--red)">{{ counts.error }}</b></span>
      <span class="stat">Done: <b>{{ counts.completed }}</b></span>
    </div>

    <div v-if="!jobs.length" class="empty">No jobs.</div>

    <table v-else class="tbl">
      <thead>
        <tr><th>Title</th><th>Mode</th><th>Status</th><th>Progress</th><th style="width:110px"></th></tr>
      </thead>
      <tbody>
        <tr v-for="j in jobs" :key="j.id" :class="['job-row', j.status]">
          <td class="title-cell">
            <span class="kind-badge">{{ j.kind === 'movie' ? '🎬' : '📺' }}</span>
            {{ j.title }}
            <span v-if="j.kind === 'episode' && j.season" class="ep-tag">
              S{{ String(j.season).padStart(2,'0') }}E{{ String(j.episode).padStart(2,'0') }}
            </span>
            <div v-if="j.error" class="err-msg">{{ j.error }}</div>
            <div v-if="j.save_path && j.status === 'completed'" class="save-path">{{ j.save_path }}</div>
          </td>
          <td class="xs muted">{{ j.output_mode }}</td>
          <td>
            <span :class="['status-dot', j.status]" />
            <span class="xs">{{ j.status }}</span>
          </td>
          <td style="min-width:100px">
            <div class="progress-bar"><div class="progress-fill" :style="{ width: (j.progress * 100).toFixed(0) + '%' }" /></div>
            <span class="xs muted">{{ (j.progress * 100).toFixed(0) }}%</span>
          </td>
          <td class="actions-cell">
            <button v-if="j.status === 'paused' || j.status === 'error' || j.status === 'queued'"
              class="act-btn green" title="Resume" @click="act('resume', j.id)">▶</button>
            <button v-if="j.status === 'running' || j.status === 'queued'"
              class="act-btn" title="Pause" @click="act('pause', j.id)">⏸</button>
            <button class="act-btn red" title="Delete" @click="act('delete', j.id)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getPipeline, jobAction, bulkAction, type PipelineJob } from '../api'

const jobs = ref<PipelineJob[]>([])
let timer: ReturnType<typeof setInterval>

const counts = computed(() => ({
  running:   jobs.value.filter(j => j.status === 'running').length,
  error:     jobs.value.filter(j => j.status === 'error').length,
  completed: jobs.value.filter(j => j.status === 'completed').length,
}))

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

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.toolbar { display:flex; align-items:center; gap:6px; margin-bottom:12px; flex-wrap:wrap; }
.btn-sm {
  background:var(--surface); border:1px solid var(--border); border-radius:4px;
  color:var(--text); font-size:12px; padding:5px 12px; cursor:pointer;
}
.btn-sm:hover { border-color:var(--accent); color:var(--accent); }
.sep { width:1px; height:20px; background:var(--border); margin:0 2px; }
.ml-auto { margin-left:auto; }
.statusbar { display:flex; gap:16px; font-size:12px; color:var(--muted); margin-bottom:14px; }
.stat b { font-weight:600; color:var(--text-bright); }
.empty { color:var(--muted); font-size:13px; padding:32px 0; text-align:center; }
.tbl { width:100%; border-collapse:collapse; font-size:13px; }
.tbl th { font-size:11px; color:var(--muted); padding:6px 10px; border-bottom:1px solid var(--border); text-align:left; }
.tbl td { padding:7px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }
.job-row:hover td { background:rgba(255,255,255,.02); }
.title-cell { max-width:360px; }
.kind-badge { font-size:14px; margin-right:4px; }
.ep-tag { font-size:10px; background:var(--border); border-radius:3px; padding:1px 5px; margin-left:4px; color:var(--muted); }
.err-msg { font-size:11px; color:var(--red); margin-top:2px; white-space:normal; word-break:break-all; }
.save-path { font-size:10px; color:var(--muted); margin-top:2px; word-break:break-all; }
.xs { font-size:11px; }
.muted { color:var(--muted); }
.status-dot {
  display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:4px; vertical-align:middle;
}
.status-dot.running   { background:var(--accent); }
.status-dot.completed { background:var(--green); }
.status-dot.error     { background:var(--red); }
.status-dot.queued    { background:var(--muted); }
.status-dot.paused    { background:#e5c07b; }
.progress-bar { height:4px; background:var(--border); border-radius:2px; margin-bottom:2px; }
.progress-fill { height:100%; background:var(--accent); border-radius:2px; transition:width .3s; }
.actions-cell { white-space:nowrap; }
.act-btn {
  background:none; border:1px solid var(--border); border-radius:3px;
  color:var(--muted); font-size:11px; padding:2px 7px; cursor:pointer; margin-right:3px;
}
.act-btn:hover { border-color:var(--text); color:var(--text); }
.act-btn.green:hover { border-color:var(--green); color:var(--green); }
.act-btn.red:hover   { border-color:var(--red);   color:var(--red); }
</style>
