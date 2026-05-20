<template>
  <div>
    <div class="card">
      <div class="card-title">Source Priority</div>
      <div class="card-desc">Drag to reorder. The worker tries sources top-to-bottom.</div>
      <div class="order-list">
        <div
          v-for="(src, i) in order"
          :key="src"
          class="order-item"
          draggable="true"
          @dragstart="dragStart(i)"
          @dragover.prevent="dragOver(i)"
          @drop="drop(i)"
        >
          <span class="handle">⠿</span>
          <span class="src-name">{{ src }}</span>
          <span v-if="builtins.includes(src)" class="badge-builtin">built-in</span>
          <span v-else class="badge-custom">template</span>
          <button class="rm-btn" @click="removeOrder(i)">✕</button>
        </div>
        <div v-if="!order.length" class="empty-order">No sources in order — add built-ins or define templates below.</div>
      </div>
      <div class="add-row">
        <select v-model="addName">
          <option value="">— add source —</option>
          <option v-for="b in builtins.filter(b => !order.includes(b))" :key="b" :value="b">{{ b }}</option>
        </select>
        <button class="btn-sm" @click="addToOrder" :disabled="!addName">Add</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">HLS Template Sources</div>
      <div class="card-desc">JSON array of custom source definitions. See docs for schema.</div>
      <textarea v-model="templatesJson" class="json-area" spellcheck="false" rows="10" />
      <div v-if="jsonError" class="err-msg">{{ jsonError }}</div>
    </div>

    <div class="actions">
      <button class="btn" @click="save" :disabled="saving">{{ saving ? 'Saving…' : 'Save Sources' }}</button>
      <span v-if="saved" class="ok-msg">✓ Saved</span>
      <span v-if="saveError" class="err-msg">{{ saveError }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getConfig, saveSettings } from '../api'

const BUILTINS = ['kkphim', 'ophim', 'nguonc']
const builtins = ref<string[]>(BUILTINS)

const order = ref<string[]>([])
const templatesJson = ref('[]')
const jsonError = ref('')
const saving = ref(false)
const saved = ref(false)
const saveError = ref('')
const addName = ref('')

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
function drop(i: number) { drag = -1 }

function removeOrder(i: number) {
  order.value.splice(i, 1)
}

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
    const src = (cfg.source_order as string[] | undefined) || []
    order.value = [...src]
    const tpl = cfg.hls_template_sources
    templatesJson.value = JSON.stringify(tpl, null, 2)
    // Add custom template names that aren't already in built-ins to the add-list
    if (Array.isArray(tpl)) {
      for (const t of tpl) {
        const name = (t as Record<string,string>).name
        if (name && !BUILTINS.includes(name)) builtins.value = [...new Set([...builtins.value, name])]
      }
    }
  } catch {}
})
</script>

<style scoped>
.card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:18px 20px; margin-bottom:16px; }
.card-title { font-size:14px; font-weight:600; color:var(--text-bright); margin-bottom:4px; }
.card-desc  { font-size:12px; color:var(--muted); margin-bottom:12px; }
.order-list { display:flex; flex-direction:column; gap:6px; margin-bottom:10px; }
.order-item {
  display:flex; align-items:center; gap:8px;
  background:var(--input-bg); border:1px solid var(--border); border-radius:5px;
  padding:7px 10px; cursor:grab; user-select:none;
}
.order-item:active { cursor:grabbing; }
.handle { color:var(--muted); font-size:14px; }
.src-name { font-size:13px; color:var(--text-bright); flex:1; }
.badge-builtin { font-size:10px; background:rgba(97,175,239,.12); color:var(--accent); border-radius:3px; padding:1px 6px; }
.badge-custom  { font-size:10px; background:rgba(152,195,121,.12); color:var(--green); border-radius:3px; padding:1px 6px; }
.rm-btn { background:none; border:none; color:var(--muted); cursor:pointer; font-size:12px; margin-left:auto; padding:0 4px; }
.rm-btn:hover { color:var(--red); }
.empty-order { color:var(--muted); font-size:12px; text-align:center; padding:10px 0; }
.add-row { display:flex; align-items:center; gap:8px; }
select {
  background:var(--input-bg); border:1px solid var(--border); border-radius:5px;
  color:var(--text); padding:5px 8px; font-size:13px; outline:none;
}
.btn-sm {
  background:var(--surface); border:1px solid var(--border); border-radius:4px;
  color:var(--text); font-size:12px; padding:5px 12px; cursor:pointer;
}
.btn-sm:disabled { opacity:.4; cursor:default; }
.json-area {
  width:100%; background:var(--input-bg); border:1px solid var(--border); border-radius:5px;
  color:var(--text-bright); padding:10px; font-family:ui-monospace,Menlo,Consolas,monospace;
  font-size:12px; line-height:1.5; resize:vertical; outline:none;
}
.json-area:focus { border-color:var(--accent); }
.actions { display:flex; align-items:center; gap:10px; }
.btn {
  background:var(--accent); color:#1e2127; font-weight:600; font-size:13px;
  border:none; border-radius:5px; padding:8px 20px; cursor:pointer;
}
.btn:disabled { opacity:.5; cursor:default; }
.ok-msg  { font-size:12px; color:var(--green); }
.err-msg { font-size:12px; color:var(--red); }
</style>
