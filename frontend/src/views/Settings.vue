<template>
  <div class="settings-wrap">
    <!-- Sidebar -->
    <nav class="sidebar">
      <button v-for="s in sections" :key="s.id" :class="['sec-btn', { active: active === s.id }]" @click="active = s.id">
        {{ s.label }}
      </button>
    </nav>

    <!-- Form panel -->
    <div class="panel">
      <!-- Radarr -->
      <template v-if="active === 'radarr'">
        <h2>Radarr</h2>
        <Field label="URL" v-model="cfg.radarr_url" placeholder="http://radarr:7878" />
        <Field label="API Key" v-model="cfg.radarr_api_key" type="password" />
        <Check label="Movie monitoring enabled" v-model="cfg.movie_enabled" />
        <Field label="Poll interval (s)" v-model.number="cfg.poll_interval_seconds" type="number" />
        <Field label="Max items per poll" v-model.number="cfg.max_items_per_poll" type="number" />
      </template>

      <!-- Sonarr -->
      <template v-if="active === 'sonarr'">
        <h2>Sonarr</h2>
        <Field label="URL" v-model="cfg.sonarr_url" placeholder="http://sonarr:8989" />
        <Field label="API Key" v-model="cfg.sonarr_api_key" type="password" />
        <Check label="Series monitoring enabled" v-model="cfg.series_enabled" />
        <Field label="Poll interval (s)" v-model.number="cfg.poll_interval_seconds" type="number" />
        <Field label="Max items per poll" v-model.number="cfg.max_items_per_poll" type="number" />
      </template>

      <!-- Jellyfin -->
      <template v-if="active === 'jellyfin'">
        <h2>Jellyfin</h2>
        <Field label="URL" v-model="cfg.jellyfin_url" placeholder="http://jellyfin:8096" />
        <Field label="API Key" v-model="cfg.jellyfin_api_key" type="password" />
        <Check label="Trigger library scan after .strm write" v-model="cfg.jellyfin_scan_after_strm" />
      </template>

      <!-- Output / Runtime -->
      <template v-if="active === 'runtime'">
        <h2>Output / Runtime</h2>
        <div class="field">
          <label class="label">Default Output Mode</label>
          <select v-model="cfg.default_output_mode">
            <option value="strm">strm — write .strm file (recommended)</option>
            <option value="hls-dl">hls-dl — download HLS to file</option>
          </select>
        </div>
        <Check label="Expose both modes in Torznab results" v-model="cfg.expose_both_modes" />
        <div class="field">
          <label class="label">Download Container</label>
          <select v-model="cfg.download_container">
            <option value="mkv">mkv</option>
            <option value="mp4">mp4</option>
            <option value="ts">ts</option>
          </select>
        </div>
        <div class="field">
          <label class="label">Import Mode (Radarr/Sonarr)</label>
          <select v-model="cfg.import_mode">
            <option value="Move">Move</option>
            <option value="Copy">Copy</option>
            <option value="Hardlink">Hardlink</option>
          </select>
        </div>
        <Field label="ffmpeg path" v-model="cfg.ffmpeg_path" placeholder="ffmpeg" />
        <Field label="ffmpeg extra args (comma-separated)" v-model="ffmpegArgs" />
      </template>

      <!-- Indexer -->
      <template v-if="active === 'indexer'">
        <h2>Torznab Indexer</h2>
        <Field label="API Key" v-model="cfg.torznab_api_key" />
        <Field label="Public Base URL" v-model="cfg.public_base_url" placeholder="http://deceptarr:8765" />
        <Field label="Server Labels (comma-separated)" v-model="serverLabels" placeholder="ViệtSub, Lồng Tiếng" />
        <Check label="Group results by source" v-model="cfg.torznab_group_sources" />
      </template>

      <!-- Downloader -->
      <template v-if="active === 'downloader'">
        <h2>Download Client</h2>
        <Field label="UI Host" v-model="cfg.ui_host" />
        <Field label="UI Port" v-model.number="cfg.ui_port" type="number" />
        <Field label="qBittorrent Username" v-model="cfg.qb_username" />
        <Field label="qBittorrent Password" v-model="cfg.qb_password" type="password" />
        <div class="field">
          <label class="label">Log Level</label>
          <select v-model="cfg.log_level">
            <option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option>
          </select>
        </div>
      </template>

      <!-- Tasks / TMDB -->
      <template v-if="active === 'tasks'">
        <h2>TMDB</h2>
        <Field label="TMDB API Key" v-model="cfg.tmdb_api_key" type="password" placeholder="Get free key at themoviedb.org" />
        <p class="hint">Required for title/year resolution in source queries. Free at <a href="https://www.themoviedb.org/settings/api" target="_blank">themoviedb.org</a>.</p>
      </template>

      <!-- Worker -->
      <template v-if="active === 'worker'">
        <h2>Worker</h2>
        <Check label="Worker enabled" v-model="cfg.worker_enabled" />
        <Field label="Retry after (s)" v-model.number="cfg.retry_after_seconds" type="number" />
        <Field label="Job detail retention (hours)" v-model.number="cfg.job_detail_retention_hours" type="number" />
        <Field label="State path" v-model="cfg.state_path" />
      </template>

      <div class="save-row">
        <button class="btn" @click="save" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
        <span v-if="saved" class="ok-msg">✓ Saved</span>
        <span v-if="saveError" class="err-msg">{{ saveError }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getConfig, saveSettings, type Config } from '../api'

