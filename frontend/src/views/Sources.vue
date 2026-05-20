<template>
  <div>
    <div class="page-head">
      <div>
        <h1>Sources</h1>
        <p class="sub">Priority-ordered HLS sources — first match wins. Drag to reorder. Built-ins (kkphim, ophim, nguonc) are always available.</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn ghost" @click="save" :disabled="saving">Discard</button>
        <button class="btn primary" @click="save" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save sources' }}
        </button>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Active sources <span style="color:var(--text-3);font-weight:500">· {{ order.length }}</span></h2>
          <p class="desc">Drag to reorder. First responder wins. Disable without removing via the remove button.</p>
        </div>
      </div>

      <div class="card-body">
        <div class="src-list">
          <div
            v-for="(src, i) in order"
            :key="src"
            class="src"
            draggable="true"
            @dragstart="dragStart(i)"
            @dragover.prevent="dragOver(i)"
            @drop="drop"
          >
            <div class="src-idx">{{ String(i + 1).padStart(2, '0') }}</div>
            <div class="src-handle">
              <button title="Move up" @click="moveUp(i)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
              </button>
              <button title="Move down" @click="moveDown(i)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
              </button>
            </div>
            <div>
              <div class="src-name">
                {{ src }}
                <span v-if="i === 0" class="badge teal" style="margin-left:6px">Primary</span>
              </div>
              <div class="src-url">{{ sourceUrl(src) }}</div>
            </div>
            <span class="badge" :class="builtins.includes(src) ? '' : 'amber'">
              {{ builtins.includes(src) ? 'Built-in' : 'Custom' }}
            </span>
            <div class="src-actions">
              <button class="icon-mini danger" title="Remove" @click="removeOrder(i)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>

          <div v-if="!order.length" class="empty-order">
            No sources — add built-ins below.
          </div>
        </div>

        <!-- Add source row -->
        <div class="add-row">
          <select v-model="addName" class="select" style="max-width:220px">
            <option value="">— add source —</option>
            <option v-for="b in availableBuiltins" :key="b" :value="b">{{ b }}</option>
          </select>
          <button class="btn" @click="addToOrder" :disabled="!addName">Add</button>
        </div>

        <!-- Custom template JSON -->
        <div style="margin-top:20px">
          <div class="field full">
            <label>
              HLS Template Sources
              <span class="hint">JSON array of custom source definitions</span>
            </label>
            <textarea v-model="templatesJson" class="json-area" spellcheck="false" rows="8" />
            <div v-if="jsonError" class="err-msg-inline">{{ jsonError }}</div>
          </div>
        </div>
      </div>

      <div class="card-foot">
        <span style="font-size:12.5px;color:var(--text-3)">Changes apply on save · resolver cache will be flushed</span>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
          <span v-if="saved" style="font-size:12px;color:var(--green)">✓ Saved</span>
          <span v-if="saveError" style="font-size:12px;color:var(--red)">{{ saveError }}</span>
          <button class="btn primary sm" @click="save" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save sources' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getConfig, saveSettings } from '../api'

const BUILTINS = ['kkphim', 'ophim', 'nguonc']
const BUILTIN_URLS: Record<string, string> = {
  kkphim: 'https://phimapi.com',
  ophim:  'https://ophim1.com',
  nguonc: 'https://phim.nguonc.com',
}

const builtins    = ref<string[]>(BUILTINS)
const order       = ref<string[]>([])
const templatesJson = ref('[]')
const jsonError   = ref('')
const saving      = ref(false)
const saved       = ref(false)
const saveError   = ref('')
const addName     = ref('')

const availableBuiltins = computed(() => builtins.value.filter(b => !order.value.includes(b)))

function sourceUrl(name: string): string {
  return BUILTIN_URLS[name] || 'custom source'
}

let drag = -1

function dragStart(i: number) { drag = i }
function dragOver(i: number) {
  if (drag === i) return
  const arr = [...order.value]
  const [item] = arr.splice(drag, 1)
  arr.splice(i, 0, item)
  order.value = arr
  drag = i
}
function drop() { drag = -1 }

function moveUp(i: number) {
  if (i === 0) return
  const arr = [...order.value];
  [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]
  order.value = arr
}
function moveDown(i: number) {
  if (i >= order.value.length - 1) return
  const arr = [...order.value];
  [arr[i], arr[i + 1]] = [arr[i + 1], arr[i]]
  order.value = arr
}

function removeOrder(i: number) { order.value.splice(i, 1) }

function addToOrder() {
  if (addName.value && !order.value.includes(addName.value)) {
    order.value.push(addName.value)
  }
  addName.value = ''
}

function validateJson() {
  jsonError.value = ''
  try {
    const parsed = JSON.parse(templatesJson.value)
    if (!Array.isArray(parsed)) throw new Error('Must be a JSON array')
    return parsed
  } catch (e: unknown) {
    jsonError.value = String(e)
    return null
  }
}

async function save() {
  const templates = validateJson()
  if (!templates) return
  saving.value = true
  saveError.value = ''
  saved.value = false
  try {
    await saveSettings({
      _section: 'sources',
      hls_template_sources: JSON.stringify(templates),
      source_order_json: JSON.stringify(order.value),
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 2500)
  } catch (e: unknown) {
    saveError.value = String(e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const cfg = await getConfig()
    order.value = [...((cfg.source_order as string[] | undefined) || [])]
    const tpl = cfg.hls_template_sources
    templatesJson.value = JSON.stringify(tpl, null, 2)
    if (Array.isArray(tpl)) {
      for (const t of tpl) {
        const name = (t as Record<string, string>).name
        if (name && !BUILTINS.includes(name)) builtins.value = [...new Set([...builtins.value, name])]
      }
    }
  } catch {}
})
</script>

<style scoped>
.add-row { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
.json-area {
  width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  color: var(--text); padding: 12px; font-family: var(--font-mono);
  font-size: 12px; line-height: 1.5; resize: vertical; outline: none;
  transition: border-color .12s;
}
.json-area:focus { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(94,224,189,.12); }
.empty-order { color: var(--text-3); font-size: 12px; text-align: center; padding: 16px 0; }
.err-msg-inline { font-size: 12px; color: var(--red); margin-top: 4px; }
</style>