// Inline micro-components
import { defineComponent, h } from 'vue'

const Field = defineComponent({
  props: { label: String, modelValue: [String, Number], type: { default: 'text' }, placeholder: String },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('div', { class: 'field' }, [
      h('label', { class: 'label' }, props.label),
      h('input', {
        type: props.type, value: props.modelValue, placeholder: props.placeholder,
        onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value),
      }),
    ])
  },
})

const Check = defineComponent({
  props: { label: String, modelValue: Boolean },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('label', { class: 'check-row' }, [
      h('input', {
        type: 'checkbox', checked: props.modelValue,
        onChange: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).checked),
      }),
      h('span', props.label),
    ])
  },
})

const sections = [
  { id: 'radarr', label: '🎬 Radarr' },
  { id: 'sonarr', label: '📺 Sonarr' },
  { id: 'jellyfin', label: '🎞 Jellyfin' },
  { id: 'runtime', label: '⚙ Output' },
  { id: 'indexer', label: '🔗 Indexer' },
  { id: 'downloader', label: '📥 Downloader' },
  { id: 'tasks', label: '🔑 TMDB' },
  { id: 'worker', label: '🔄 Worker' },
]

const active = ref('radarr')
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const cfg = ref<Record<string, any>>({})
const saving = ref(false)
const saved = ref(false)
const saveError = ref('')

const ffmpegArgs = computed({
  get: () => ((cfg.value.ffmpeg_extra_args as string[]) || []).join(', '),
  set: (v: string) => { cfg.value.ffmpeg_extra_args = v.split(',').map(s => s.trim()).filter(Boolean) },
})
const serverLabels = computed({
  get: () => ((cfg.value.server_labels as string[]) || []).join(', '),
  set: (v: string) => { cfg.value.server_labels = v.split(',').map(s => s.trim()).filter(Boolean) },
})

async function save() {
  saving.value = true
  saveError.value = ''
  saved.value = false
  try {
    const payload: Record<string, unknown> = { _section: active.value, ...cfg.value }
    // Convert arrays back to comma-string for sections that use csv()
    if (active.value === 'runtime') payload.ffmpeg_extra_args = ffmpegArgs.value
    if (active.value === 'indexer') payload.server_labels = serverLabels.value
    await saveSettings(payload)
    saved.value = true
    setTimeout(() => { saved.value = false }, 2500)
  } catch (e: unknown) {
    saveError.value = String(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  try { cfg.value = await getConfig() as Record<string, any> } catch {}
})
</script>

<style scoped>
.settings-wrap { display:flex; gap:20px; align-items:flex-start; }
.sidebar {
  display:flex; flex-direction:column; gap:2px; min-width:130px; flex-shrink:0;
  background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:8px;
}
.sec-btn {
  text-align:left; background:none; border:none; border-radius:5px;
  color:var(--muted); font-size:13px; padding:7px 10px; cursor:pointer;
}
.sec-btn:hover { background:rgba(255,255,255,.04); color:var(--text); }
.sec-btn.active { background:rgba(97,175,239,.12); color:var(--accent); font-weight:600; }
.panel { flex:1; min-width:0; background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:20px 24px; }
h2 { font-size:16px; font-weight:600; color:var(--text-bright); margin-bottom:16px; }
:deep(.field) { display:flex; flex-direction:column; gap:4px; margin-bottom:14px; }
:deep(.label) { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
:deep(input[type=text]), :deep(input[type=number]), :deep(input[type=password]), :deep(select) {
  background:var(--input-bg); border:1px solid var(--border); border-radius:5px;
  color:var(--text-bright); padding:7px 10px; font-size:13px; outline:none; max-width:420px;
}
:deep(input:focus), :deep(select:focus) { border-color:var(--accent); }
:deep(.check-row) {
  display:flex; align-items:center; gap:8px; cursor:pointer;
  font-size:13px; color:var(--text); margin-bottom:10px;
}
:deep(.check-row input[type=checkbox]) { width:15px; height:15px; accent-color:var(--accent); }
.hint { font-size:12px; color:var(--muted); margin-top:-6px; margin-bottom:10px; }
.hint a { color:var(--accent); }
.save-row { display:flex; align-items:center; gap:10px; margin-top:20px; padding-top:16px; border-top:1px solid var(--border); }
.btn {
  background:var(--accent); color:#1e2127; font-weight:600; font-size:13px;
  border:none; border-radius:5px; padding:8px 22px; cursor:pointer;
}
.btn:disabled { opacity:.5; cursor:default; }
.ok-msg  { font-size:12px; color:var(--green); }
.err-msg { font-size:12px; color:var(--red); }
</style>
